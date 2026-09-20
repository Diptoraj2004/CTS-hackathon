"""Core API. Pydantic models on every route already reject malformed input
before it reaches anything below (FastAPI does this automatically) — that's
the "schema validation gate" from the architecture doc, not a separate module.

Wraps the real RAG pipeline (understand -> retrieve -> injection scan ->
relevance gate -> generate -> cite -> decide — all in pipeline.answer(), one
call, see pipeline.py's module docstring for why it used to run twice) with
the safety spine: prompt-injection scanning on the live query and on
ingested documents; a mode-consistency check; PII/PHI redaction on the
final answer (and on everything that reaches the audit log); rate limiting;
an admin API key on mutating/internal routes; and a hash-chained,
disk-persisted audit trail. Every escalation lands in the same
disk-persisted human review queue.

/ingest runs its pipeline on a background thread and returns a job_id
immediately — see ingest_jobs.py for why.
"""
import os
import threading
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from backend.app.ingestion.export_to_rag_store import parse_and_chunk, store_chunks
from backend.ingest_jobs import create_job, get_job, update_job
from backend.rag import query_understanding
from backend.rag.generator import GenerationError
from backend.rag.pipeline import answer as rag_answer
from backend.rag.vector_store import delete_by_source_file, get_embedder, get_table
from backend.safety import injection_guard, redaction
from backend.safety.audit_log import AuditLog
from backend.safety.auth import require_admin_key
from backend.safety.gate_router import check_mode_consistency
from backend.safety.rate_limit import RateLimitMiddleware
from backend.safety.review_queue import HumanReviewQueue
from backend.safety.schemas import ChatbotResponse, QueryRequest

app = FastAPI(title="DrugDocQA Core API", version="0.7")

app.add_middleware(RateLimitMiddleware)

# React runs on a different origin (localhost:3000/5173) during dev — without
# this, the browser blocks every request before it even reaches the routes
# below. Tighten allow_origins to the real deployed URL before the demo.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

audit_log = AuditLog()
review_queue = HumanReviewQueue(audit_log)

UPLOAD_DIR = Path("data/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # the frontend already says "50 MB max" — this makes it real


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@app.on_event("startup")
def _warm_up_embedder():
    """Load the sentence-transformers model once at boot instead of on the
    first real request. A cold load can take 10-60s on a fresh Colab
    runtime — pay that cost here, not on someone's first /query or /ingest
    call during the demo."""
    get_embedder()
    status = redaction.redaction_status()
    if not status["active"]:
        print(f"[startup] WARNING: PII/PHI redaction is disabled — {status['reason']}")


def _escalate(query: str, mode: str, reason: str, risk_level: str, ip: str | None) -> ChatbotResponse:
    """risk_level: 'high' for a mode-consistency/safety-gate hit, 'low' for
    an evidence-quality escalation. `reason` is passed straight through —
    this used to get overwritten with review_queue's generic "a reviewer
    has been notified" message, so the actual cause never reached the
    frontend."""
    result = review_queue.flag(query, mode, reason)
    return ChatbotResponse(
        mode=mode, answer="", status="ESCALATED",
        reason=reason, risk_level=risk_level, request_id=result["request_id"],
    )


@app.post("/query", response_model=ChatbotResponse)
def process_query(req: QueryRequest, request: Request):
    ip = _client_ip(request)

    if injection_guard.looks_like_injection(req.query):
        audit_log.log("INJECTION_BLOCKED", req.query[:200], ip=ip)
        raise HTTPException(status_code=400, detail="That query couldn't be processed.")

    needs_review, reason = check_mode_consistency(req.query, req.mode)
    if needs_review:
        return _escalate(req.query, req.mode, reason, risk_level="high", ip=ip)

    try:
        # Single call: understand -> retrieve -> corpus injection scan ->
        # relevance gate -> generate -> cite, all inside pipeline.answer()
        # now. Previously main.py ran understand()+retrieve() itself just to
        # scan retrieved chunks, then rag_answer() ran the exact same two
        # calls again internally to actually generate — full pipeline twice
        # per query.
        result = rag_answer(req.query, mode=req.mode, session_id=req.session_id, drug_hint=req.drug_name)
    except GenerationError as e:
        audit_log.log("GENERATION_FAILED", f"session={req.session_id}: {e}", ip=ip)
        raise HTTPException(status_code=503, detail="The answer generator is unavailable right now.")

    if result.status == "ESCALATED":
        return _escalate(req.query, req.mode, result.reason or "insufficient evidence",
                         risk_level=result.risk_level or "low", ip=ip)

    safe_answer = redaction.redact(result.answer)
    audit_log.log("QUERY_ANSWERED", f"session={req.session_id}", ip=ip)
    return ChatbotResponse(
        mode=req.mode, answer=safe_answer, citations=result.citations,
        status="APPROVED", confidence=result.confidence,
    )


@app.get("/admin/auth/check", dependencies=[Depends(require_admin_key)])
def admin_auth_check():
    """Lightweight probe: validates the X-Admin-Key header using the existing
    require_admin_key dependency and returns 200 {"authenticated": true} if
    the key is correct.  The frontend admin login uses this to verify a key
    entered by the operator before storing it in sessionStorage — no new auth
    mechanism is involved, just a read-only probe of the existing one."""
    return {"authenticated": True}


def _run_ingestion(job_id: str, stored_path: Path, drug_name: str, doc_id: str | None) -> None:
    """Runs on a background thread, off the request/response cycle entirely.
    Parses directly from stored_path — the file's permanent, original-name-
    derived location — so citations and the document viewer never see a
    throwaway temp filename."""
    orig_label = stored_path.name
    try:
        update_job(job_id, stage="PARSING", detail="Parsing and chunking the document.")
        chunks = parse_and_chunk(str(stored_path), doc_id=doc_id, drug_name=drug_name)
        update_job(job_id, chunks_found=len(chunks))

        if not chunks:
            detail = "No readable text or sections found in document."
            audit_log.log("INGESTION_FAILED", f"file={orig_label}: {detail}")
            update_job(job_id, stage="FAILED", detail=detail, error=detail)
            stored_path.unlink(missing_ok=True)
            return

        update_job(job_id, stage="SCANNING", detail="Scanning chunks for hidden instructions.")
        flagged = [c for c in chunks if injection_guard.looks_like_injection(c.text)]
        if flagged:
            detail = f"{len(flagged)} of {len(chunks)} section(s) failed a safety check."
            audit_log.log("INGESTION_REJECTED", f"file={orig_label}: {detail}")
            update_job(job_id, stage="REJECTED", detail=detail, error=detail)
            stored_path.unlink(missing_ok=True)
            return

        update_job(job_id, stage="EMBEDDING", detail="Embedding chunks and writing to the vector store.")
        n = store_chunks(chunks)

        audit_log.log("INGESTION_ACCEPTED", f"file={orig_label}: {n} chunks stored")
        update_job(job_id, stage="STORED", detail=f"Stored {n} chunk(s).", chunks_stored=n)
    except Exception as e:
        audit_log.log("INGESTION_FAILED", f"file={orig_label}: {e}")
        update_job(job_id, stage="FAILED", detail="Ingestion failed.", error=str(e))
        stored_path.unlink(missing_ok=True)


@app.post("/ingest", dependencies=[Depends(require_admin_key)])
async def ingest_document(file: UploadFile, drug_name: str, doc_id: str | None = None):
    """Requires the admin key (X-Admin-Key header) — previously anyone could
    call this. Writes the upload straight to its permanent location under a
    job-id-prefixed, collision-proof filename, and hands the real
    parse -> scan -> embed pipeline to a background thread. Returns a
    job_id almost immediately. Poll GET /ingest/{job_id}/status for progress."""
    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail=f"File exceeds the {MAX_UPLOAD_BYTES // (1024*1024)} MB limit.")

    safe_filename = os.path.basename(file.filename or "upload")
    clean_drug_name = drug_name.strip().lower()

    job = create_job(filename=file.filename, drug_name=clean_drug_name, doc_id=doc_id)
    stored_path = UPLOAD_DIR / f"{job['job_id'][:8]}_{safe_filename}"
    stored_path.write_bytes(content)

    threading.Thread(
        target=_run_ingestion,
        args=(job["job_id"], stored_path, clean_drug_name, doc_id),
        daemon=True,
    ).start()
    return {"job_id": job["job_id"], "status": "QUEUED"}


@app.get("/ingest/{job_id}/status")
def ingest_status(job_id: str):
    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="unknown job id")
    return job


@app.get("/documents/{filename}/view")
def view_document(filename: str):
    """Public: this is what the patient/clinician-facing citation links open,
    not an admin action, so it doesn't require the admin key."""
    safe_filename = os.path.basename(filename)
    file_path = (UPLOAD_DIR / safe_filename).resolve()

    if not str(file_path).startswith(str(UPLOAD_DIR.resolve()) + os.sep):
        audit_log.log("UNAUTHORIZED_FILE_ACCESS", f"attempted_file={safe_filename}")
        raise HTTPException(status_code=403, detail="Access denied.")
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="Document not found.")

    ext = safe_filename.rsplit(".", 1)[-1].lower() if "." in safe_filename else ""
    if ext == "pdf":
        media_type = "application/pdf"
    elif ext == "xml":
        media_type = "application/xml"
    else:
        raise HTTPException(status_code=400, detail="Preview for this file type is not supported.")

    audit_log.log("DOCUMENT_VIEWED", f"filename={safe_filename}")
    return FileResponse(path=file_path, media_type=media_type,
                        headers={"Content-Disposition": f'inline; filename="{safe_filename}"'})


@app.get("/documents/{filename}/download")
def download_document(filename: str):
    """Public download endpoint: serves the stored document file as an attachment download."""
    safe_filename = os.path.basename(filename)
    file_path = (UPLOAD_DIR / safe_filename).resolve()

    if not str(file_path).startswith(str(UPLOAD_DIR.resolve()) + os.sep):
        audit_log.log("UNAUTHORIZED_FILE_ACCESS", f"attempted_file={safe_filename}")
        raise HTTPException(status_code=403, detail="Access denied.")
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="Document not found.")

    ext = safe_filename.rsplit(".", 1)[-1].lower() if "." in safe_filename else ""
    if ext == "pdf":
        media_type = "application/pdf"
    elif ext == "xml":
        media_type = "application/xml"
    elif ext in ("xlsx", "xls"):
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    elif ext in ("docx", "doc"):
        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    else:
        media_type = "application/octet-stream"

    audit_log.log("DOCUMENT_DOWNLOADED", f"filename={safe_filename}")
    return FileResponse(path=file_path, media_type=media_type,
                        filename=safe_filename,
                        headers={"Content-Disposition": f'attachment; filename="{safe_filename}"'})



@app.delete("/documents/{filename}", dependencies=[Depends(require_admin_key)])
def delete_document(filename: str, request: Request):
    """New: previously there was no way to remove a document at all — the
    library UI's delete affordance had nothing to call. Removes both the
    file on disk and its chunks from the vector store."""
    safe_filename = os.path.basename(filename)
    file_path = (UPLOAD_DIR / safe_filename).resolve()
    if not str(file_path).startswith(str(UPLOAD_DIR.resolve()) + os.sep):
        raise HTTPException(status_code=403, detail="Access denied.")

    removed_chunks = delete_by_source_file(safe_filename)
    file_existed = file_path.is_file()
    file_path.unlink(missing_ok=True)

    if not file_existed and removed_chunks == 0:
        raise HTTPException(status_code=404, detail="Document not found.")

    audit_log.log("DOCUMENT_DELETED", f"file={safe_filename}: {removed_chunks} chunk(s) removed",
                  ip=_client_ip(request))
    return {"filename": safe_filename, "chunks_removed": removed_chunks}


def _json_safe_records(df):
    """pandas NaN in a nullable numeric column serializes to invalid JSON
    and crashes the response with a 500. Swap NaN for None before to_dict()."""
    return df.astype(object).where(df.notna(), None).to_dict(orient="records")


@app.get("/sources")
def list_sources():
    table = get_table()
    if table is None:
        return []
    df = table.to_pandas()
    cols = [c for c in ["drug_name", "source_file", "version", "label_version", "effective_date", "ingestion_timestamp", "source_type"]
            if c in df.columns]
    return _json_safe_records(df[cols].drop_duplicates())


@app.get("/sources/{drug_name}")
def sources_for_drug(drug_name: str):
    table = get_table()
    if table is None:
        return []
    df = table.to_pandas()
    df = df[df["drug_name"].str.lower() == drug_name.lower()]
    cols = [c for c in ["chunk_id", "section", "source_file", "version", "page"]
            if c in df.columns]
    return _json_safe_records(df[cols])


@app.get("/drugs")
def list_drugs():
    """New: the medication selector was hard-coded (`popularDrugs`) and took
    free text, so users could pick a drug that was never ingested. This is
    the real list to build that dropdown from."""
    return {"drugs": query_understanding.known_drugs()}


@app.delete("/session/{session_id}", dependencies=[Depends(require_admin_key)])
def forget_session(session_id: str, request: Request):
    """Right-to-erasure for a session. Only clears per-session conversational
    state — the audit log is intentionally untouched (it's designed to never
    hold raw PII in the first place, so there's nothing sensitive to remove).
    Admin-key gated: this is a destructive action on behalf of a user, not
    something any anonymous caller should be able to trigger for any session_id."""
    cleared = query_understanding.forget(session_id)
    audit_log.log("SESSION_ERASURE_REQUESTED", f"session={session_id}", ip=_client_ip(request))
    return {"status": "ACKNOWLEDGED", "cleared": cleared}


@app.get("/review/pending", dependencies=[Depends(require_admin_key)])
def pending_reviews():
    return review_queue.pending()


@app.get("/review/{request_id}", dependencies=[Depends(require_admin_key)])
def get_review(request_id: str):
    """New: the response schema promised the frontend could poll a pending
    review by request_id; there was no endpoint to poll."""
    try:
        return review_queue.get(request_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="unknown request id")


@app.post("/review/{request_id}", dependencies=[Depends(require_admin_key)])
def resolve_review(request_id: str, action: str, notes: str = "", answer: str | None = None):
    try:
        return review_queue.resolve(request_id, action, notes, answer)
    except KeyError:
        raise HTTPException(status_code=404, detail="unknown request id")


@app.get("/audit/verify")
def verify_audit():
    ok, msg = audit_log.verify()
    return {"valid": ok, "message": msg, "entries": len(audit_log)}


@app.get("/audit/logs", dependencies=[Depends(require_admin_key)])
def list_audit_logs(limit: int = 100, offset: int = 0):
    """New: /audit/verify only ever returned counts. This is the actual
    listing the AuditLogs admin page needs, instead of static mock rows."""
    return {"entries": audit_log.entries(limit=limit, offset=offset), "total": len(audit_log)}


@app.get("/dashboard/stats", dependencies=[Depends(require_admin_key)])
def dashboard_stats():
    """New: the admin dashboard had nothing real to show numbers from."""
    table = get_table()
    n_chunks = table.count_rows() if table is not None else 0
    n_drugs = len(query_understanding.known_drugs())
    ok, _ = audit_log.verify()
    return {
        "documents_indexed": n_drugs,
        "chunks_indexed": n_chunks,
        "pending_reviews": len(review_queue.pending()),
        "audit_entries": len(audit_log),
        "audit_chain_valid": ok,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)

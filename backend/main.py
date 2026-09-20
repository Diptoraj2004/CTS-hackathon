"""Core API. Pydantic models on every route already reject malformed input
before it reaches anything below (FastAPI does this automatically) — that's
the "schema validation gate" from the architecture doc, not a separate module.

Wraps the real RAG pipeline (understand -> retrieve -> relevance gate ->
generate -> cite -> decide) with the safety spine: prompt-injection scanning
on the query, retrieved chunks, AND ingested documents; a mode-consistency
check; PII/PHI redaction on the final answer (and on everything that reaches
the audit log — see audit_log.py); rate limiting; and a hash-chained audit
trail. Every escalation lands in the same human review queue.

/ingest runs its pipeline on a background thread and returns a job_id
immediately — see ingest_jobs.py for why.
"""
import os
import threading
from pathlib import Path

from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from backend.app.ingestion.export_to_rag_store import parse_and_chunk, store_chunks
from backend.ingest_jobs import create_job, get_job, update_job
from backend.rag import query_understanding, retriever
from backend.rag.generator import GenerationError
from backend.rag.pipeline import answer as rag_answer
from backend.rag.vector_store import get_embedder, get_table
from backend.safety import gate_router, injection_guard, redaction
from backend.safety.audit_log import AuditLog
from backend.safety.rate_limit import RateLimitMiddleware
from backend.safety.review_queue import HumanReviewQueue
from backend.safety.schemas import ChatbotResponse, QueryRequest

app = FastAPI(title="DrugDocQA Core API", version="0.6")

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


def _escalate(query: str, mode: str, reason: str, risk_level: str) -> ChatbotResponse:
    """risk_level: 'high' for a mode-consistency/safety gate hit, 'low' for an
    evidence-quality escalation from the RAG pipeline. Previously this always
    overwrote `reason` with review_queue's generic "a reviewer has been
    notified" message — the actual cause (e.g. "clinician-level question in
    patient mode") never left the server, so the frontend's regex-matching on
    `reason` could never work. `reason` is now the real reason; risk_level is
    the machine-readable field the frontend should actually key off of."""
    result = review_queue.flag(query, mode, reason)
    return ChatbotResponse(
        mode=mode, answer="", status="ESCALATED",
        reason=reason, risk_level=risk_level, request_id=result["request_id"],
    )


@app.post("/query", response_model=ChatbotResponse)
def process_query(req: QueryRequest):
    if injection_guard.looks_like_injection(req.query):
        audit_log.log("INJECTION_BLOCKED", req.query[:200])
        raise HTTPException(status_code=400, detail="That query couldn't be processed.")

    needs_review, reason = gate_router.check_mode_consistency(req.query, req.mode)
    if needs_review:
        return _escalate(req.query, req.mode, reason, risk_level="high")

    info = query_understanding.understand(
        req.query, mode=req.mode, session_id=req.session_id, drug_hint=req.drug_name,
    )
    retrieved = retriever.retrieve(info.standalone_query, info.drug_names, sections=info.section_hints)
    if any(injection_guard.looks_like_injection(r.chunk.text) for r in retrieved):
        audit_log.log("INJECTION_BLOCKED_IN_CORPUS", info.standalone_query[:200])
        raise HTTPException(status_code=422, detail="A source document failed a safety check.")

    try:
        result = rag_answer(req.query, mode=req.mode, session_id=req.session_id)
    except GenerationError as e:
        # Neither Groq nor Ollama could produce an answer (e.g. Ollama isn't
        # running and GROQ_API_KEY isn't set). Previously unhandled -> 500.
        audit_log.log("GENERATION_FAILED", f"session={req.session_id}: {e}")
        raise HTTPException(status_code=503, detail="The answer generator is unavailable right now.")

    if result.status == "ESCALATED":
        return _escalate(req.query, req.mode, result.reason or "insufficient evidence", risk_level="low")

    safe_answer = redaction.redact(result.answer)
    audit_log.log("QUERY_ANSWERED", f"session={req.session_id}")
    return ChatbotResponse(
        mode=req.mode, answer=safe_answer, citations=result.citations,
        status="APPROVED", confidence=result.confidence,
    )


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

        update_job(job_id, stage="SCANNING", detail="Scanning chunks for hidden instructions.")
        flagged = [c for c in chunks if injection_guard.looks_like_injection(c.text)]
        if flagged:
            detail = f"{len(flagged)} of {len(chunks)} section(s) failed a safety check."
            audit_log.log("INGESTION_REJECTED", f"file={orig_label}: {detail}")
            update_job(job_id, stage="REJECTED", detail=detail, error=detail)
            stored_path.unlink(missing_ok=True)  # don't keep bytes for a rejected document
            return

        update_job(job_id, stage="EMBEDDING", detail="Embedding chunks and writing to the vector store.")
        n = store_chunks(chunks)  # also registers the version metadata now — see export_to_rag_store.py

        audit_log.log("INGESTION_ACCEPTED", f"file={orig_label}: {n} chunks stored")
        update_job(job_id, stage="STORED", detail=f"Stored {n} chunk(s).", chunks_stored=n)
    except Exception as e:
        audit_log.log("INGESTION_FAILED", f"file={orig_label}: {e}")
        update_job(job_id, stage="FAILED", detail="Ingestion failed.", error=str(e))
        stored_path.unlink(missing_ok=True)


@app.post("/ingest")
async def ingest_document(file: UploadFile, drug_name: str, doc_id: str | None = None):
    """Accepts the upload, writes it straight to its permanent location under
    a job-id-prefixed, collision-proof filename (previously: a random temp
    file, whose gibberish name then leaked into every citation and the
    document viewer, and re-uploading a same-named file just overwrote it),
    and hands the real parse -> scan -> embed pipeline to a background
    thread. Returns a job_id almost immediately. Poll
    GET /ingest/{job_id}/status for progress."""
    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail=f"File exceeds the {MAX_UPLOAD_BYTES // (1024*1024)} MB limit.")

    safe_filename = os.path.basename(file.filename or "upload")
    clean_drug_name = drug_name.strip().lower()  # retriever.py filters on drug_name.lower() —
    # storing anything else here means an uploaded "Paracetamol" can never be
    # found by a query for "paracetamol". This was the single biggest reason
    # retrieval could come back empty for a freshly-ingested drug.

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
    """Safely serves uploaded documents for viewing in the browser (e.g. PDFs inline)."""
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
    return FileResponse(
        path=file_path,
        media_type=media_type,
        headers={"Content-Disposition": f'inline; filename="{safe_filename}"'},
    )


def _json_safe_records(df):
    """pandas NaN in a nullable numeric column serializes to invalid JSON
    (`NaN` is not valid JSON) and crashes the response with a 500. Swap NaN
    for None before to_dict()."""
    return df.astype(object).where(df.notna(), None).to_dict(orient="records")


@app.get("/sources")
def list_sources():
    """Every distinct document currently backing the chatbot's answers —
    the transparency endpoint: where the data is actually coming from."""
    table = get_table()
    if table is None:
        return []
    df = table.to_pandas()
    cols = [c for c in ["drug_name", "source_file", "version", "effective_date", "source_type"]
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


@app.delete("/session/{session_id}")
def forget_session(session_id: str):
    """Right-to-erasure for a session. Only clears per-session conversational
    state — the audit log is intentionally untouched (it's designed to never
    hold raw PII in the first place, so there's nothing sensitive to remove)."""
    cleared = query_understanding.forget(session_id)
    audit_log.log("SESSION_ERASURE_REQUESTED", f"session={session_id}")
    return {"status": "ACKNOWLEDGED", "cleared": cleared}


@app.get("/review/pending")
def pending_reviews():
    return review_queue.pending()


@app.post("/review/{request_id}")
def resolve_review(request_id: str, action: str, notes: str = "", answer: str | None = None):
    try:
        return review_queue.resolve(request_id, action, notes, answer)
    except KeyError:
        raise HTTPException(status_code=404, detail="unknown request id")


@app.get("/audit/verify")
def verify_audit():
    ok, msg = audit_log.verify()
    return {"valid": ok, "message": msg, "entries": len(audit_log)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)

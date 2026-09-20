"""Core API. See pipeline.py, ingest_jobs.py, audit_log.py, review_queue.py,
redaction.py, auth.py module docstrings for the reasoning behind each piece."""
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from backend.app.ingestion.export_to_rag_store import parse_and_chunk, store_chunks
from backend.ingest_jobs import create_job, get_job, update_job
from backend.paths import DATA_DIR
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
from backend.safety.schemas import ChatbotResponse, QueryRequest, ReviewResolution

app = FastAPI(title="DrugDocQA Core API", version="0.8")

app.add_middleware(RateLimitMiddleware)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    # 422 now only ever means "your request body was malformed" — it used to
    # get reused for a corpus prompt-injection hit ("A source document failed
    # a safety check"), which is a completely different situation and now
    # goes through pipeline.py's ESCALATED path instead, never an HTTP error.
    errors = [f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors()]
    return JSONResponse(status_code=422, content={"detail": "Invalid request: " + "; ".join(errors)})


audit_log = AuditLog()
review_queue = HumanReviewQueue(audit_log)

UPLOAD_DIR = DATA_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

MAX_UPLOAD_BYTES = 50 * 1024 * 1024

# Bounded: unbounded threading.Thread-per-upload meant N concurrent /ingest
# calls spawned N CPU-heavy parse/embed threads at once. 3 workers queue the
# rest instead of piling on.
_ingest_executor = ThreadPoolExecutor(max_workers=3, thread_name_prefix="ingest")


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@app.on_event("startup")
def _warm_up_embedder():
    get_embedder()
    status = redaction.redaction_status()
    if not status["active"]:
        print(f"[startup] WARNING: PII/PHI redaction is disabled — {status['reason']}")


def _escalate(query: str, mode: str, reason: str, risk_level: str, ip: str | None) -> ChatbotResponse:
    result = review_queue.flag(query, mode, reason)
    return ChatbotResponse(mode=mode, answer="", status="ESCALATED",
                           reason=reason, risk_level=risk_level, request_id=result["request_id"])


@app.post("/query", response_model=ChatbotResponse)
def process_query(req: QueryRequest, request: Request):
    ip = _client_ip(request)

    if injection_guard.looks_like_injection(req.query):
        audit_log.log("INJECTION_BLOCKED", req.query[:200], ip=ip, status="BLOCKED")
        raise HTTPException(status_code=400, detail="That query couldn't be processed.")

    needs_review, reason = check_mode_consistency(req.query, req.mode)
    if needs_review:
        return _escalate(req.query, req.mode, reason, risk_level="high", ip=ip)

    try:
        result = rag_answer(req.query, mode=req.mode, session_id=req.session_id, drug_hint=req.drug_name)
    except GenerationError as e:
        audit_log.log("GENERATION_FAILED", f"session={req.session_id}: {e}", ip=ip, status="FAILED")
        raise HTTPException(status_code=503, detail="The answer generator is unavailable right now.")

    if result.status == "ESCALATED":
        return _escalate(req.query, req.mode, result.reason or "insufficient evidence",
                         risk_level=result.risk_level or "low", ip=ip)

    audit_log.log("QUERY_ANSWERED", f"session={req.session_id}", ip=ip, status="SUCCESS")
    return ChatbotResponse(mode=req.mode, answer=result.answer, citations=result.citations,
                           status="APPROVED", confidence=result.confidence)


def _run_ingestion(job_id: str, stored_path: Path, drug_name: str, doc_id: str | None,
                   original_filename: str) -> None:
    try:
        update_job(job_id, stage="PARSING", detail="Parsing and chunking the document.")
        chunks = parse_and_chunk(str(stored_path), doc_id=doc_id, drug_name=drug_name,
                                 original_filename=original_filename)
        update_job(job_id, chunks_found=len(chunks))

        if len(chunks) == 0:
            # Previously: 0 chunks (blank/unreadable PDF, OCR failed on
            # every page) still ended in STORED with chunks_stored=0 — a
            # silent success for a document that contributed nothing.
            detail = "No extractable text — parsing and OCR both produced nothing usable."
            audit_log.log("INGESTION_FAILED", f"file={original_filename}: {detail}",
                          resource=f"document:{original_filename}", status="FAILED")
            update_job(job_id, stage="FAILED", detail=detail, error=detail)
            stored_path.unlink(missing_ok=True)
            return

        update_job(job_id, stage="SCANNING", detail="Scanning chunks for hidden instructions.")
        flagged = [c for c in chunks if injection_guard.looks_like_injection(c.text)]
        if flagged:
            detail = f"{len(flagged)} of {len(chunks)} section(s) failed a safety check."
            audit_log.log("INGESTION_REJECTED", f"file={original_filename}: {detail}",
                          resource=f"document:{original_filename}", status="REJECTED")
            update_job(job_id, stage="REJECTED", detail=detail, error=detail)
            stored_path.unlink(missing_ok=True)
            return

        update_job(job_id, stage="EMBEDDING", detail="Embedding chunks and writing to the vector store.")
        n = store_chunks(chunks)
        query_understanding.invalidate_known_drugs_cache()

        audit_log.log("INGESTION_ACCEPTED", f"file={original_filename}: {n} chunks stored",
                      resource=f"document:{original_filename}", status="SUCCESS")
        update_job(job_id, stage="STORED", detail=f"Stored {n} chunk(s).", chunks_stored=n)
    except Exception as e:
        audit_log.log("INGESTION_FAILED", f"file={original_filename}: {e}",
                      resource=f"document:{original_filename}", status="FAILED")
        update_job(job_id, stage="FAILED", detail="Ingestion failed.", error=str(e))
        stored_path.unlink(missing_ok=True)


@app.post("/ingest", dependencies=[Depends(require_admin_key)])
async def ingest_document(file: UploadFile, drug_name: str, doc_id: str | None = None):
    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail=f"File exceeds the {MAX_UPLOAD_BYTES // (1024*1024)} MB limit.")

    safe_filename = os.path.basename(file.filename or "upload")
    clean_drug_name = drug_name.strip().lower()

    job = create_job(filename=file.filename, drug_name=clean_drug_name, doc_id=doc_id)
    stored_path = UPLOAD_DIR / f"{job['job_id'][:8]}_{safe_filename}"
    stored_path.write_bytes(content)

    _ingest_executor.submit(_run_ingestion, job["job_id"], stored_path, clean_drug_name, doc_id, safe_filename)
    return {"job_id": job["job_id"], "status": "QUEUED"}


@app.get("/ingest/{job_id}/status")
def ingest_status(job_id: str):
    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="unknown job id")
    return job


@app.get("/documents/{filename}/view")
def view_document(filename: str):
    safe_filename = os.path.basename(filename)
    file_path = (UPLOAD_DIR / safe_filename).resolve()
    if not str(file_path).startswith(str(UPLOAD_DIR.resolve()) + os.sep):
        audit_log.log("UNAUTHORIZED_FILE_ACCESS", f"attempted_file={safe_filename}", status="BLOCKED")
        raise HTTPException(status_code=403, detail="Access denied.")
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="Document not found.")

    ext = safe_filename.rsplit(".", 1)[-1].lower() if "." in safe_filename else ""
    media_type = {"pdf": "application/pdf", "xml": "application/xml"}.get(ext)
    if not media_type:
        raise HTTPException(status_code=400, detail="Preview for this file type is not supported.")

    audit_log.log("DOCUMENT_VIEWED", f"filename={safe_filename}", resource=f"document:{safe_filename}")
    return FileResponse(path=file_path, media_type=media_type,
                        headers={"Content-Disposition": f'inline; filename="{safe_filename}"'})


@app.delete("/documents/{filename}", dependencies=[Depends(require_admin_key)])
def delete_document(filename: str, request: Request):
    safe_filename = os.path.basename(filename)
    file_path = (UPLOAD_DIR / safe_filename).resolve()
    if not str(file_path).startswith(str(UPLOAD_DIR.resolve()) + os.sep):
        raise HTTPException(status_code=403, detail="Access denied.")

    removed_chunks = delete_by_source_file(safe_filename)
    file_existed = file_path.is_file()
    file_path.unlink(missing_ok=True)
    if not file_existed and removed_chunks == 0:
        raise HTTPException(status_code=404, detail="Document not found.")

    query_understanding.invalidate_known_drugs_cache()
    audit_log.log("DOCUMENT_DELETED", f"file={safe_filename}: {removed_chunks} chunk(s) removed",
                  ip=_client_ip(request), resource=f"document:{safe_filename}", status="SUCCESS")
    return {"filename": safe_filename, "chunks_removed": removed_chunks}


def _json_safe_records(df):
    return df.astype(object).where(df.notna(), None).to_dict(orient="records")


@app.get("/sources")
def list_sources():
    table = get_table()
    if table is None:
        return []
    df = table.to_pandas()
    cols = [c for c in ["drug_name", "source_file", "original_filename", "version",
                        "effective_date", "source_type"] if c in df.columns]
    return _json_safe_records(df[cols].drop_duplicates())


@app.get("/sources/{drug_name}")
def sources_for_drug(drug_name: str):
    table = get_table()
    if table is None:
        return []
    df = table.to_pandas()
    df = df[df["drug_name"].str.lower() == drug_name.lower()]
    cols = [c for c in ["chunk_id", "section", "source_file", "original_filename", "version", "page"]
            if c in df.columns]
    return _json_safe_records(df[cols])


@app.get("/drugs")
def list_drugs():
    return {"drugs": query_understanding.known_drugs()}


@app.get("/review/{request_id}")
def get_review(request_id: str):
    # No admin key: a user needs to poll their own escalation's status.
    try:
        return review_queue.get(request_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="unknown request id")


@app.delete("/session/{session_id}")
def forget_session(session_id: str, request: Request):
    # No admin key: a user must be able to erase their own session.
    cleared = query_understanding.forget(session_id)
    audit_log.log("SESSION_ERASURE_REQUESTED", f"session={session_id}",
                  ip=_client_ip(request), resource=f"session:{session_id}", status="SUCCESS")
    return {"status": "ACKNOWLEDGED", "cleared": cleared}


@app.get("/review/pending", dependencies=[Depends(require_admin_key)])
def pending_reviews():
    return review_queue.pending()


@app.post("/review/{request_id}", dependencies=[Depends(require_admin_key)])
def resolve_review(request_id: str, body: ReviewResolution):
    try:
        return review_queue.resolve(request_id, body.action, body.notes, body.answer)
    except KeyError:
        raise HTTPException(status_code=404, detail="unknown request id")


@app.get("/audit/verify")
def verify_audit():
    ok, msg = audit_log.verify()
    return {"valid": ok, "message": msg, "entries": len(audit_log)}


@app.get("/redaction/status", dependencies=[Depends(require_admin_key)])
def get_redaction_status():
    return redaction.redaction_status()


@app.get("/audit/logs", dependencies=[Depends(require_admin_key)])
def list_audit_logs(limit: int = 100, offset: int = 0):
    return {"entries": audit_log.entries(limit=limit, offset=offset), "total": len(audit_log)}


@app.get("/dashboard/stats", dependencies=[Depends(require_admin_key)])
def dashboard_stats():
    table = get_table()
    n_chunks = 0
    n_documents = 0
    if table is not None:
        n_chunks = table.count_rows()
        # honest note: this still loads the full table into pandas to get a
        # distinct source_file count — no lighter path found in the pinned
        # LanceDB API without risking an untested call. Correct now
        # (documents, not drugs); not yet optimized.
        df = table.to_pandas()
        n_documents = df["source_file"].nunique() if "source_file" in df.columns else 0
    ok, _ = audit_log.verify()
    return {
        "documents_indexed": n_documents,
        "chunks_indexed": n_chunks,
        "pending_reviews": len(review_queue.pending()),
        "audit_entries": len(audit_log),
        "audit_chain_valid": ok,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)

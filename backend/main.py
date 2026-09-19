"""Core API. Pydantic models on every route already reject malformed input
before it reaches anything below (FastAPI does this automatically) — that's
the "schema validation gate" from the architecture doc, not a separate module.

Wraps the real RAG pipeline (understand -> retrieve -> relevance gate ->
generate -> cite -> decide) with the safety spine: prompt-injection scanning
on the query, retrieved chunks, AND ingested documents; a mode-consistency
check; PII/PHI redaction on the final answer (and on everything that reaches
the audit log — see audit_log.py); rate limiting; and a hash-chained audit
trail. Every escalation lands in the same human review queue.
"""
import tempfile

from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from backend.app.ingestion.export_to_rag_store import parse_and_chunk, store_chunks
from backend.rag import query_understanding, retriever
from backend.rag.pipeline import answer as rag_answer
from backend.rag.vector_store import get_table
from backend.safety import gate_router, injection_guard, redaction
from backend.safety.audit_log import AuditLog
from backend.safety.rate_limit import RateLimitMiddleware
from backend.safety.review_queue import HumanReviewQueue
from backend.safety.schemas import ChatbotResponse, QueryRequest

app = FastAPI(title="DrugDocQA Core API", version="0.4")

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


def _escalate(query: str, mode: str, reason: str) -> ChatbotResponse:
    result = review_queue.flag(query, mode, reason)
    return ChatbotResponse(
        mode=mode, answer="", status="ESCALATED",
        reason=result["message"], request_id=result["request_id"],
    )


@app.post("/query", response_model=ChatbotResponse)
def process_query(req: QueryRequest):
    if injection_guard.looks_like_injection(req.query):
        audit_log.log("INJECTION_BLOCKED", req.query[:200])
        raise HTTPException(status_code=400, detail="That query couldn't be processed.")

    needs_review, reason = gate_router.check_mode_consistency(req.query, req.mode)
    if needs_review:
        return _escalate(req.query, req.mode, reason)

    info = query_understanding.understand(req.query, mode=req.mode, session_id=req.session_id)
    retrieved = retriever.retrieve(info.standalone_query, info.drug_names, sections=info.section_hints)
    if any(injection_guard.looks_like_injection(r.chunk.text) for r in retrieved):
        audit_log.log("INJECTION_BLOCKED_IN_CORPUS", info.standalone_query[:200])
        raise HTTPException(status_code=422, detail="A source document failed a safety check.")

    result = rag_answer(req.query, mode=req.mode, session_id=req.session_id)

    if result.status == "ESCALATED":
        return _escalate(req.query, req.mode, result.reason or "insufficient evidence")

    safe_answer = redaction.redact(result.answer)
    audit_log.log("QUERY_ANSWERED", f"session={req.session_id}")
    return ChatbotResponse(
        mode=req.mode, answer=safe_answer, citations=result.citations,
        status="APPROVED", confidence=result.confidence,
    )


@app.post("/ingest")
async def ingest_document(file: UploadFile, drug_name: str, doc_id: str | None = None):
    """Parses and chunks first, scans every chunk for hidden instructions,
    and only writes to the shared store if nothing was flagged — so a
    malicious upload can't poison the corpus for every future query.
    Every outcome (accepted or rejected) is audit-logged either way, which
    is the "what was entered vs not processed" notification."""
    suffix = "." + file.filename.rsplit(".", 1)[-1] if "." in file.filename else ""
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name

    try:
        chunks = parse_and_chunk(tmp_path, doc_id=doc_id, drug_name=drug_name)
    except Exception as e:
        audit_log.log("INGESTION_FAILED", f"file={file.filename}: {e}")
        raise HTTPException(status_code=422, detail=f"Could not parse this file: {e}")

    flagged = [c for c in chunks if injection_guard.looks_like_injection(c.text)]
    if flagged:
        audit_log.log(
            "INGESTION_REJECTED",
            f"file={file.filename}: {len(flagged)} of {len(chunks)} chunks flagged, whole document rejected",
        )
        raise HTTPException(
            status_code=422,
            detail=f"Document rejected: {len(flagged)} section(s) failed a safety check.",
        )

    n = store_chunks(chunks)
    audit_log.log("INGESTION_ACCEPTED", f"file={file.filename}: {n} chunks stored")
    return {"status": "ACCEPTED", "filename": file.filename, "chunks_stored": n}


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
    return df[cols].drop_duplicates().to_dict(orient="records")


@app.get("/sources/{drug_name}")
def sources_for_drug(drug_name: str):
    table = get_table()
    if table is None:
        return []
    df = table.to_pandas()
    df = df[df["drug_name"].str.lower() == drug_name.lower()]
    cols = [c for c in ["chunk_id", "section", "source_file", "version", "page"]
            if c in df.columns]
    return df[cols].to_dict(orient="records")


@app.delete("/session/{session_id}")
def forget_session(session_id: str):
    """Right-to-erasure for a session. Only clears per-session conversational
    state — the audit log is intentionally untouched (see audit_log.py for
    why: it's designed to never hold raw PII in the first place, so there's
    nothing sensitive in it to remove)."""
    # TODO(soumya): query_understanding's session memory needs a
    # forget(session_id) function exposed — nothing to call yet.
    audit_log.log("SESSION_ERASURE_REQUESTED", f"session={session_id}")
    return {"status": "ACKNOWLEDGED", "note": "session memory clear pending query_understanding.forget()"}


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

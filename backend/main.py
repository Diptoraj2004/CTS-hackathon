"""Core API. Pydantic models on every route already reject malformed input
before it reaches anything below (FastAPI does this automatically) — that's
the "schema validation gate" from the architecture doc, not a separate module.
Generation (Groq/Ollama) is Soumya's next piece and isn't in the repo yet;
marked below."""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from backend.rag import config as rag_config
from backend.rag import query_understanding, retriever
from backend.rag.schemas import Citation
from backend.safety import gate_router, injection_guard, redaction
from backend.safety.audit_log import AuditLog
from backend.safety.review_queue import HumanReviewQueue
from backend.safety.schemas import ChatbotResponse, QueryRequest

app = FastAPI(title="DrugDocQA Core API", version="0.2")

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

    info = query_understanding.understand(req.query, mode=req.mode, session_id=req.session_id)
    retrieved = retriever.retrieve(info.standalone_query, info.drug_names, sections=info.section_hints)

    if not retrieved or retrieved[0].score < rag_config.MIN_RELEVANCE:
        return _escalate(req.query, req.mode, "insufficient retrieval evidence")

    needs_review, reason = gate_router.check_mode_consistency(req.query, req.mode)
    if needs_review:
        return _escalate(req.query, req.mode, reason)

    chunk_texts = [r.chunk.text for r in retrieved]
    if any(injection_guard.looks_like_injection(t) for t in chunk_texts):
        audit_log.log("INJECTION_BLOCKED_IN_CORPUS", info.standalone_query[:200])
        raise HTTPException(status_code=422, detail="A source document failed a safety check.")

    prompt = injection_guard.delimit_context(chunk_texts, req.query)

    # TODO(soumya): swap this for the real Groq-primary/Ollama-fallback call
    raw_answer = f"[generation pending — prompt ready, {len(chunk_texts)} chunks in context]"

    safe_answer = redaction.redact(raw_answer)
    query_understanding.remember_answer(req.session_id, safe_answer)

    citations = [
        Citation(chunk_id=r.chunk.chunk_id, doc=r.chunk.source_file,
                 section=r.chunk.section, page=r.chunk.page)
        for r in retrieved
    ]
    audit_log.log("QUERY_ANSWERED", f"session={req.session_id}")
    return ChatbotResponse(mode=req.mode, answer=safe_answer, citations=citations,
                            status="APPROVED", confidence=retrieved[0].score)


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

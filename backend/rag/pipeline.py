"""RAG pipeline: understand -> retrieve -> injection scan -> relevance gate ->
generate -> cite -> decide. Returns the RAGResponse JSON the frontend receives.

main.py used to call understand() and retrieve() itself (to run the
prompt-injection scan on retrieved chunks) and then call this function,
which did understand() and retrieve() again internally to generate the
actual answer — the whole pipeline ran twice per query, roughly doubling
latency on top of an already-slow LLM call. The scan is folded in here
instead, so main.py just calls answer() once and gets everything."""
from backend.rag import config
from backend.rag.citation import process as process_citations
from backend.rag.generator import NOT_IN_CONTEXT, generate
from backend.rag.query_understanding import remember_answer, understand
from backend.rag.relevance_gate import check
from backend.rag.retriever import retrieve
from backend.rag.schemas import Mode, RAGResponse
from backend.safety import injection_guard
from backend.safety.redaction import RedactionUnavailable, redact

FALLBACK = {
    "clinician": "Insufficient reliable evidence in the uploaded labels to answer this confidently. "
                 "The query has been flagged for human review.",
    "patient": "I couldn't find enough reliable information in the uploaded drug documents to answer "
               "this safely. Your question has been flagged for review. Please ask your doctor or "
               "pharmacist.",
}


def _escalate(mode: Mode, reason: str, confidence: float, session_id: str,
              risk_level: str = "low") -> RAGResponse:
    remember_answer(session_id, FALLBACK[mode])
    return RAGResponse(mode=mode, answer=FALLBACK[mode], status="ESCALATED",
                       confidence=round(confidence, 2), reason=reason, risk_level=risk_level)


def answer(query: str, mode: Mode, session_id: str = "default", drug_hint: str | None = None) -> RAGResponse:
    info = understand(query, mode=mode, session_id=session_id, drug_hint=drug_hint)
    retrieved = retrieve(info.standalone_query, info.drug_names, sections=info.section_hints)

    if any(injection_guard.looks_like_injection(r.chunk.text) for r in retrieved):
        # A source document hides an instruction for the model — this is a
        # safety-relevant hit (indirect prompt injection via the corpus),
        # so it's high risk in the same sense a mode-mismatch is, not a
        # plain evidence-quality issue.
        return _escalate(mode, "A source document failed a safety check.", 0.0, session_id, risk_level="high")

    gate = check(info, retrieved)
    if not gate.passed:
        return _escalate(mode, gate.reason, gate.top_score, session_id)

    gen = generate(info, gate.evidence)
    if NOT_IN_CONTEXT in gen.text:
        return _escalate(mode, "Answer not found in the retrieved label sections",
                         gate.top_score, session_id)

    try:
        safe_text = redact(gen.text)
    except RedactionUnavailable as e:
        # Fail closed: an answer that hasn't been redacted must never reach
        # citation processing or the user, however good it looks otherwise.
        return _escalate(mode, f"Redaction unavailable, answer withheld: {e}",
                         0.0, session_id, risk_level="high")

    cit = process_citations(safe_text, gate.evidence, question=query)
    confidence = (gate.top_score + cit.coverage) / 2

    if cit.invalid_refs:
        return _escalate(mode, f"Model cited non-existent sources: {cit.invalid_refs}",
                         confidence, session_id)
    if cit.ungrounded_topics:
        return _escalate(mode, "High-risk topic not covered by the cited label sections: "
                         + ", ".join(cit.ungrounded_topics), confidence, session_id)
    if cit.unsupported_numbers:
        return _escalate(mode, "Numbers in the answer do not match the cited source: "
                         + " | ".join(cit.unsupported_numbers), confidence, session_id)
    if not cit.citations:
        return _escalate(mode, "Answer contains no citations", confidence, session_id)
    if cit.coverage < config.MIN_CITATION_COVERAGE:
        return _escalate(mode, f"Only {cit.coverage:.0%} of statements are cited",
                         confidence, session_id)

    remember_answer(session_id, cit.text)
    return RAGResponse(mode=mode, answer=cit.text, citations=cit.citations,
                       status="APPROVED", confidence=round(confidence, 2))


if __name__ == "__main__":
    print("=" * 60)
    print(" Drug Documentation Q&A  (RAG backend test console)")
    print("=" * 60)
    choice = input("Select mode:  1 = Patient / caregiver   2 = Clinician  > ").strip()
    mode: Mode = "clinician" if choice == "2" else "patient"
    print(f"\nMode: {mode.upper()}.  Type a question, '/mode' to switch, or 'exit' to quit.")

    while True:
        q = input("\nYou: ").strip()
        if q.lower() in ("", "exit", "quit"):
            break
        if q == "/mode":
            mode = "patient" if mode == "clinician" else "clinician"
            print(f"Switched to {mode.upper()} mode.")
            continue
        print("Thinking...")
        print(answer(q, mode=mode, session_id="console").model_dump_json(indent=2))

"""RAG pipeline: understand -> retrieve -> relevance gate -> generate -> cite -> decide.
Returns the RAGResponse JSON the frontend receives."""
from backend.rag import config
from backend.rag.citation import process as process_citations
from backend.rag.generator import NOT_IN_CONTEXT, generate
from backend.rag.query_understanding import remember_answer, understand
from backend.rag.relevance_gate import check
from backend.rag.retriever import retrieve
from backend.rag.schemas import Mode, RAGResponse

FALLBACK = {
    "clinician": "Insufficient reliable evidence in the uploaded labels to answer this confidently. "
                 "The query has been flagged for human review.",
    "patient": "I couldn't find enough reliable information in the uploaded drug documents to answer "
               "this safely. Your question has been flagged for review. Please ask your doctor or "
               "pharmacist.",
}


def _escalate(mode: Mode, reason: str, confidence: float, session_id: str) -> RAGResponse:
    remember_answer(session_id, FALLBACK[mode])
    return RAGResponse(mode=mode, answer=FALLBACK[mode], status="ESCALATED",
                       confidence=round(confidence, 2), reason=reason)


def answer(query: str, mode: Mode, session_id: str = "default") -> RAGResponse:
    info = understand(query, mode=mode, session_id=session_id)
    retrieved = retrieve(info.standalone_query, info.drug_names, sections=info.section_hints)

    gate = check(info, retrieved)
    if not gate.passed:
        return _escalate(mode, gate.reason, gate.top_score, session_id)

    gen = generate(info, gate.evidence)
    if NOT_IN_CONTEXT in gen.text:
        return _escalate(mode, "Answer not found in the retrieved label sections",
                         gate.top_score, session_id)

    cit = process_citations(gen.text, gate.evidence)
    confidence = (gate.top_score + cit.coverage) / 2

    if cit.invalid_refs:
        return _escalate(mode, f"Model cited non-existent sources: {cit.invalid_refs}",
                         confidence, session_id)
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

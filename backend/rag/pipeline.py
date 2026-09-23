"""Intent-routed RAG pipeline.

The orchestrator first decides whether a query needs conversation history,
label retrieval, FAERS, or an escalation. This prevents unnecessary vector
searches while keeping factual medication answers grounded in source material.
"""
from concurrent.futures import ThreadPoolExecutor
import time

from backend.rag import config
from backend.rag.api_tools import fetch_faers_adverse_events, format_faers_context
from backend.rag.citation import process as process_citations
from backend.rag.confidence import bucket_for, calibrated_score
from backend.rag.generator import NOT_IN_CONTEXT, generate
from backend.rag.intent import classify
from backend.rag.quality_metrics import estimate as estimate_metrics
from backend.rag.query_understanding import (
    cache_response, get_cached_response, get_last_cached_response, get_history,
    remember_answer, understand,
)
from backend.rag.relevance_gate import check
from backend.rag.retriever import retrieve
from backend.rag.schemas import Citation, Mode, RAGResponse, QualityMetrics
from backend.safety import injection_guard
from backend.safety.redaction import RedactionUnavailable, redact

FALLBACK = {
    "clinician": "Insufficient reliable evidence in the uploaded labels to answer this confidently. The query has been flagged for human review.",
    "patient": "I couldn't find enough reliable information in the uploaded drug documents to answer this safely. Your question has been flagged for review. Please ask your doctor or pharmacist.",
}
OUT_OF_SCOPE = {
    "clinician": "This doesn't appear to be a question about the ingested drug documentation. I can only answer questions grounded in the uploaded labels.",
    "patient": "That doesn't look like a question about a medication. I can only help with questions about the drugs in the uploaded documents.",
}
INJECTION_QUERY_MESSAGE = "This request was blocked because it contains instructions that attempt to alter the assistant's operating rules. Please submit a medication question instead."
INJECTION_CORPUS_MESSAGE = "A retrieved source was blocked because it contained an embedded instruction. The source was not passed to the answer model."

# Reuse one worker instead of constructing a ThreadPoolExecutor for every
# FAERS request. This avoids per-request thread creation while preserving the
# existing parallel FAERS + retrieval behaviour.
_FAERS_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="faers")


def _response_from_cache(cached: dict, mode: Mode, intent) -> RAGResponse:
    metrics = QualityMetrics(**cached.get("quality_metrics", {}))
    return RAGResponse(
        mode=mode, answer=cached.get("answer", ""), citations=cached.get("citations", []),
        status="APPROVED", confidence=cached.get("confidence", 1.0),
        confidence_bucket=cached.get("confidence_bucket", "high"),
        intent=intent.intent, intent_confidence=intent.confidence,
        retrieval_used=False, history_used=True, faers_used=bool(cached.get("faers_used")),
        quality_metrics=metrics,
    )


def _history_response(query: str, mode: Mode, session_id: str, intent) -> RAGResponse:
    cached = get_last_cached_response(session_id)
    if cached and cached.get("status") == "APPROVED":
        return _response_from_cache(cached, mode, intent)
    history = get_history(session_id)
    last_ai = next((m for m in reversed(history.messages) if getattr(m, "type", "") == "ai"), None)
    if last_ai:
        return RAGResponse(mode=mode, answer=last_ai.content, status="APPROVED",
                           confidence=0.7, confidence_bucket="medium", intent=intent.intent,
                           intent_confidence=intent.confidence, history_used=True,
                           quality_metrics=QualityMetrics(
                               retrieval_precision=None, answer_correctness=None,
                               citation_accuracy=None, estimated=True,
                               methodology="History-only response; no new source retrieval was performed.",
                           ))
    return RAGResponse(mode=mode, answer="There is not enough previous conversation context to answer that request yet.",
                       status="ESCALATED", reason="NO_HISTORY_CONTEXT", risk_level="none",
                       intent=intent.intent, intent_confidence=intent.confidence, history_used=True)


def _escalate(mode: Mode, reason: str, confidence: float, session_id: str,
              risk_level: str = "low", answer: str | None = None,
              intent=None, retrieval_used=False, history_used=False, faers_used=False,
              quality_metrics: QualityMetrics | None = None) -> RAGResponse:
    if reason == "PROMPT_INJECTION":
        message = INJECTION_QUERY_MESSAGE
    elif reason == "CORPUS_INJECTION":
        message = INJECTION_CORPUS_MESSAGE
    elif risk_level == "none":
        message = OUT_OF_SCOPE[mode]
    else:
        message = answer or FALLBACK[mode]
    return RAGResponse(mode=mode, answer=message, status="ESCALATED",
                       confidence=round(calibrated_score(confidence), 2),
                       confidence_bucket=bucket_for(confidence), reason=reason,
                       risk_level=risk_level, intent=getattr(intent, "intent", None),
                       intent_confidence=getattr(intent, "confidence", None),
                       retrieval_used=retrieval_used, history_used=history_used,
                       faers_used=faers_used,
                       quality_metrics=quality_metrics or QualityMetrics())


def answer(query: str, mode: Mode, session_id: str = "default", drug_hint: str | None = None) -> RAGResponse:
    started = time.perf_counter()
    intent = classify(query, session_id=session_id, drug_hint=drug_hint)
    intent_ms = (time.perf_counter() - started) * 1000

    if injection_guard.looks_like_injection(query):
        return _escalate(mode, "PROMPT_INJECTION", 0.0, session_id, risk_level="high", intent=intent)

    if intent.intent == "OFF_TOPIC":
        return _escalate(mode, "OFF_TOPIC", 0.0, session_id, risk_level="none", intent=intent)

    if intent.intent == "HISTORY_ONLY":
        return _history_response(query, mode, session_id, intent)

    cached = get_cached_response(session_id, query)
    if cached and cached.get("status") == "APPROVED":
        return _response_from_cache(cached, mode, intent)

    understand_started = time.perf_counter()
    info = understand(query, mode=mode, session_id=session_id, drug_hint=drug_hint)
    understand_ms = (time.perf_counter() - understand_started) * 1000
    if intent.needs_faers:
        # "How often" is also a dosage phrase in ordinary label queries, but
        # once intent routing selects FAERS it should not bias retrieval toward
        # Dosage and Administration. Prefer adverse-reaction sections.
        info.section_hints = [s for s in info.section_hints if s != "Dosage and Administration"]
        if "Adverse Reactions" not in info.section_hints:
            info.section_hints.append("Adverse Reactions")

    faers_future = None
    if intent.needs_faers and info.drug_names:
        faers_future = _FAERS_EXECUTOR.submit(fetch_faers_adverse_events, info.drug_names[0])

    retrieval_started = time.perf_counter()
    retrieved = retrieve(info.standalone_query, info.drug_names,
                         sections=info.section_hints, preferred_audience=mode)
    retrieval_ms = (time.perf_counter() - retrieval_started) * 1000

    if any(injection_guard.looks_like_injection(r.chunk.text) for r in retrieved):
        return _escalate(mode, "CORPUS_INJECTION", 0.0, session_id, risk_level="high",
                         intent=intent, retrieval_used=True)

    gate = check(info, retrieved)
    if not gate.passed:
        off_topic = not info.drug_names and (
            not retrieved or gate.reason.startswith("Weak evidence: no drug identified")
            or gate.reason == "No documents matched the question"
        )
        return _escalate(mode, gate.reason, gate.top_score, session_id,
                         risk_level="none" if off_topic else "low", intent=intent,
                         retrieval_used=True, history_used=intent.needs_history,
                         faers_used=faers_future is not None)

    faers_context = None
    faers_result = None
    if faers_future is not None:
        faers_result = faers_future.result()
        faers_context = format_faers_context(faers_result)

    generation_started = time.perf_counter()
    gen = generate(info, gate.evidence, faers_context=faers_context)
    generation_ms = (time.perf_counter() - generation_started) * 1000
    if NOT_IN_CONTEXT in gen.text:
        return _escalate(mode, "ANSWER_NOT_GROUNDED", gate.top_score, session_id,
                         intent=intent, retrieval_used=True, history_used=intent.needs_history,
                         faers_used=faers_result is not None)

    try:
        safe_text = redact(gen.text)
    except RedactionUnavailable as e:
        return _escalate(mode, f"REDACTION_UNAVAILABLE: {e}", 0.0, session_id,
                         risk_level="high", intent=intent, retrieval_used=True,
                         history_used=intent.needs_history, faers_used=faers_result is not None)

    faers_citation = None
    if faers_result is not None:
        faers_citation = Citation(chunk_id=f"faers:{faers_result.drug}", doc="openFDA FAERS",
                                  section="Adverse event reports", source="faers", url=faers_result.url)

    cit = process_citations(safe_text, gate.evidence, question=query, external_citation=faers_citation)
    confidence = calibrated_score((gate.top_score + cit.coverage) / 2)
    metrics = estimate_metrics(retrieved, gate.evidence, cit)

    if cit.invalid_refs:
        return _escalate(mode, f"INVALID_CITATIONS: {cit.invalid_refs}", confidence, session_id,
                         intent=intent, retrieval_used=True, history_used=intent.needs_history,
                         faers_used=faers_result is not None, quality_metrics=metrics)
    if cit.ungrounded_topics:
        return _escalate(mode, "UNGROUNDED_HIGH_RISK_TOPIC: " + ", ".join(cit.ungrounded_topics),
                         confidence, session_id, intent=intent, retrieval_used=True,
                         history_used=intent.needs_history, faers_used=faers_result is not None,
                         quality_metrics=metrics)
    if cit.unsupported_numbers:
        return _escalate(mode, "UNSUPPORTED_NUMBERS: " + " | ".join(cit.unsupported_numbers),
                         confidence, session_id, intent=intent, retrieval_used=True,
                         history_used=intent.needs_history, faers_used=faers_result is not None,
                         quality_metrics=metrics)
    if not cit.citations:
        return _escalate(mode, "NO_CITATIONS", confidence, session_id, intent=intent,
                         retrieval_used=True, history_used=intent.needs_history,
                         faers_used=faers_result is not None, quality_metrics=metrics)
    if cit.coverage < config.MIN_CITATION_COVERAGE:
        return _escalate(mode, f"LOW_CITATION_COVERAGE: {cit.coverage:.0%}", confidence, session_id,
                         intent=intent, retrieval_used=True, history_used=intent.needs_history,
                         faers_used=faers_result is not None, quality_metrics=metrics)

    total_ms = (time.perf_counter() - started) * 1000
    print(
        "[rag-timing] "
        f"intent_ms={intent_ms:.1f} understand_ms={understand_ms:.1f} "
        f"retrieval_ms={retrieval_ms:.1f} generation_ms={generation_ms:.1f} "
        f"total_ms={total_ms:.1f} faers={faers_result is not None}"
    )

    response = RAGResponse(mode=mode, answer=cit.text, citations=cit.citations,
                           status="APPROVED", confidence=round(confidence, 2),
                           confidence_bucket=bucket_for(confidence), intent=intent.intent,
                           intent_confidence=intent.confidence, retrieval_used=True,
                           history_used=intent.needs_history, faers_used=faers_result is not None,
                           quality_metrics=metrics)
    remember_answer(session_id, cit.text)
    cache_response(session_id, query, response.model_dump())
    return response


if __name__ == "__main__":
    print("DrugDoc AI intent-routed RAG console")

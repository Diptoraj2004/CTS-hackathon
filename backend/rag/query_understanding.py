"""Query understanding: drug extraction, follow-up resolution (LangChain memory),
and section hints, producing a standalone query for retrieval."""
import difflib
import re
import threading
import time

from langchain_core.chat_history import InMemoryChatMessageHistory
from langchain_core.messages import AIMessage, HumanMessage

from backend.rag.schemas import Mode, QueryInfo
from backend.rag.vector_store import get_table

# (label sections to boost, words added to the query, everyday trigger phrases)
SECTION_RULES = [
    (["Contraindications"], "contraindications",
     ["should not take", "shouldn't take", "can't take", "cannot take",
      "who can't", "avoid", "not safe", "contraindicat"]),
    (["Adverse Reactions"], "adverse reactions side effects",
     ["side effect", "adverse", "reaction"]),
    (["Dosage and Administration"], "dosage and administration",
     ["dose", "dosage", "how much", "how often", "how many"]),
    (["Boxed Warning", "Warnings and Precautions"], "boxed warning warnings",
     ["warning", "danger", "risk", "serious"]),
    (["Indications and Usage"], "indications and usage",
     ["used for", "what is it for", "indicat", "treat"]),
]

# session_id -> (last_used_timestamp, history). /query runs as a plain `def`
# route, which FastAPI dispatches to its threadpool -- concurrent requests
# really do run on different OS threads, so this dict needs a lock, not just
# careful ordering. TTL eviction keeps it from growing forever with no
# restart in sight during a multi-day demo/eval window.
SESSION_TTL_SECONDS = 2 * 60 * 60
_sessions: dict[str, tuple[float, InMemoryChatMessageHistory]] = {}
_sessions_lock = threading.Lock()

# known_drugs() used to call table.to_pandas() -- pulling every row AND
# every embedding vector into memory -- on every single query, since
# understand() calls it unconditionally. A short TTL cache turns "reload the
# whole table" into "reload it at most once every few seconds," and
# invalidate_known_drugs_cache() (called from main.py right after a
# successful ingestion) means a newly-ingested drug is visible immediately
# rather than waiting out the TTL.
_KNOWN_DRUGS_TTL_SECONDS = 30
_known_drugs_cache: tuple[float, list[str]] | None = None
_known_drugs_lock = threading.Lock()


def _prune_expired_sessions_locked() -> None:
    """Caller must already hold _sessions_lock."""
    cutoff = time.time() - SESSION_TTL_SECONDS
    for sid in [s for s, (last_used, _) in _sessions.items() if last_used < cutoff]:
        del _sessions[sid]


def get_history(session_id: str) -> InMemoryChatMessageHistory:
    now = time.time()
    with _sessions_lock:
        _prune_expired_sessions_locked()
        if session_id in _sessions:
            _, hist = _sessions[session_id]
        else:
            hist = InMemoryChatMessageHistory()
        _sessions[session_id] = (now, hist)
        return hist


def forget(session_id: str) -> bool:
    """Right-to-erasure: drop a session's conversational memory entirely.
    Returns True if a session existed and was cleared, False if there was
    nothing to clear (already gone / never existed). Called by
    DELETE /session/{session_id} in main.py."""
    with _sessions_lock:
        return _sessions.pop(session_id, None) is not None


def invalidate_known_drugs_cache() -> None:
    """Call after a successful ingestion so the new drug shows up in
    known_drugs() immediately instead of waiting out the TTL."""
    global _known_drugs_cache
    with _known_drugs_lock:
        _known_drugs_cache = None


def known_drugs() -> list[str]:
    """Drug names that actually exist in the vector store, cached briefly."""
    global _known_drugs_cache
    now = time.time()
    with _known_drugs_lock:
        if _known_drugs_cache is not None and now - _known_drugs_cache[0] < _KNOWN_DRUGS_TTL_SECONDS:
            return _known_drugs_cache[1]

    table = get_table()
    drugs = sorted(set(table.to_pandas()["drug_name"].tolist())) if table is not None else []

    with _known_drugs_lock:
        _known_drugs_cache = (now, drugs)
    return drugs


def extract_drugs(query: str, known: list[str]) -> list[str]:
    q = query.lower()
    found = [d for d in known if re.search(r"\b" + re.escape(d) + r"\b", q)]
    if not found:  # tolerate typos, e.g. "amoxicilin"
        for token in re.findall(r"[a-z][a-z\-]{4,}", q):
            match = difflib.get_close_matches(token, known, n=1, cutoff=0.8)
            if match and match[0] not in found:
                found.append(match[0])
    return found


def resolve_drug_hint(drug_hint: str, known: list[str]) -> list[str]:
    """Turn a frontend-supplied drug name (e.g. from a dropdown) into a
    canonical name from the vector store, if it matches one. Only used as
    a fallback when the query text itself didn't mention a drug name."""
    h = drug_hint.strip().lower()
    if not h:
        return []
    if h in known:
        return [h]
    match = difflib.get_close_matches(h, known, n=1, cutoff=0.6)
    return match


def previous_drugs(history: InMemoryChatMessageHistory) -> list[str]:
    for msg in reversed(history.messages):
        if isinstance(msg, HumanMessage) and msg.additional_kwargs.get("drugs"):
            return list(msg.additional_kwargs["drugs"])
    return []


def section_hints(query: str) -> tuple[list[str], list[str]]:
    """Returns (section names to boost, expansion words for the query)."""
    q = query.lower()
    sections, expansions = [], []
    for secs, expansion, keys in SECTION_RULES:
        if any(re.search(r"\b" + re.escape(k), q) for k in keys):
            sections.extend(secs)
            expansions.append(expansion)
    return sections, expansions


def understand(query: str, mode: Mode, session_id: str = "default",
               drug_hint: str | None = None) -> QueryInfo:
    """drug_hint: optional drug name from the frontend (e.g. a dropdown
    selection). Only used when the query text itself contains no drug name
    and there's no prior turn to fall back on — explicit mentions in the
    query always win, since the user may be asking about a different drug
    than the one they last selected."""
    history = get_history(session_id)
    known = known_drugs()
    drugs = extract_drugs(query, known)
    if not drugs and drug_hint:
        drugs = resolve_drug_hint(drug_hint, known)
    if not drugs:
        drugs = previous_drugs(history)  # follow-up: reuse drug from earlier turn

    parts = [d for d in drugs if d not in query.lower()]  # add drug if not literally present
    parts.append(query.strip())
    sections, expansions = section_hints(query)
    if expansions:
        parts.append("(" + "; ".join(expansions) + ")")
    standalone = " ".join(parts)

    history.add_message(HumanMessage(content=query, additional_kwargs={"drugs": drugs}))
    return QueryInfo(original_query=query, standalone_query=standalone,
                     drug_names=drugs, section_hints=sections, mode=mode)


def remember_answer(session_id: str, answer: str) -> None:
    get_history(session_id).add_message(AIMessage(content=answer))


if __name__ == "__main__":
    from backend.rag.retriever import retrieve

    conversation = [
        "What is the maximum dose of metformin?",
        "What about side effects?",
        "Who should not take amoxicilin?",
        "Who should not take this drug?",
    ]
    for q in conversation:
        info = understand(q, mode="patient", session_id="demo")
        top = retrieve(info.standalone_query, info.drug_names, top_k=1,
                       sections=info.section_hints)[0]
        print(f"\nUser:       {q}")
        print(f"Drugs:      {info.drug_names}   Sections: {info.section_hints}")
        print(f"Standalone: {info.standalone_query}")
        print(f"Top chunk:  {top.chunk.chunk_id} ({top.chunk.section})  score={top.score:.3f}")

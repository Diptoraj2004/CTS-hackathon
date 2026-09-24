"""Query understanding: drug extraction, follow-up resolution (LangChain memory),
and section hints, producing a standalone query for retrieval."""
import difflib
import json
import os
import re
import sqlite3
import threading
import time
import uuid
from typing import Any

from langchain_core.chat_history import InMemoryChatMessageHistory
from langchain_core.messages import AIMessage, HumanMessage

from backend.rag.schemas import Mode, QueryInfo
from backend.rag.drug_aliases import BRAND_TO_GENERIC, normalize_drug_name
from backend.rag.vector_store import distinct_values
from backend.app.config import SESSION_DB_PATH as CONFIG_SESSION_DB_PATH
from backend.rag import config

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

SESSION_TTL_SECONDS = 2 * 60 * 60
SESSION_DB_PATH = CONFIG_SESSION_DB_PATH
_sessions_lock = threading.Lock()


def _session_connection() -> sqlite3.Connection:
    path = os.getenv("SESSION_DB_PATH", str(SESSION_DB_PATH))

    connection = sqlite3.connect(path, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL")

    # ------------------------------------------------------------------
    # Shared chat-session schema
    # ------------------------------------------------------------------
    # Keep this schema compatible with backend.rag.user_sessions.
    # query_understanding may be the first module touching the database,
    # so it must be able to initialize/migrate the complete schema itself.
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS chat_sessions (
            session_id TEXT PRIMARY KEY,
            last_used REAL NOT NULL,
            summary TEXT,
            parent_session_id TEXT,
            summary_tokens INTEGER NOT NULL DEFAULT 0,
            rolled_over_at REAL,
            user_id TEXT,
            title TEXT,
            drug_name TEXT,
            created_at REAL,
            updated_at REAL
        )
        """
    )

    # Existing databases may have been created before the newer
    # authenticated-session fields existed.
    migrations = [
        ("summary", "TEXT"),
        ("parent_session_id", "TEXT"),
        ("summary_tokens", "INTEGER NOT NULL DEFAULT 0"),
        ("rolled_over_at", "REAL"),
        ("user_id", "TEXT"),
        ("title", "TEXT"),
        ("drug_name", "TEXT"),
        ("created_at", "REAL"),
        ("updated_at", "REAL"),
    ]

    existing_columns = {
        row["name"]
        for row in connection.execute(
            "PRAGMA table_info(chat_sessions)"
        ).fetchall()
    }

    for column, definition in migrations:
        if column not in existing_columns:
            connection.execute(
                f"ALTER TABLE chat_sessions ADD COLUMN {column} {definition}"
            )

    # Preserve legacy anonymous sessions.
    #
    # We deliberately DO NOT assign an existing session to any user.
    # This prevents an old anonymous conversation from accidentally
    # becoming visible to the first authenticated user.
    connection.execute(
        """
        UPDATE chat_sessions
        SET created_at = COALESCE(created_at, last_used),
            updated_at = COALESCE(updated_at, last_used)
        WHERE created_at IS NULL
           OR updated_at IS NULL
        """
    )

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS chat_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            additional_json TEXT NOT NULL DEFAULT '{}'
        )
        """
    )

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS response_cache (
            session_id TEXT NOT NULL,
            normalized_query TEXT NOT NULL,
            response_json TEXT NOT NULL,
            created_at REAL NOT NULL,
            PRIMARY KEY(session_id, normalized_query)
        )
        """
    )

    connection.commit()

    return connection


def estimate_tokens(text: str) -> int:
    """Conservative, dependency-free estimate for English chat text."""
    return max(1, (len(text) + 3) // 4)


def session_messages(session_id: str) -> list[dict]:
    connection = _session_connection()
    rows = connection.execute(
        "SELECT role, content, additional_json FROM chat_messages WHERE session_id = ? ORDER BY id",
        (session_id,),
    ).fetchall()
    connection.close()
    return [{"role": row["role"], "content": row["content"],
             "additional": json.loads(row["additional_json"])} for row in rows]


def session_summary(session_id: str) -> str | None:
    connection = _session_connection()
    row = connection.execute("SELECT summary FROM chat_sessions WHERE session_id = ?", (session_id,)).fetchone()
    connection.close()
    return row["summary"] if row and row["summary"] else None

def session_drug(session_id: str) -> str | None:
    """Return the persisted active medicine for a session.

    The value is session-scoped, so it survives context trimming and a fresh
    process while never becoming a global/device-level memory.
    """
    connection = _session_connection()
    row = connection.execute(
        "SELECT drug_name FROM chat_sessions WHERE session_id = ?",
        (session_id,),
    ).fetchone()
    connection.close()
    return row["drug_name"] if row and row["drug_name"] else None


def set_session_drug(session_id: str, drug_name: str | None) -> None:
    """Persist the canonical active medicine for an already-authorized session."""
    if not drug_name:
        return
    connection = _session_connection()
    now = time.time()
    connection.execute(
        """
        UPDATE chat_sessions
        SET drug_name = ?, updated_at = ?, last_used = ?
        WHERE session_id = ?
        """,
        (drug_name, now, now, session_id),
    )
    connection.commit()
    connection.close()


def context_status(session_id: str) -> dict:
    messages = session_messages(session_id)
    summary = session_summary(session_id) or ""
    estimated = estimate_tokens(summary) + sum(estimate_tokens(message["content"]) for message in messages)
    usable_limit = max(0, config.CONTEXT_WINDOW_TOKENS - config.CONTEXT_RESPONSE_RESERVE)
    warning_threshold = int(config.CONTEXT_WINDOW_TOKENS * config.CONTEXT_WARNING_RATIO)
    return {
        "session_id": session_id,
        "estimated_tokens": estimated,
        "context_limit": config.CONTEXT_WINDOW_TOKENS,
        "response_reserve": config.CONTEXT_RESPONSE_RESERVE,
        "remaining_tokens": max(0, usable_limit - estimated),
        "warning_threshold": warning_threshold,
        "near_limit": estimated >= warning_threshold,
        "message_count": len(messages),
    }


def create_rollover_session(source_session_id: str, summary: str, user_id: str | None = None) -> str:
    new_session_id = str(uuid.uuid4())
    now = time.time()
    connection = _session_connection()
    connection.execute(
        """
        INSERT INTO chat_sessions(
            session_id,
            last_used,
            summary,
            parent_session_id,
            summary_tokens,
            rolled_over_at,
            user_id,
            title,
            drug_name,
            created_at,
            updated_at
        )
        SELECT
            ?,
            ?,
            ?,
            ?,
            ?,
            ?,
            ?,
            title,
            drug_name,
            ?,
            ?
        FROM chat_sessions
        WHERE session_id = ?
        """,
        (
            new_session_id,
            now,
            summary,
            source_session_id,
            estimate_tokens(summary),
            now,
            user_id,
            now,
            now,
            source_session_id,
        ),
    )
    connection.commit()
    connection.close()
    return new_session_id

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


def get_history(session_id: str) -> InMemoryChatMessageHistory:
    now = time.time()
    with _sessions_lock:
        connection = _session_connection()
        connection.execute("DELETE FROM chat_sessions WHERE last_used < ?",
                           (now - SESSION_TTL_SECONDS,))
        connection.execute("DELETE FROM chat_messages WHERE session_id NOT IN (SELECT session_id FROM chat_sessions)")
        rows = connection.execute(
            "SELECT role, content, additional_json FROM chat_messages WHERE session_id = ? ORDER BY id",
            (session_id,),
        ).fetchall()
        hist = InMemoryChatMessageHistory()
        for row in rows:
            if row["role"] == "human":
                hist.add_message(HumanMessage(content=row["content"], additional_kwargs=json.loads(row["additional_json"])))
            else:
                hist.add_message(AIMessage(content=row["content"]))
        connection.execute("INSERT INTO chat_sessions(session_id, last_used) VALUES (?, ?) ON CONFLICT(session_id) DO UPDATE SET last_used=excluded.last_used", (session_id, now))
        connection.commit()
        connection.close()
        return hist


def _save_history(session_id: str, history: InMemoryChatMessageHistory) -> None:
    with _sessions_lock:
        connection = _session_connection()
        connection.execute("DELETE FROM chat_messages WHERE session_id = ?", (session_id,))
        for message in history.messages:
            role = "human" if isinstance(message, HumanMessage) else "ai"
            additional = getattr(message, "additional_kwargs", {})
            connection.execute(
                "INSERT INTO chat_messages(session_id, role, content, additional_json) VALUES (?, ?, ?, ?)",
                (session_id, role, message.content, json.dumps(additional)),
            )
        connection.execute("INSERT INTO chat_sessions(session_id, last_used) VALUES (?, ?) ON CONFLICT(session_id) DO UPDATE SET last_used=excluded.last_used", (session_id, time.time()))
        connection.commit()
        connection.close()


def forget(session_id: str) -> bool:
    """Right-to-erasure: drop a session's conversational memory entirely.
    Returns True if a session existed and was cleared, False if there was
    nothing to clear (already gone / never existed). Called by
    DELETE /session/{session_id} in main.py."""
    with _sessions_lock:
        connection = _session_connection()
        existed = connection.execute("SELECT 1 FROM chat_sessions WHERE session_id = ?", (session_id,)).fetchone() is not None
        connection.execute("DELETE FROM chat_messages WHERE session_id = ?", (session_id,))
        connection.execute("DELETE FROM response_cache WHERE session_id = ?", (session_id,))
        connection.execute("DELETE FROM chat_sessions WHERE session_id = ?", (session_id,))
        connection.commit()
        connection.close()
        return existed


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

    drugs = distinct_values("drug_name")

    with _known_drugs_lock:
        _known_drugs_cache = (now, drugs)
    return drugs


def extract_drugs(query: str, known: list[str]) -> list[str]:
    q = query.lower()
    # `known` holds whatever case the ingested label used (e.g. "AC FAST"),
    # not necessarily lowercase -- matching a lowercased query against
    # un-lowercased known names silently never matches real all-caps/mixed-
    # case drug names. Build a lowercase lookup once instead.
    known_lower = {d.lower(): d for d in known}
    found = [known_lower[dl] for dl in known_lower
             if re.search(r"\b" + re.escape(dl) + r"\b", q)]
    for alias, canonical in BRAND_TO_GENERIC.items():
        if not re.search(r"\b" + re.escape(alias) + r"\b", q):
            continue
        if canonical in known_lower and known_lower[canonical] not in found:
            found.append(known_lower[canonical])
    if not found:  # tolerate typos, e.g. "amoxicilin"
        for token in re.findall(r"[a-z][a-z\-]{4,}", q):
            match = difflib.get_close_matches(normalize_drug_name(token), list(known_lower), n=1, cutoff=0.8)
            if match and known_lower[match[0]] not in found:
                found.append(known_lower[match[0]])
    return found


def resolve_drug_hint(drug_hint: str, known: list[str]) -> list[str]:
    """Turn a frontend-supplied drug name (e.g. from a dropdown) into a
    canonical name from the vector store, if it matches one. Only used as
    a fallback when the query text itself didn't mention a drug name."""
    h = normalize_drug_name(drug_hint)
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
    summary = session_summary(session_id)
    known = known_drugs()
    drugs = extract_drugs(query, known)

    # Explicit query text wins. Otherwise resolve the selected medicine, then
    # the persisted session medicine, then legacy message history. This order
    # prevents a stale local/device value from becoming the source of truth.
    if not drugs and drug_hint:
        drugs = resolve_drug_hint(drug_hint, known)
    if not drugs:
        persisted_drug = session_drug(session_id)
        if persisted_drug and persisted_drug in known:
            drugs = [persisted_drug]
    if not drugs:
        drugs = previous_drugs(history)

    if drugs:
        # Keep the active medicine durable beyond any in-memory/history trim.
        # The API has already authenticated and ownership-checked this session.
        set_session_drug(session_id, drugs[0])

    parts = [d for d in drugs if d not in query.lower()]  # add drug if not literally present
    parts.append(query.strip())
    sections, expansions = section_hints(query)
    if expansions:
        parts.append("(" + "; ".join(expansions) + ")")
    standalone = " ".join(parts)

    history.add_message(HumanMessage(content=query, additional_kwargs={"drugs": drugs}))
    _save_history(session_id, history)
    return QueryInfo(original_query=query, standalone_query=standalone,
                     drug_names=drugs, section_hints=sections, mode=mode,
                     conversation_summary=summary)


def _normalize_query(query: str) -> str:
    return re.sub(r"\s+", " ", query.strip().lower())


def get_cached_response(session_id: str, query: str) -> dict[str, Any] | None:
    connection = _session_connection()
    row = connection.execute(
        "SELECT response_json FROM response_cache WHERE session_id = ? AND normalized_query = ?",
        (session_id, _normalize_query(query)),
    ).fetchone()
    connection.close()
    if not row:
        return None
    try:
        return json.loads(row["response_json"])
    except (TypeError, json.JSONDecodeError):
        return None


def cache_response(session_id: str, query: str, response: dict[str, Any]) -> None:
    connection = _session_connection()
    connection.execute(
        "INSERT INTO response_cache(session_id, normalized_query, response_json, created_at) VALUES (?, ?, ?, ?) "
        "ON CONFLICT(session_id, normalized_query) DO UPDATE SET response_json=excluded.response_json, created_at=excluded.created_at",
        (session_id, _normalize_query(query), json.dumps(response), time.time()),
    )
    connection.commit()
    connection.close()


def get_last_cached_response(session_id: str) -> dict[str, Any] | None:
    connection = _session_connection()
    row = connection.execute(
        "SELECT response_json FROM response_cache WHERE session_id = ? ORDER BY created_at DESC LIMIT 1",
        (session_id,),
    ).fetchone()
    connection.close()
    if not row:
        return None
    try:
        return json.loads(row["response_json"])
    except (TypeError, json.JSONDecodeError):
        return None


def remember_answer(session_id: str, answer: str) -> None:
    history = get_history(session_id)
    history.add_message(AIMessage(content=answer))
    _save_history(session_id, history)


def find_repeat_answer(session_id: str, query: str) -> str | None:
    """Mentor-requested check: does this question actually need a fresh
    vectorDB retrieval, or is chat memory enough? Scoped conservatively to
    a near-exact repeat of the immediately preceding question (a UI
    double-submit, a "sorry, say that again?") rather than a general
    "can memory answer this" classifier -- a real classifier needs its own
    LLM call, which would ADD latency, not cut it. This is a cheap,
    reliable win for the narrow case it covers; it does not try to detect
    every question chat history could in principle answer.

    Caller is responsible for not treating a fallback/escalation message as
    a cached APPROVED answer -- this function only returns raw text, it
    doesn't know which FALLBACK strings pipeline.py uses.
    """
    history = get_history(session_id)
    messages = history.messages
    if len(messages) < 2:
        return None
    prev_ai, prev_human = messages[-1], messages[-2]
    if not (isinstance(prev_ai, AIMessage) and isinstance(prev_human, HumanMessage)):
        return None
    normalize = lambda s: re.sub(r"\s+", " ", s.strip().lower())
    if normalize(prev_human.content) != normalize(query):
        return None
    return prev_ai.content


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

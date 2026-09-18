"""Query understanding: drug extraction, follow-up resolution (LangChain memory),
and section hints, producing a standalone query for retrieval."""
import difflib
import re

from langchain_core.chat_history import InMemoryChatMessageHistory
from langchain_core.messages import AIMessage, HumanMessage

from backend.rag.schemas import Mode, QueryInfo
from backend.rag.vector_store import get_collection

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

# Words that refer back to something said earlier ("it", "this drug", "what about ...")
_FOLLOWUP = re.compile(r"\b(it|its|this|that|these|those|they|them|same|"
                       r"what about|how about|and for|also)\b")

_sessions: dict[str, InMemoryChatMessageHistory] = {}


def get_history(session_id: str) -> InMemoryChatMessageHistory:
    return _sessions.setdefault(session_id, InMemoryChatMessageHistory())


def known_drugs() -> list[str]:
    """Drug names that actually exist in the vector store."""
    metas = get_collection().get(include=["metadatas"])["metadatas"]
    return sorted({m["drug_name"] for m in metas if m.get("drug_name")})


def extract_drugs(query: str, known: list[str]) -> list[str]:
    q = query.lower()
    found = [d for d in known if re.search(r"\b" + re.escape(d) + r"\b", q)]
    if not found:  # tolerate typos, e.g. "amoxicilin"
        for token in re.findall(r"[a-z][a-z\-]{4,}", q):
            match = difflib.get_close_matches(token, known, n=1, cutoff=0.8)
            if match and match[0] not in found:
                found.append(match[0])
    return found


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


def is_followup(query: str, sections: list[str]) -> bool:
    """A question continues the previous drug only if it refers back or asks a drug topic."""
    return bool(sections) or bool(_FOLLOWUP.search(query.lower()))


def understand(query: str, mode: Mode, session_id: str = "default") -> QueryInfo:
    history = get_history(session_id)
    sections, expansions = section_hints(query)

    drugs = extract_drugs(query, known_drugs())
    if not drugs and is_followup(query, sections):
        drugs = previous_drugs(history)  # follow-up: reuse drug from earlier turn

    parts = [d for d in drugs if d not in query.lower()]  # add drug if not literally present
    parts.append(query.strip())
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
        "What is the weather in Kolkata?",
    ]
    for q in conversation:
        info = understand(q, mode="patient", session_id="demo")
        top = retrieve(info.standalone_query, info.drug_names, top_k=1,
                       sections=info.section_hints)[0]
        print(f"\nUser:       {q}")
        print(f"Drugs:      {info.drug_names}   Sections: {info.section_hints}")
        print(f"Standalone: {info.standalone_query}")
        print(f"Top chunk:  {top.chunk.chunk_id} ({top.chunk.section})  score={top.score:.3f}")

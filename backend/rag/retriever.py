"""Retrieval: query -> top-K chunks from LanceDB, filtered by drug,
re-ranked with a small bonus for chunks from the sections the user asked about."""
import re
from typing import Optional

from backend.rag import config
from backend.rag.schemas import Chunk, RetrievedChunk
from backend.rag.vector_store import get_table, hybrid_search

SECTION_BOOST = 0.15  # ranking bonus only; the stored score stays the raw similarity
_STOPWORDS = {"and", "or", "of", "the", "for", "to", "in", "with", "use"}


def _tokens(text: str) -> set[str]:
    """Meaningful words, lowercased, numbers/symbols removed, simple plural -> singular.
    '6 ADVERSE REACTIONS' -> {'adverse', 'reaction'}"""
    words = re.findall(r"[a-z]+", text.lower())
    return {w[:-1] if w.endswith("s") and len(w) > 4 else w
            for w in words if w not in _STOPWORDS}


def section_matches(section: str, wanted: list[str]) -> bool:
    """True if the chunk's section shares a meaningful word with any wanted section.
    Works for 'Adverse Reactions', '6 ADVERSE REACTIONS', 'WARNING: LACTIC ACIDOSIS'..."""
    sec = _tokens(section)
    return any(_tokens(w) & sec for w in wanted)


def retrieve(query: str, drug_names: Optional[list[str]] = None,
             top_k: int = config.TOP_K,
             sections: Optional[list[str]] = None,
             preferred_audience: str | None = None) -> list[RetrievedChunk]:
    table = get_table()
    if table is None or table.count_rows() == 0:
        return []

    n = min(max(top_k * 3, 10), table.count_rows()) if sections else top_k
    rows = hybrid_search(query, drug_names=drug_names, limit=n)

    results = []
    for row in rows:
        score = row.get("_retrieval_score", 0.0)
        fields = {k: v for k, v in row.items()
              if k not in ("vector", "_distance", "_score", "_hybrid_score",
                       "_retrieval_score", "_fts_rank")}
        preferred_bonus = 0.04 if preferred_audience and fields.get("audience") == preferred_audience \
            and fields.get("source") == "brand_site" else 0.0
        results.append(RetrievedChunk(chunk=Chunk(**fields), score=round(score + preferred_bonus, 3)))

    if sections:
        results.sort(key=lambda r: r.score + (SECTION_BOOST if section_matches(r.chunk.section, sections) else 0),
                     reverse=True)
    elif preferred_audience:
        results.sort(key=lambda r: r.score, reverse=True)
    return results[:top_k]


if __name__ == "__main__":
    print("Section matching with real-label naming styles:")
    cases = [
        ("6 ADVERSE REACTIONS", ["Adverse Reactions"], True),
        ("2 DOSAGE & ADMINISTRATION", ["Dosage and Administration"], True),
        ("WARNING: LACTIC ACIDOSIS", ["Boxed Warning", "Warnings and Precautions"], True),
        ("5 WARNINGS AND PRECAUTIONS", ["Boxed Warning", "Warnings and Precautions"], True),
        ("4 CONTRAINDICATIONS", ["Indications and Usage"], False),
        ("1 INDICATIONS AND USAGE", ["Contraindications"], False),
    ]
    for section, wanted, expected in cases:
        got = section_matches(section, wanted)
        print(f"  {'PASS' if got == expected else 'FAIL'}  {section:<28} vs {wanted} -> {got}")

    tests = [
        ("What is the maximum daily dose of metformin?", ["metformin"], ["Dosage and Administration"]),
        ("What are the side effects?", ["metformin"], ["Adverse Reactions"]),
        ("What is the dose for severe infections?", None, None),
    ]
    for q, drugs, secs in tests:
        print(f"\nQ: {q}   (filter: {drugs}, sections: {secs})")
        for r in retrieve(q, drugs, top_k=3, sections=secs):
            print(f"  {r.score:.3f}  {r.chunk.chunk_id:<11} {r.chunk.section}")

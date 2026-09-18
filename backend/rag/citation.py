"""Citation engine: map [n] markers to document/section/page, drop fake citations,
renumber in order of appearance, and measure how many factual sentences are cited."""
import re

from pydantic import BaseModel, Field

from backend.rag.schemas import Citation, RetrievedChunk

_MARKER = re.compile(r"\[(\d+(?:\s*,\s*\d+)*)\]")      # [1]  [1,3]  [1, 3]
_SKIP_PHRASES = ("talk to your doctor", "talk to your pharmacist", "doctor or pharmacist")


class CitationResult(BaseModel):
    text: str                                   # answer with renumbered markers
    citations: list[Citation] = Field(default_factory=list)
    invalid_refs: list[int] = Field(default_factory=list)   # cited numbers with no excerpt
    coverage: float = 0.0                       # share of factual sentences with a citation
    uncited: list[str] = Field(default_factory=list)


def _factual_sentences(text: str) -> list[str]:
    """Sentences that state facts (skips headings, very short lines, safety disclaimer)."""
    sentences = []
    for line in text.splitlines():
        line = line.strip().lstrip("-*• ").strip()
        if not line or line.endswith(":"):
            continue
        for s in re.split(r"(?<=[.!?])\s+", line):
            s = s.strip()
            if len(s.split()) < 4 or any(p in s.lower() for p in _SKIP_PHRASES):
                continue
            sentences.append(s)
    return sentences


def process(answer: str, evidence: list[RetrievedChunk]) -> CitationResult:
    old_to_new: dict[int, int] = {}
    citations: list[Citation] = []
    invalid: set[int] = set()

    def renumber(match: re.Match) -> str:
        kept = []
        for part in match.group(1).split(","):
            n = int(part)
            if not 1 <= n <= len(evidence):
                invalid.add(n)
                continue
            if n not in old_to_new:
                old_to_new[n] = len(old_to_new) + 1
                c = evidence[n - 1].chunk
                citations.append(Citation(chunk_id=c.chunk_id, doc=c.source_file,
                                          section=c.section, page=c.page))
            kept.append(old_to_new[n])
        return "".join(f"[{k}]" for k in sorted(set(kept)))

    new_text = _MARKER.sub(renumber, answer)
    new_text = re.sub(r"[ \t]+([.,;:])", r"\1", new_text)      # tidy space left by removed markers

    facts = _factual_sentences(new_text)
    uncited = [s for s in facts if not _MARKER.search(s)]
    coverage = 1.0 if not facts else round((len(facts) - len(uncited)) / len(facts), 2)

    return CitationResult(text=new_text, citations=citations, invalid_refs=sorted(invalid),
                          coverage=coverage, uncited=uncited)


if __name__ == "__main__":
    from backend.rag.sample_chunks import SAMPLE_CHUNKS

    by_id = {c.chunk_id: c for c in SAMPLE_CHUNKS}
    evidence = [RetrievedChunk(chunk=by_id[i], score=0.6)
                for i in ("met-ind-1", "met-dose-1", "met-ci-1")]

    good = ("The maximum recommended dose is 2550 mg per day [2]. "
            "Start with 500 mg twice a day with meals [2]. "
            "It must not be used in severe renal impairment [3].")
    bad = ("The maximum recommended dose is 2550 mg per day [2][7]. "
           "It is also safe during pregnancy for most patients. "
           "It is used for type 2 diabetes [1].")

    for name, answer in (("GOOD answer", good), ("BAD answer", bad)):
        r = process(answer, evidence)
        print(f"\n===== {name} =====")
        print(r.text)
        print(f"citations:    {[(c.chunk_id, c.section, c.page) for c in r.citations]}")
        print(f"invalid refs: {r.invalid_refs}")
        print(f"coverage:     {r.coverage}")
        print(f"uncited:      {r.uncited}")

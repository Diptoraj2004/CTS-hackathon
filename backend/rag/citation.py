"""Citation engine: map [n] markers to document/section/page, drop fake citations,
auto-cite sentences clearly supported by one excerpt, verify numbers and high-risk topics
against the cited sources, renumber in order of appearance, and measure coverage."""
import re

from pydantic import BaseModel, Field

from backend.rag.schemas import Citation, RetrievedChunk

_MARKER = re.compile(r"\[(\d+(?:\s*,\s*\d+)*)\]")      # [1]  [1,3]  [1, 3]
_TRAILING = re.compile(r"([.!?])[ \t]*((?:\[\d+(?:\s*,\s*\d+)*\][ \t]*)+)")  # "day. [1]"
_NUMBER = re.compile(r"\d+(?:\.\d+)?")
_SKIP_PHRASES = ("talk to your doctor", "talk to your pharmacist", "doctor or pharmacist")
_STOPWORDS = {"with", "that", "this", "from", "have", "should", "would", "could", "their",
              "there", "which", "about", "what", "when", "your", "into", "also", "been",
              "were", "they", "them", "does", "than", "then", "only", "more", "most",
              "some", "such", "other", "according", "excerpts", "excerpt"}
MIN_OVERLAP = 0.6   # share of a sentence's key words that must appear in one excerpt

# High-risk topics: if the question or answer mentions one, the cited excerpts must too.
# Each topic lists patient words AND label words, so "kidney" is satisfied by "renal".
HIGH_RISK_TOPICS = {
    "pregnancy": [r"pregnan", r"fetus", r"fetal"],
    "breastfeeding": [r"breast.?feed", r"lactat", r"nursing", r"breast milk"],
    "children": [r"child", r"kids?\b", r"pediatric", r"paediatric", r"infant", r"adolescent",
                 r"newborn"],
    "older adults": [r"elderly", r"geriatric", r"older adult", r"65 or older", r"aged? 65"],
    "kidney": [r"kidney", r"renal", r"egfr", r"creatinine"],
    "liver": [r"liver", r"hepatic"],
    "alcohol": [r"alcohol", r"drinking"],
    "heart": [r"heart\b", r"cardiac", r"cardiovascular"],
    "surgery": [r"surgery", r"surgical"],
    "contrast imaging": [r"contrast", r"radiolog"],
}


class CitationResult(BaseModel):
    text: str                                   # answer with renumbered markers
    citations: list[Citation] = Field(default_factory=list)
    invalid_refs: list[int] = Field(default_factory=list)   # cited numbers with no excerpt
    coverage: float = 0.0                       # share of factual sentences with a citation
    uncited: list[str] = Field(default_factory=list)
    auto_cited: list[str] = Field(default_factory=list)     # sentences the engine cited itself
    unsupported_numbers: list[str] = Field(default_factory=list)  # numbers not in cited source
    ungrounded_topics: list[str] = Field(default_factory=list)    # high-risk topics not in sources


def _normalize(text: str) -> str:
    """Move citations written after the full stop to before it: 'day. [1]' -> 'day [1].'"""
    return _TRAILING.sub(lambda m: " " + m.group(2).strip() + m.group(1), text)


def _numbers(text: str) -> set[str]:
    text = _MARKER.sub("", text)
    text = re.sub(r"(?<=\d),(?=\d{3}\b)", "", text)          # 2,550 -> 2550
    return set(_NUMBER.findall(text))


def _stems(text: str) -> set[str]:
    return {w[:6] for w in re.findall(r"[a-z]+", text.lower())
            if len(w) >= 4 and w not in _STOPWORDS}


def _topics(text: str) -> set[str]:
    t = text.lower()
    return {name for name, patterns in HIGH_RISK_TOPICS.items()
            if any(re.search(r"\b" + p, t) for p in patterns)}


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


def process(answer: str, evidence: list[RetrievedChunk], question: str = "") -> CitationResult:
    old_to_new: dict[int, int] = {}
    citations: list[Citation] = []
    invalid: set[int] = set()

    def cite(n: int) -> int:
        """Register excerpt n (1-based) as a citation; return its new number."""
        if n not in old_to_new:
            old_to_new[n] = len(old_to_new) + 1
            c = evidence[n - 1].chunk
            citations.append(Citation(chunk_id=c.chunk_id, doc=c.source_file,
                                      section=c.section, page=c.page))
        return old_to_new[n]

    def renumber(match: re.Match) -> str:
        kept = []
        for part in match.group(1).split(","):
            n = int(part)
            if not 1 <= n <= len(evidence):
                invalid.add(n)
                continue
            kept.append(cite(n))
        return "".join(f"[{k}]" for k in sorted(set(kept)))

    text = _MARKER.sub(renumber, _normalize(answer))
    text = re.sub(r"[ \t]+([.,;:])", r"\1", text)      # tidy space left by removed markers

    # 1) Auto-cite uncited sentences that are clearly supported by one excerpt
    auto = []
    for s in _factual_sentences(text):
        if _MARKER.search(s):
            continue
        stems, nums = _stems(s), _numbers(s)
        if len(stems) < 3:
            continue
        best, best_ratio = None, 0.0
        for idx, r in enumerate(evidence, start=1):
            if not nums <= _numbers(r.chunk.text):      # every number must be in the excerpt
                continue
            ratio = len(stems & _stems(r.chunk.text)) / len(stems)
            if ratio > best_ratio:
                best, best_ratio = idx, ratio
        if best is not None and best_ratio >= MIN_OVERLAP:
            k = cite(best)
            fixed = s[:-1] + f" [{k}]" + s[-1] if s[-1] in ".!?" else f"{s} [{k}]"
            text = text.replace(s, fixed, 1)
            auto.append(s)

    # 2) Every number in a cited sentence must appear in its cited excerpt(s)
    new_to_chunk = {new: evidence[old - 1].chunk for old, new in old_to_new.items()}
    unsupported = []
    for s in _factual_sentences(text):
        refs = [int(x) for group in _MARKER.findall(s) for x in group.split(",")]
        if not refs:
            continue
        source = " ".join(new_to_chunk[k].text for k in refs if k in new_to_chunk)
        missing = _numbers(s) - _numbers(source)
        if missing:
            unsupported.append(f"{s}  (not in source: {', '.join(sorted(missing))})")

    # 3) High-risk topics in the question or answer must be covered by the cited excerpts
    cited_text = " ".join(c.text for c in new_to_chunk.values())
    ungrounded = sorted(_topics(question + " " + text) - _topics(cited_text))

    # 4) Coverage
    facts = _factual_sentences(text)
    uncited = [s for s in facts if not _MARKER.search(s)]
    coverage = 1.0 if not facts else round((len(facts) - len(uncited)) / len(facts), 2)

    return CitationResult(text=text, citations=citations, invalid_refs=sorted(invalid),
                          coverage=coverage, uncited=uncited, auto_cited=auto,
                          unsupported_numbers=unsupported, ungrounded_topics=ungrounded)


if __name__ == "__main__":
    from backend.rag.sample_chunks import SAMPLE_CHUNKS

    by_id = {c.chunk_id: c for c in SAMPLE_CHUNKS}
    evidence = [RetrievedChunk(chunk=by_id[i], score=0.6)
                for i in ("met-ind-1", "met-dose-1", "met-ci-1")]

    tests = {
        "GOOD answer": ("What is the dose?",
                        "The maximum recommended dose is 2550 mg per day [2]. "
                        "Start with 500 mg twice a day with meals [2]. "
                        "It must not be used in severe renal impairment [3]."),
        "BAD answer": ("What is the dose?",
                       "The maximum recommended dose is 2550 mg per day [2][7]. "
                       "It is also safe during pregnancy for most patients. "
                       "It is used for type 2 diabetes [1]."),
        "TRAILING-citation answer": ("What is the dose?",
                                     "The maximum recommended dose is 2550 mg per day. [2]\n\n"
                                     "* Take metformin with your meals. [2]\n"
                                     "* Do not use it with severe kidney problems. [3]\n\n"
                                     "Please talk to your doctor or pharmacist before making any change."),
        "SUPPORTED-but-uncited answer": ("Can people with kidney problems take metformin?",
                                         "No, metformin must not be used in severe renal impairment [3]. "
                                         "Severe renal impairment (eGFR below 30 mL/min/1.73 m2) "
                                         "is a contraindication for metformin."),
        "WRONG-NUMBER answer": ("What is the maximum dose?",
                                "The maximum recommended dose is 3000 mg per day [2]."),
        "PREGNANCY hallucination": ("Is metformin safe during pregnancy?",
                                    "No, metformin is contraindicated in pregnant women [3]."),
        "CHILDREN (label says pediatric)": ("Can children take metformin?",
                                            "Yes, pediatric patients 10 years and older can use it [1]."),
    }
    for name, (question, answer) in tests.items():
        r = process(answer, evidence, question=question)
        print(f"\n===== {name} =====")
        print(r.text)
        print(f"citations:   {[(c.chunk_id, c.page) for c in r.citations]}")
        print(f"invalid:     {r.invalid_refs}   coverage: {r.coverage}")
        print(f"uncited:     {r.uncited}")
        print(f"auto_cited:  {r.auto_cited}")
        print(f"bad numbers: {r.unsupported_numbers}")
        print(f"ungrounded:  {r.ungrounded_topics}")

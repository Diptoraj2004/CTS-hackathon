"""Data contracts for the RAG part: retrieval -> gate -> generation -> citations."""
from typing import Literal, Optional

from pydantic import BaseModel, Field

Mode = Literal["clinician", "patient"]


class Chunk(BaseModel):
    """One piece of a drug label, produced by the ingestion pipeline."""
    chunk_id: str
    text: str
    drug_name: str
    section: str                    # e.g. "Dosage and Administration"
    source_file: str                # e.g. "metformin_label.pdf"
    page: Optional[int] = None
    version: Optional[str] = None
    # Extended metadata from the ingestion pipeline (Suman) — all optional so
    # existing code that only reads the fields above keeps working unchanged.
    document_id: Optional[str] = None
    set_id: Optional[str] = None
    active_ingredient: Optional[str] = None
    subsection: Optional[str] = None
    source_type: Optional[str] = None       # "pdf" / "xml" / "ocr"
    source_identifier: Optional[str] = None
    effective_date: Optional[str] = None    # for detecting superseded label versions
    ingestion_timestamp: Optional[str] = None
    extraction_method: Optional[str] = None


class RetrievedChunk(BaseModel):
    """A chunk returned by retrieval, with its raw similarity score (0 to 1)."""
    chunk: Chunk
    score: float


class QueryInfo(BaseModel):
    """Output of query understanding."""
    original_query: str
    standalone_query: str           # follow-ups rewritten into a full question
    drug_names: list[str] = Field(default_factory=list)
    section_hints: list[str] = Field(default_factory=list)  # e.g. ["Adverse Reactions"]
    mode: Mode


class Citation(BaseModel):
    chunk_id: str
    doc: str
    section: str
    page: Optional[int] = None


class RAGResponse(BaseModel):
    """Final JSON sent to the frontend."""
    mode: Mode
    answer: str
    citations: list[Citation] = Field(default_factory=list)
    status: Literal["APPROVED", "ESCALATED"]
    confidence: float = 0.0
    reason: Optional[str] = None    # why it was escalated, if it was


if __name__ == "__main__":
    demo = RAGResponse(
        mode="patient",
        answer="Take metformin with meals to reduce stomach upset [1].",
        citations=[Citation(chunk_id="met-dose-1", doc="metformin_label.pdf",
                            section="Dosage and Administration", page=4)],
        status="APPROVED",
        confidence=0.82,
    )
    print(demo.model_dump_json(indent=2))

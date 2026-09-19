"""Request/response contracts for the API layer. Reuses backend.rag.schemas
where it already fits instead of redefining Mode/Citation a second time."""
from typing import Optional

from pydantic import BaseModel, Field

from backend.rag.schemas import Mode, RAGResponse


class QueryRequest(BaseModel):
    session_id: str
    query: str = Field(..., min_length=2)
    mode: Mode
    drug_name: Optional[str] = None  # e.g. a frontend dropdown selection; only
    # used as a fallback when the query text itself names no drug — see
    # query_understanding.understand()'s drug_hint parameter.


class DocumentUploadRequest(BaseModel):
    file_path: str


class ChatbotResponse(RAGResponse):
    """RAGResponse plus a request_id, so the frontend can poll a pending review."""
    request_id: Optional[str] = None

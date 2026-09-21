# DEPRECATED for the live app: the shared pipeline (main.py -> export_to_rag_store
# -> backend.rag.vector_store) does not use this file. It's Suman's original
# standalone CLI path (backend/app/ingestion/pipeline.py). Two vector-store
# implementations still exist side by side -- unifying them is still open,
# not done in this pass (real risk of breaking whichever path isn't tested
# right now; needs care, not a rushed merge).
"""Compatibility adapter for the canonical RAG vector store.

New ingestion code should use ``backend.rag.vector_store`` directly. This
adapter keeps the older standalone pipeline API working while ensuring there
is only one LanceDB schema and writer implementation.
"""
from typing import Any

from backend.app.models import EmbeddingRecord
from backend.rag.schemas import Chunk as RagChunk
from backend.rag.vector_store import add_chunks, get_table


def _to_rag_chunk(record: EmbeddingRecord) -> RagChunk:
    chunk = record.chunk
    return RagChunk(
        chunk_id=chunk.chunk_id,
        text=chunk.text,
        drug_name=chunk.drug_name,
        section=chunk.section,
        source_file=chunk.source_file,
        page=chunk.page_number,
        version=chunk.label_version,
        document_id=chunk.document_id,
        set_id=chunk.set_id,
        active_ingredient=chunk.active_ingredient,
        subsection=chunk.subsection,
        source_type=chunk.source_type,
        source_identifier=chunk.source_identifier,
        effective_date=chunk.effective_date,
        ingestion_timestamp=chunk.ingestion_timestamp,
        extraction_method=chunk.extraction_method,
        original_filename=chunk.original_filename,
    )


class VectorStore:
    """Backward-compatible facade over the shared RAG LanceDB store."""

    def __init__(self, uri: str | None = None, table_name: str = "drug_chunks"):
        self.uri = uri
        self.table_name = table_name
        self.table = None
        self.load()

    def add(self, records: list[EmbeddingRecord]):
        if records:
            add_chunks([_to_rag_chunk(record) for record in records])
        self.load()

    def load(self):
        self.table = get_table()

    def similarity_search(self, query_embedding: list[float], k: int = 5) -> list[dict[str, Any]]:
        if self.table is None:
            return []
        results = self.table.search(query_embedding).limit(k).to_list()
        output = []
        for result in results:
            item = dict(result)
            item.pop("vector", None)
            item["similarity_score"] = item.pop("_distance", 0.0)
            output.append(item)
        return output

class VectorStore:
    def __init__(self, uri: str = "data/vector_db", table_name: str = "drug_chunks"):
        self.uri = uri
        self.table_name = table_name
        
        os.makedirs(os.path.dirname(self.uri), exist_ok=True)
        self.db = lancedb.connect(self.uri)
        self.table = None
        
    def add(self, records: List[EmbeddingRecord]):
        if not records:
            return
            
        data = []
        for r in records:
            chunk = r.chunk
            row = {
                "vector": r.embedding,
                "chunk_id": chunk.chunk_id,
                "document_id": chunk.document_id,
                "set_id": chunk.set_id,
                "drug_name": chunk.drug_name,
                "active_ingredient": chunk.active_ingredient,
                "section": chunk.section,
                "subsection": chunk.subsection,
                "page_number": chunk.page_number,
                "source_file": chunk.source_file,
                "source_type": chunk.source_type,
                "source_identifier": chunk.source_identifier,
                "text": chunk.text,
                "label_version": chunk.label_version,
                "effective_date": chunk.effective_date,
                "ingestion_timestamp": chunk.ingestion_timestamp,
                "extraction_method": chunk.extraction_method
            }
            data.append(row)
            
        try:
            self.table = self.db.open_table(self.table_name)
            self.table.add(data)
        except Exception:
            self.table = self.db.create_table(self.table_name, data=data)
            
    def load(self):
        try:
            self.table = self.db.open_table(self.table_name)
        except Exception:
            self.table = None
            
    def similarity_search(self, query_embedding: List[float], k: int = 5) -> List[Dict[str, Any]]:
        if not self.table:
            return []
            
        results = self.table.search(query_embedding).limit(k).to_list()
        
        final_results = []
        for r in results:
            dist = r.get("_distance", 0.0)
            res = r.copy()
            if "vector" in res:
                del res["vector"]
            res["similarity_score"] = dist
            final_results.append(res)
            
        return final_results

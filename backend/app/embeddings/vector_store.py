# DEPRECATED for the live app: the shared pipeline (main.py -> export_to_rag_store
# -> backend.rag.vector_store) does not use this file. It's Suman's original
# standalone CLI path (backend/app/ingestion/pipeline.py). Two vector-store
# implementations still exist side by side -- unifying them is still open,
# not done in this pass (real risk of breaking whichever path isn't tested
# right now; needs care, not a rushed merge).
import lancedb
import os
import pyarrow as pa
from typing import List, Dict, Any
from backend.app.models import EmbeddingRecord

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

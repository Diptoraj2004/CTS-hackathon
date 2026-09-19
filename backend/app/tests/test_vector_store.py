import pytest
import os
import shutil
from backend.app.embeddings.vector_store import VectorStore
from backend.app.models import Chunk, EmbeddingRecord

def test_vector_store(tmp_path):
    db_path = os.path.join(tmp_path, "vector_db")
    store = VectorStore(uri=db_path, table_name="test_table")
    
    chunk1 = Chunk(
        chunk_id="c1", document_id="d1", drug_name="DrugX", section="s1",
        page_number=1, source_file="sf", source_type="pdf", text="This is text.",
        ingestion_timestamp="t", extraction_method="pdf_text"
    )
    
    chunk2 = Chunk(
        chunk_id="c2", document_id="d1", drug_name="DrugX", section="s1",
        page_number=1, source_file="sf", source_type="pdf", text="This is text version 2.",
        label_version="v2",
        ingestion_timestamp="t", extraction_method="pdf_text"
    )
    
    record1 = EmbeddingRecord(chunk=chunk1, embedding=[0.1, 0.2, 0.3])
    record2 = EmbeddingRecord(chunk=chunk2, embedding=[0.2, 0.3, 0.4])
    
    store.add([record1, record2])
    assert store.table is not None
    assert len(store.table.search().to_list()) == 2
    
    # Reload database
    store2 = VectorStore(uri=db_path, table_name="test_table")
    store2.load()
    assert store2.table is not None
    
    # search
    results = store2.similarity_search([0.1, 0.2, 0.3], k=1)
    assert len(results) == 1
    assert results[0]['chunk_id'] == "c1"
    assert results[0]['similarity_score'] >= 0.0 # LanceDB returns actual distance/score
    
    # ensure multiple versions exist
    all_docs = store2.table.search().to_list()
    assert len(all_docs) == 2

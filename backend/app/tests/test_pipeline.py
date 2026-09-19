import pytest
import os
from backend.app.ingestion.pipeline import ingest_document
from backend.app.embeddings.vector_store import VectorStore
from backend.app.embeddings.embedder import Embedder

def test_pipeline_end_to_end(test_pdf_path, test_xml_path, monkeypatch, tmp_path):
    test_db_dir = os.path.join(tmp_path, "vector_db")
    
    import app.embeddings.vector_store as vs_module
    import app.metadata.versioning as vm_module
    
    original_vs_init = vs_module.VectorStore.__init__
    def mock_vs_init(self, uri=None, table_name="drug_chunks"):
        original_vs_init(self, uri=test_db_dir, table_name=table_name)
        
    monkeypatch.setattr(vs_module.VectorStore, "__init__", mock_vs_init)
    
    original_vm_init = vm_module.VersionManager.__init__
    def mock_vm_init(self, storage_dir=None):
        original_vm_init(self, storage_dir=test_db_dir)
        
    monkeypatch.setattr(vm_module.VersionManager, "__init__", mock_vm_init)

    # Ingest PDF
    doc, chunks, records, store = ingest_document(test_pdf_path, doc_id="test_doc_id", drug_name="Test Drug")
    
    assert doc is not None
    assert len(chunks) > 0
    assert store.table is not None
    assert len(store.table.search().to_list()) == len(chunks)
    assert doc.metadata.source_type == "pdf"
    
    # Ingest XML
    doc_x, chunks_x, records_x, store_x = ingest_document(test_xml_path, doc_id="xml_id", drug_name="XML Drug")
    
    assert doc_x is not None
    assert len(chunks_x) > 0
    # Store should accumulate
    assert len(store_x.table.search().to_list()) == len(chunks) + len(chunks_x)
    assert doc_x.metadata.source_type == "xml"

    # Test similarity search
    embedder = Embedder.get_instance()
    query_emb = embedder.embed_chunks(chunks_x)[0].embedding
    
    results = store_x.similarity_search(query_emb, k=1)
    assert len(results) == 1
    assert "similarity_score" in results[0]

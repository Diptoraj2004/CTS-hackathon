from backend.app.ingestion.parser import ParserFactory
from backend.app.ingestion.chunker import Chunker
from backend.app.metadata.versioning import VersionManager
from backend.app.embeddings.embedder import Embedder
from backend.app.embeddings.vector_store import VectorStore
import os
import sys

def ingest_document(path: str, doc_id: str = None, drug_name: str = None):
    print("Parsing...")
    doc = ParserFactory.parse_document(file_path=path, doc_id=doc_id, drug_name=drug_name)
    
    print("Version tagging...")
    version_mgr = VersionManager()
    doc = version_mgr.tag_document(doc)
    
    print("Chunking...")
    chunker = Chunker()
    chunks = chunker.chunk_document(doc)
    
    if not chunks:
        print("No chunks produced.")
        return None
        
    print("Embedding...")
    embedder = Embedder.get_instance()
    records = embedder.embed_chunks(chunks)
    
    print("Saving to LanceDB...")
    dimension = embedder.get_embedding_dimension()
    store = VectorStore()
    store.add(records)
    
    # Calculate stats
    pages_count = len(doc.pages)
    sections_count = len(doc.sections)
    chunks_count = len(chunks)
    extraction_methods = list(set([c.extraction_method for c in chunks]))
    
    print("\n--- Ingestion Complete ---")
    print(f"Document ID: {doc.metadata.document_id}")
    print(f"Drug: {doc.metadata.drug_name}")
    print(f"Source: {doc.metadata.source_file}")
    print(f"Source Type: {doc.metadata.source_type}")
    print(f"Label Version: {doc.metadata.label_version}")
    print(f"Effective Date: {doc.metadata.effective_date}")
    print(f"Extraction Method: {', '.join(extraction_methods)}")
    print(f"Pages: {pages_count}")
    print(f"Sections: {sections_count}")
    print(f"Chunks: {chunks_count}")
    print(f"Embedding Model: {embedder.model_name}")
    print(f"Embedding Dimension: {dimension}")
    print(f"LanceDB Table: {store.table_name}")
    print(f"Vector database:\nLanceDB")
    
    return doc, chunks, records, store

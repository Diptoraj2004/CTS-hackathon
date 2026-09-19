"""Bridges the ingestion pipeline (parsing, OCR, chunking, embedding — all
Suman's tested modules, untouched) to the single shared LanceDB store that
retriever.py actually searches. Split into parse/scan/store so the API layer
can reject a document before anything from it is written anywhere.
"""
from backend.app.embeddings.embedder import Embedder
from backend.app.ingestion.chunker import Chunker
from backend.app.ingestion.parser import ParserFactory
from backend.app.metadata.versioning import VersionManager
from backend.rag.schemas import Chunk as RagChunk
from backend.rag.vector_store import add_chunks


def _to_rag_chunk(chunk) -> RagChunk:
    """Suman's Chunk -> the canonical Chunk the retriever/gates/citations use.
    Field names differ in a couple of places (page_number -> page,
    label_version -> version); everything else carries straight through."""
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
    )


def parse_and_chunk(path: str, doc_id: str = None, drug_name: str = None) -> list[RagChunk]:
    """Parse + version-tag + chunk only — nothing is written to the store yet,
    so a caller can run a safety check (injection scan, size limit, etc.) on
    the result before deciding whether to store it."""
    doc = ParserFactory.parse_document(file_path=path, doc_id=doc_id, drug_name=drug_name)
    doc = VersionManager().tag_document(doc)
    chunks = Chunker().chunk_document(doc)
    return [_to_rag_chunk(c) for c in chunks]


def store_chunks(chunks: list[RagChunk]) -> int:
    """Embed and write already-approved chunks. Returns the count written."""
    if not chunks:
        return 0
    add_chunks(chunks)
    return len(chunks)


def ingest_and_export(path: str, doc_id: str = None, drug_name: str = None) -> int:
    """Convenience wrapper for scripts/manual runs — no safety check in
    between. The API endpoint uses parse_and_chunk() + store_chunks()
    separately instead, so it can scan before storing."""
    return store_chunks(parse_and_chunk(path, doc_id, drug_name))


if __name__ == "__main__":
    import sys
    n = ingest_and_export(sys.argv[1])
    print(f"Wrote {n} chunks to the shared LanceDB store.")

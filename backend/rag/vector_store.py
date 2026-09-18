"""Chroma vector store: embed chunks and store them with their metadata."""
from functools import lru_cache

import chromadb
from sentence_transformers import SentenceTransformer

from backend.rag import config
from backend.rag.schemas import Chunk


@lru_cache(maxsize=1)
def get_embedder() -> SentenceTransformer:
    """Load the embedding model once and reuse it."""
    return SentenceTransformer(config.EMBED_MODEL)


def embed(texts: list[str]) -> list[list[float]]:
    """Normalized embeddings, so similarity = 1 - (squared L2 distance / 2)."""
    return get_embedder().encode(texts, normalize_embeddings=True).tolist()


@lru_cache(maxsize=1)
def get_collection():
    client = chromadb.PersistentClient(path=str(config.CHROMA_DIR))
    # We always supply our own embeddings, so no built-in embedding function.
    return client.get_or_create_collection(
        name=config.COLLECTION_NAME, embedding_function=None
    )


def chunk_metadata(chunk: Chunk) -> dict:
    """Everything except text and id; Chroma does not accept None values."""
    return chunk.model_dump(exclude={"text", "chunk_id"}, exclude_none=True)


def add_chunks(chunks: list[Chunk]) -> None:
    """Insert or update chunks (safe to run more than once)."""
    get_collection().upsert(
        ids=[c.chunk_id for c in chunks],
        documents=[c.text for c in chunks],
        embeddings=embed([c.text for c in chunks]),
        metadatas=[chunk_metadata(c) for c in chunks],
    )


if __name__ == "__main__":
    from backend.rag.sample_chunks import SAMPLE_CHUNKS

    add_chunks(SAMPLE_CHUNKS)
    col = get_collection()
    print(f"Stored {col.count()} chunks in collection '{config.COLLECTION_NAME}'")
    print(f"Location: {config.CHROMA_DIR}")

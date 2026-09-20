"""LanceDB vector store: embed chunks and store them with their metadata.
Ported from Soumya's Chroma version — same public functions (get_embedder,
embed, add_chunks) so nothing calling this module needs to change."""
from functools import lru_cache

import lancedb
from sentence_transformers import SentenceTransformer

from backend.rag import config
from backend.rag.schemas import Chunk


@lru_cache(maxsize=1)
def get_embedder() -> SentenceTransformer:
    """Load the embedding model once and reuse it."""
    return SentenceTransformer(config.EMBED_MODEL)


def embed(texts: list[str]) -> list[list[float]]:
    """Normalized embeddings, so cosine distance behaves as expected."""
    return get_embedder().encode(texts, normalize_embeddings=True).tolist()


@lru_cache(maxsize=1)
def get_db():
    return lancedb.connect(str(config.LANCEDB_DIR))


def get_table():
    """None if nothing's been ingested yet — callers should handle that."""
    db = get_db()
    if config.COLLECTION_NAME in db.list_tables().tables:
        return db.open_table(config.COLLECTION_NAME)
    return None


def _row(chunk: Chunk, vector: list[float]) -> dict:
    row = chunk.model_dump(exclude_none=True)
    row["vector"] = vector
    return row


def add_chunks(chunks: list[Chunk]) -> None:
    """Insert or update chunks (safe to run more than once — re-adding a
    chunk_id that already exists replaces it rather than duplicating it)."""
    vectors = embed([c.text for c in chunks])
    rows = [_row(c, v) for c, v in zip(chunks, vectors)]

    db = get_db()
    if config.COLLECTION_NAME in db.list_tables().tables:
        table = db.open_table(config.COLLECTION_NAME)
        ids = ", ".join(f"'{c.chunk_id}'" for c in chunks)
        table.delete(f"chunk_id IN ({ids})")
        table.add(rows)
    else:
        db.create_table(config.COLLECTION_NAME, data=rows)


def delete_by_source_file(source_file: str) -> int:
    """Removes every chunk belonging to one uploaded document. Returns the
    row count before deletion (LanceDB's delete() doesn't report a count),
    so the caller can tell whether anything actually matched."""
    table = get_table()
    if table is None:
        return 0
    escaped = source_file.replace("'", "''")
    before = table.count_rows(f"source_file = '{escaped}'")
    if before:
        table.delete(f"source_file = '{escaped}'")
    return before


if __name__ == "__main__":
    from backend.rag.sample_chunks import SAMPLE_CHUNKS

    add_chunks(SAMPLE_CHUNKS)
    table = get_table()
    print(f"Stored {table.count_rows()} chunks in table '{config.COLLECTION_NAME}'")
    print(f"Location: {config.LANCEDB_DIR}")

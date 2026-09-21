"""LanceDB vector store: embed chunks and store them with their metadata.
Ported from Soumya's Chroma version — same public functions (get_embedder,
embed, add_chunks) so nothing calling this module needs to change."""
import threading
from functools import lru_cache

import lancedb
from sentence_transformers import SentenceTransformer

from backend.rag import config
from backend.rag.schemas import Chunk

# Guards the check-then-create-or-add sequence in add_chunks(). Two
# concurrent ingestions can both see "table doesn't exist yet" and both call
# create_table() -- the second call either errors or clobbers the first,
# depending on LanceDB version. One lock around the whole read-decide-write
# sequence removes the race entirely (bounded, low-contention: ingestion
# already runs on a small thread pool, not one thread per request).
_table_lock = threading.Lock()


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
    if not chunks:
        return
    vectors = embed([c.text for c in chunks])
    rows = [_row(c, v) for c, v in zip(chunks, vectors)]

    with _table_lock:
        db = get_db()
        if config.COLLECTION_NAME in db.list_tables().tables:
            table = db.open_table(config.COLLECTION_NAME)
            if "original_filename" not in table.schema.names:
                table.add_columns({"original_filename": "CAST(NULL AS string)"})
            if hasattr(table, "merge_insert"):
                # True atomic upsert-by-key where the installed LanceDB
                # supports it -- no window where a chunk_id is briefly
                # missing between a delete and the following add (which is
                # what a concurrent /query's retrieve() could otherwise
                # observe).
                (table.merge_insert("chunk_id")
                      .when_matched_update_all()
                      .when_not_matched_insert_all()
                      .execute(rows))
            else:
                # Older LanceDB without merge_insert: same delete-then-add
                # as before. Still correct (still holds _table_lock so it
                # can't race with another ingestion), just not atomic
                # against a concurrent reader for the brief window between
                # the two calls -- disclosed limitation, not silently hidden.
                ids = ", ".join(f"'{c.chunk_id}'" for c in chunks)
                table.delete(f"chunk_id IN ({ids})")
                table.add(rows)
        else:
            db.create_table(config.COLLECTION_NAME, data=rows)


def delete_by_source_file(source_file: str) -> int:
    """Removes every chunk belonging to one uploaded document. Returns the
    row count before deletion (LanceDB's delete() doesn't report a count),
    so the caller can tell whether anything actually matched."""
    with _table_lock:
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

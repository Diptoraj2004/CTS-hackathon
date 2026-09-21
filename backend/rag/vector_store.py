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


def distinct_values(column: str) -> list[str]:
    """Read one metadata column without materializing the embedding table."""
    table = get_table()
    if table is None or column not in table.schema.names:
        return []

    try:
        rows = table.to_arrow(columns=[column]).column(column).to_pylist()
    except TypeError:
        # Older LanceDB versions may not accept the columns keyword, but can
        # still project columns through the table's scanner.
        # For newer versions (e.g. 0.38+), use search().select().
        rows = table.search().select([column]).to_arrow().column(column).to_pylist()
    return sorted({str(value) for value in rows if value not in (None, "")})


def document_records() -> list[dict]:
    """Return one metadata record per source file, without loading vectors."""
    table = get_table()
    if table is None:
        return []
    columns = ["source_file", "original_filename", "drug_name", "source_type",
               "version", "effective_date", "ingestion_timestamp"]
    columns = [column for column in columns if column in table.schema.names]
    if "source_file" not in columns:
        return []
    try:
        rows = table.to_arrow(columns=columns).to_pylist()
    except TypeError:
        rows = table.search().select(columns).to_arrow().to_pylist()

    documents = {}
    for row in rows:
        source_file = row.get("source_file")
        if source_file and source_file not in documents:
            documents[source_file] = {
                "id": source_file,
                "filename": row.get("original_filename") or source_file,
                "drug_name": row.get("drug_name") or "unknown",
                "source_type": row.get("source_type") or "unknown",
                "version": row.get("version") or "unknown",
                "effective_date": row.get("effective_date") or "unknown",
                "ingestion_timestamp": row.get("ingestion_timestamp"),
            }
    return sorted(documents.values(), key=lambda item: item["filename"].lower())


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

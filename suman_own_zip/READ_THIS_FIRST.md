# What changed from your zip, and one thing you depend on

- All internal imports rewritten from `from app.X` to `from backend.app.X`
  (the rest of the repo runs from the repo root, not from inside `backend/`).
- `app/ingestion/pdf_parser.py`: `import fitz` -> `import pymupdf as fitz`
  (the old import name is deprecated; alias kept so nothing else changes).
- `app/ingestion/export_to_rag_store.py` split into `parse_and_chunk()` and
  `store_chunks()` so the API layer can run a safety check in between —
  your own `ingest_document()`/`VectorStore` are untouched.

**Dependency, not included here:** `backend/rag/schemas.py` (Soumya's file)
was extended with your metadata fields (document_id, set_id, active_ingredient,
etc.) so your Chunk data survives the conversion. Pull `main` for that file
before running the bridge script — it's not in this zip since it isn't yours
to carry.

Your own tests pass as-is (7/7, ran them for real) after the import fix.
One pre-existing thing not from this pass: `datetime.utcnow()` in
pdf_parser.py/xml_parser.py throws a deprecation warning on newer Python —
harmless for the demo, worth a two-minute fix (`datetime.now(datetime.UTC)`)
whenever you have a spare minute.

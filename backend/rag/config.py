"""Settings for the RAG part. Change values here, not inside the code."""
from pathlib import Path

RAG_DIR = Path(__file__).resolve().parent

# Vector store (LanceDB, embedded, stored on disk — switched from Chroma per
# the mentor's suggestion: zero-ops, no external hosting, natively multimodal)
LANCEDB_DIR = RAG_DIR / "lancedb_data"
COLLECTION_NAME = "drug_labels"

# Embedding model: must be the SAME model the ingestion teammate uses
EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

# Retrieval
TOP_K = 4

# Relevance gate: minimum cosine similarity to count as evidence (tune later)
MIN_RELEVANCE = 0.45


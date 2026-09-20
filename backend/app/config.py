import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", 500))
    CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", 50))
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
    # Bare "tesseract" resolves via PATH on Linux/Colab (after `apt-get install
    # tesseract-ocr`). The old hardcoded Windows path silently broke OCR on
    # every non-Windows host — run_ocr() swallows the resulting error and
    # returns empty text, which then reports as a normal empty page rather
    # than a failure. Set TESSERACT_CMD explicitly if your binary isn't on PATH.
    TESSERACT_CMD = os.getenv("TESSERACT_CMD", "tesseract")
    POOR_EXTRACTION_THRESHOLD = int(os.getenv("POOR_EXTRACTION_THRESHOLD", 50)) # min meaningful chars
    PRINTABLE_RATIO_THRESHOLD = float(os.getenv("PRINTABLE_RATIO_THRESHOLD", 0.7))

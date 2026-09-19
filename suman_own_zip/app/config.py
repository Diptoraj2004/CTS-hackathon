import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", 500))
    CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", 50))
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
    TESSERACT_CMD = os.getenv("TESSERACT_CMD", r"C:\Program Files\Tesseract-OCR\tesseract.exe")
    POOR_EXTRACTION_THRESHOLD = int(os.getenv("POOR_EXTRACTION_THRESHOLD", 50)) # min meaningful chars
    PRINTABLE_RATIO_THRESHOLD = float(os.getenv("PRINTABLE_RATIO_THRESHOLD", 0.7))

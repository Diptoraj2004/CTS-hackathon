import uuid
import re
from typing import List
from backend.app.models import ParsedDocument, Chunk, Section
from backend.app.config import Config

class Chunker:
    def __init__(self, chunk_size: int = None, chunk_overlap: int = None):
        self.chunk_size = chunk_size or Config.CHUNK_SIZE
        self.chunk_overlap = chunk_overlap or Config.CHUNK_OVERLAP

    def _split_text(self, text: str) -> List[str]:
        normalized = re.sub(r"\s+", " ", text).strip()
        if not normalized:
            return []

        sentences = re.split(r"(?<=[.!?])\s+", normalized)
        sentences = [sentence.strip() for sentence in sentences if sentence.strip()]
        chunks: List[str] = []
        current: List[str] = []

        def flush() -> None:
            if current:
                chunks.append(" ".join(current).strip())

        for sentence in sentences:
            if len(sentence) > self.chunk_size:
                flush()
                current.clear()
                step = max(1, self.chunk_size - self.chunk_overlap)
                chunks.extend(
                    sentence[start:start + self.chunk_size].strip()
                    for start in range(0, len(sentence), step)
                )
                continue

            candidate = " ".join(current + [sentence])
            if current and len(candidate) > self.chunk_size:
                previous = current[:]
                flush()
                current.clear()
                overlap_length = 0
                for prior_sentence in reversed(previous):
                    if overlap_length + len(prior_sentence) + 1 > self.chunk_overlap:
                        break
                    current.insert(0, prior_sentence)
                    overlap_length += len(prior_sentence) + 1

            current.append(sentence)

        flush()
        return chunks

    def chunk_document(self, doc: ParsedDocument) -> List[Chunk]:
        chunks = []
        meta = doc.metadata
        
        if doc.sections:
            for section in doc.sections:
                text_chunks = self._split_text(section.text)
                for i, text in enumerate(text_chunks):
                    if not text: continue
                    chunks.append(Chunk(
                        chunk_id=str(uuid.uuid4()),
                        document_id=meta.document_id,
                        set_id=meta.set_id,
                        drug_name=meta.drug_name,
                        active_ingredient=meta.active_ingredient,
                        section=section.title,
                        subsection=None,
                        page_number=1,
                        source_file=meta.source_file,
                        source_type=meta.source_type,
                        source_identifier=meta.source_identifier,
                        text=text,
                        label_version=meta.label_version,
                        effective_date=meta.effective_date,
                        ingestion_timestamp=meta.ingestion_timestamp,
                        extraction_method="xml_text",
                        original_filename=meta.original_filename
                    ))
        else:
            for page in doc.pages:
                text_chunks = self._split_text(page.text)
                for i, text in enumerate(text_chunks):
                    if not text: continue
                    chunks.append(Chunk(
                        chunk_id=str(uuid.uuid4()),
                        document_id=meta.document_id,
                        set_id=meta.set_id,
                        drug_name=meta.drug_name,
                        active_ingredient=meta.active_ingredient,
                        section=page.section,
                        subsection=page.subsection,
                        page_number=page.page_number,
                        source_file=meta.source_file,
                        source_type=meta.source_type,
                        source_identifier=meta.source_identifier,
                        text=text,
                        label_version=meta.label_version,
                        effective_date=meta.effective_date,
                        ingestion_timestamp=meta.ingestion_timestamp,
                        extraction_method=page.extraction_method,
                        original_filename=meta.original_filename
                    ))
                    
        return chunks

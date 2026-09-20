import uuid
from typing import List
from backend.app.models import ParsedDocument, Chunk, Section
from backend.app.config import Config

class Chunker:
    def __init__(self, chunk_size: int = None, chunk_overlap: int = None):
        self.chunk_size = chunk_size or Config.CHUNK_SIZE
        self.chunk_overlap = chunk_overlap or Config.CHUNK_OVERLAP

    def _split_text(self, text: str) -> List[str]:
        paragraphs = text.split('\n\n')
        chunks = []
        current_chunk = ""
        
        for p in paragraphs:
            if len(current_chunk) + len(p) < self.chunk_size:
                current_chunk += p + "\n\n"
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                if len(p) > self.chunk_size:
                    for i in range(0, len(p), self.chunk_size - self.chunk_overlap):
                        chunks.append(p[i:i + self.chunk_size].strip())
                    current_chunk = ""
                else:
                    current_chunk = p + "\n\n"
        
        if current_chunk:
            chunks.append(current_chunk.strip())
            
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
                        section="General",
                        subsection=None,
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

import os
from backend.app.models import ParsedDocument
from backend.app.ingestion.pdf_parser import PDFParser
from backend.app.ingestion.xml_parser import XMLParser

class ParserFactory:
    @staticmethod
    def parse_document(file_path: str, doc_id: str = None, drug_name: str = None, use_ocr: bool = True) -> ParsedDocument:
        ext = os.path.splitext(file_path)[1].lower()
        if ext == '.pdf':
            if not doc_id: doc_id = f"pdf_{os.path.basename(file_path)}"
            if not drug_name: drug_name = "Unknown Drug"
            parser = PDFParser(use_ocr=use_ocr)
            return parser.parse(file_path, doc_id, drug_name)
        elif ext == '.xml':
            parser = XMLParser()
            return parser.parse(file_path, doc_id, drug_name)
        else:
            raise ValueError(f"Unsupported file extension: {ext}")

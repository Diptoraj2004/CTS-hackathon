"""Fetch and parse patient-facing brand-source pages and PDFs."""
import datetime
import os
import tempfile

import requests
from bs4 import BeautifulSoup

from backend.app.ingestion.pdf_parser import PDFParser
from backend.app.models import DocumentMetadata, Page, PageBlock, ParsedDocument

MAX_DOWNLOAD_BYTES = 50 * 1024 * 1024
_HEADERS = {"User-Agent": "DrugDocAI/1.0 medical-document-ingestion"}


class BrandSourceParser:
    def parse(self, url: str, doc_id: str | None, drug_name: str) -> ParsedDocument:
        response = requests.get(url, headers=_HEADERS, timeout=20, stream=True)
        response.raise_for_status()
        content_type = response.headers.get("content-type", "").lower()
        suffix = os.path.splitext(url.split("?", 1)[0])[1].lower()
        if "pdf" in content_type or suffix == ".pdf":
            return self._parse_pdf(response, url, doc_id, drug_name)
        if "html" not in content_type and content_type:
            raise ValueError(f"Unsupported brand-source content type: {content_type}")
        content = b"".join(response.iter_content(chunk_size=1024 * 1024))
        if len(content) > MAX_DOWNLOAD_BYTES:
            raise ValueError("Brand-source HTML exceeds the permitted size limit.")
        return self._parse_html(content, url, doc_id, drug_name)

    @staticmethod
    def _parse_html(content: bytes, url: str, doc_id: str | None,
                    drug_name: str) -> ParsedDocument:
        soup = BeautifulSoup(content, "html.parser")
        for element in soup(["script", "style", "noscript", "nav", "footer"]):
            element.decompose()
        root = soup.find("main") or soup.find("article") or soup.body or soup
        blocks = []
        section = "Brand Information"
        for element in root.find_all(["h1", "h2", "h3", "p", "li"], recursive=True):
            text = " ".join(element.get_text(" ", strip=True).split())
            if not text:
                continue
            if element.name in {"h1", "h2", "h3"}:
                section = text[:200]
                continue
            kind = "list" if element.name == "li" else "text"
            blocks.append(PageBlock(kind=kind, text=text))
        text = "\n".join(block.text for block in blocks)
        return _document(url, doc_id, drug_name, text, blocks, section)

    @staticmethod
    def _parse_pdf(response, url: str, doc_id: str | None,
                   drug_name: str) -> ParsedDocument:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as handle:
            size = 0
            for part in response.iter_content(chunk_size=1024 * 1024):
                size += len(part)
                if size > MAX_DOWNLOAD_BYTES:
                    raise ValueError("Brand-source PDF exceeds the permitted size limit.")
                handle.write(part)
            temporary_path = handle.name
        try:
            document = PDFParser(use_ocr=True).parse(
                temporary_path, doc_id or f"brand_pdf_{abs(hash(url))}", drug_name
            )
            document.metadata.source = "brand_site"
            document.metadata.audience = "patient"
            document.metadata.source_url = url
            document.metadata.source_file = url
            document.metadata.original_filename = url.rsplit("/", 1)[-1] or "brand_source.pdf"
            return document
        finally:
            os.unlink(temporary_path)


def _document(url: str, doc_id: str | None, drug_name: str, text: str,
              blocks: list[PageBlock], section: str) -> ParsedDocument:
    return ParsedDocument(
        metadata=DocumentMetadata(
            document_id=doc_id or f"brand_html_{abs(hash(url))}",
            drug_name=drug_name or "Unknown Drug",
            ingestion_timestamp=datetime.datetime.utcnow().isoformat(),
            source_file=url,
            source_type="html",
            source_identifier=url,
            original_filename=url,
            source="brand_site",
            audience="patient",
            source_url=url,
        ),
        pages=[Page(page_number=1, text=text, extraction_method="html",
                    section=section, blocks=blocks)],
        sections=[],
    )

"""PDF text extraction.

Each yielded record carries page number metadata so chunks can cite
the original page. Uses pypdf which handles most PDFs but isn't perfect
for complex layouts (multi-column papers, scanned PDFs, etc.).
"""

from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader


@dataclass
class PageText:
    """Raw text from one PDF page."""

    page_number: int   # 1-based
    text: str


def extract_pdf(path: Path) -> tuple[str, list[PageText]]:
    """Read a PDF and return (document_title, list of pages).

    The title is taken from PDF metadata if available; otherwise the filename.
    """
    reader = PdfReader(str(path))

    title = None
    if reader.metadata and reader.metadata.title:
        title = reader.metadata.title.strip()
    if not title:
        title = path.stem

    pages: list[PageText] = []
    for i, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""
        text = text.strip()
        if text:
            pages.append(PageText(page_number=i, text=text))

    return title, pages

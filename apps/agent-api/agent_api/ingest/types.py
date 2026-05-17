"""Shared types for the ingestion pipeline.

A Chunk is a self-contained piece of a document that will be embedded
and stored in Qdrant. Metadata travels with the chunk so retrieval can
surface citations, filter by source, etc.
"""

from dataclasses import dataclass, field


@dataclass
class Chunk:
    """A single chunk of text with metadata."""

    text: str                       # The chunk content as it will appear to the user
    embeddable_text: str            # Text passed to the embedder (may have header prepended)
    source_file: str                # Path to the source file
    document_title: str             # Title of the document
    section_path: list[str]         # Heading hierarchy, e.g., ["Pods", "Init Containers"]
    chunk_index: int                # 0-based position within the source file
    content_type: str               # "pdf" or "markdown"
    page_number: int | None = None  # For PDFs, the page this chunk came from
    extra: dict = field(default_factory=dict)  # Anything else worth storing


@dataclass
class IngestResult:
    """Summary of an ingestion run."""

    source_file: str
    chunks_created: int
    chunks_stored: int
    errors: list[str] = field(default_factory=list)

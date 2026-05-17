"""Ingestion pipeline orchestrator.

Given a path (file or directory), dispatches to the right extractor and
chunker based on file extension, then upserts to Qdrant.
"""

from pathlib import Path

from agent_api.ingest.chunkers.markdown import chunk_markdown
from agent_api.ingest.extractors.markdown import extract_markdown
from agent_api.ingest.extractors.pdf import extract_pdf
from agent_api.ingest.chunkers.fixed import chunk_text
from agent_api.ingest.qdrant_store import ensure_collection, upsert_chunks
from agent_api.ingest.types import Chunk, IngestResult


SUPPORTED_EXTENSIONS = {".md", ".pdf"}


def ingest_file(path: Path, collection: str) -> IngestResult:
    """Ingest a single file into the given Qdrant collection."""
    ext = path.suffix.lower()
    chunks: list[Chunk] = []

    if ext == ".pdf":
        title, pages = extract_pdf(path)
        index = 0
        for page in pages:
            page_chunks = chunk_text(
                text=page.text,
                source_file=str(path),
                document_title=title,
                content_type="pdf",
                base_chunk_index=index,
                page_number=page.page_number,
            )
            chunks.extend(page_chunks)
            index += len(page_chunks)
    elif ext == ".md":
        title, sections = extract_markdown(path)
        chunks = chunk_markdown(
            sections=sections,
            source_file=str(path),
            document_title=title,
        )
    else:
        return IngestResult(
            source_file=str(path),
            chunks_created=0,
            chunks_stored=0,
            errors=[f"Unsupported extension: {ext}"],
        )

    ensure_collection(collection)
    stored = upsert_chunks(collection, chunks)

    return IngestResult(
        source_file=str(path),
        chunks_created=len(chunks),
        chunks_stored=stored,
    )


def ingest_path(path: Path, collection: str) -> list[IngestResult]:
    """Ingest a file or every supported file in a directory."""
    results: list[IngestResult] = []
    if path.is_file():
        results.append(ingest_file(path, collection))
    elif path.is_dir():
        files = sorted(
            f for f in path.rglob("*")
            if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS
        )
        for f in files:
            results.append(ingest_file(f, collection))
    else:
        results.append(IngestResult(
            source_file=str(path),
            chunks_created=0,
            chunks_stored=0,
            errors=[f"Path not found: {path}"],
        ))
    return results

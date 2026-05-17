"""Async wrapper for the synchronous ingestion pipeline.

FastAPI handlers are async. The ingestion code is sync (uses blocking
httpx.Client calls to Ollama). Running sync code directly in an async
handler blocks the event loop, freezing every other in-flight request.

We use asyncio.to_thread() to run ingestion in a worker thread. The
event loop stays free during the embed calls.
"""

import asyncio
from pathlib import Path

from agent_api.ingest.pipeline import ingest_file
from agent_api.ingest.types import IngestResult


async def ingest_file_async(path: Path, collection: str) -> IngestResult:
    """Run ingest_file in a worker thread, awaitable."""
    return await asyncio.to_thread(ingest_file, path, collection)

"""Qdrant-backed chunk store.

Creates collections, upserts chunks, and exposes a simple search method
used by the CLI search command. The Day 11 retriever will share this
client when wiring RAG into the chat endpoint.
"""

import uuid
from dataclasses import dataclass
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from agent_api.ingest.embedder import embed, embedding_dim
from agent_api.ingest.types import Chunk
from agent_api.settings import settings


@dataclass
class SearchResult:
    """Returned by search() - a retrieved chunk with its similarity score."""

    score: float
    text: str
    source_file: str
    document_title: str
    section_path: list[str]
    page_number: int | None
    chunk_index: int
    content_type: str


def _client() -> QdrantClient:
    host = settings.qdrant_host
    if host == "qdrant":
        host = "localhost"
    return QdrantClient(host=host, port=settings.qdrant_port)


def ensure_collection(name: str) -> None:
    """Create the collection if it doesn't exist."""
    c = _client()
    existing = {col.name for col in c.get_collections().collections}
    if name in existing:
        return

    dim = embedding_dim()
    c.create_collection(
        collection_name=name,
        vectors_config=qmodels.VectorParams(
            size=dim,
            distance=qmodels.Distance.COSINE,
        ),
    )


def upsert_chunks(collection: str, chunks: list[Chunk]) -> int:
    """Embed and store chunks in the collection. Returns count stored."""
    if not chunks:
        return 0

    c = _client()
    points: list[qmodels.PointStruct] = []

    for chunk in chunks:
        vector = embed(chunk.embeddable_text)
        payload: dict[str, Any] = {
            "text": chunk.text,
            "source_file": chunk.source_file,
            "document_title": chunk.document_title,
            "section_path": chunk.section_path,
            "chunk_index": chunk.chunk_index,
            "content_type": chunk.content_type,
        }
        if chunk.page_number is not None:
            payload["page_number"] = chunk.page_number
        if chunk.extra:
            payload["extra"] = chunk.extra

        points.append(
            qmodels.PointStruct(
                id=str(uuid.uuid4()),
                vector=vector,
                payload=payload,
            )
        )

    BATCH = 64
    for i in range(0, len(points), BATCH):
        c.upsert(collection_name=collection, points=points[i:i + BATCH])

    return len(points)


def search(collection: str, query: str, top_k: int = 5) -> list[SearchResult]:
    """Search the collection for chunks similar to the query.

    Uses query_points() which is the current API (search() was removed
    in qdrant-client 1.12+).
    """
    c = _client()
    query_vector = embed(query)
    response = c.query_points(
        collection_name=collection,
        query=query_vector,
        limit=top_k,
        with_payload=True,
    )
    points = response.points  # query_points returns a QueryResponse wrapper
    return [
        SearchResult(
            score=p.score,
            text=(p.payload or {}).get("text", ""),
            source_file=(p.payload or {}).get("source_file", ""),
            document_title=(p.payload or {}).get("document_title", ""),
            section_path=(p.payload or {}).get("section_path", []),
            page_number=(p.payload or {}).get("page_number"),
            chunk_index=(p.payload or {}).get("chunk_index", 0),
            content_type=(p.payload or {}).get("content_type", ""),
        )
        for p in points
    ]


def collection_info(name: str) -> dict | None:
    """Return basic info about a collection, or None if it doesn't exist."""
    c = _client()
    existing = {col.name for col in c.get_collections().collections}
    if name not in existing:
        return None
    info = c.get_collection(collection_name=name)
    return {
        "name": name,
        "points_count": info.points_count,
        "vectors_count": info.vectors_count,
        "status": info.status.value if hasattr(info.status, "value") else str(info.status),
    }


def drop_collection(name: str) -> bool:
    """Delete a collection. Returns True if it was deleted, False if absent."""
    c = _client()
    existing = {col.name for col in c.get_collections().collections}
    if name not in existing:
        return False
    c.delete_collection(collection_name=name)
    return True

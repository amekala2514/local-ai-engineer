"""Retriever - fetches relevant chunks for a query.

Wraps the Qdrant search from Day 10. Returns a RetrievalContext that
carries both the chunks and metadata about how/why they were retrieved.

The 'reason' field exists so Phase B's auto-detect logic can record
why it decided to retrieve (or not). Today the reason is always
'collection_attached'.
"""

from dataclasses import dataclass, field
from typing import Any

from agent_api.ingest.qdrant_store import SearchResult, search


@dataclass
class RetrievalContext:
    """Bundle of retrieved chunks plus metadata about the retrieval."""

    chunks: list[SearchResult]
    collection_id: str
    query: str
    reason: str  # Why retrieval ran (e.g., "collection_attached")
    extra: dict[str, Any] = field(default_factory=dict)


def retrieve_for_query(
    query: str,
    collection_id: str,
    top_k: int = 5,
    reason: str = "collection_attached",
) -> RetrievalContext:
    """Run a single retrieval and return the context object."""
    results = search(collection_id, query, top_k=top_k)
    return RetrievalContext(
        chunks=results,
        collection_id=collection_id,
        query=query,
        reason=reason,
        extra={
            "top_score": results[0].score if results else None,
            "result_count": len(results),
        },
    )

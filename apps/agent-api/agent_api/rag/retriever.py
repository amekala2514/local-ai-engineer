"""Retriever - fetches relevant chunks for a query.

Day 14 update: optionally reranks the initial vector-similarity results
using a cross-encoder reranker for better relevance.

The pattern: over-fetch top-N (typically 20) by vector similarity, then
rerank those to top-K (typically 5). This is much higher quality than
pure vector top-K, at the cost of one extra inference call.
"""

from dataclasses import dataclass, field
from typing import Any

from agent_api.ingest.qdrant_store import SearchResult, search
from agent_api.rag.reranker import RerankedResult, get_reranker, reranker_enabled


@dataclass
class RetrievalContext:
    """Bundle of retrieved chunks plus metadata about the retrieval."""

    chunks: list[SearchResult]
    collection_id: str
    query: str
    reason: str
    extra: dict[str, Any] = field(default_factory=dict)


async def retrieve_for_query(
    query: str,
    collection_id: str,
    top_k: int = 5,
    reason: str = "collection_attached",
    rerank: bool | None = None,
    fetch_k: int = 20,
) -> RetrievalContext:
    """Run retrieval and return the context object.

    If reranking is enabled (either by parameter or by global setting),
    we fetch top-`fetch_k` from Qdrant and rerank to top-`top_k`.
    Otherwise we just return Qdrant's top-`top_k`.
    """
    use_rerank = rerank if rerank is not None else reranker_enabled()
    initial_k = fetch_k if use_rerank else top_k

    results = search(collection_id, query, top_k=initial_k)

    if not use_rerank or not results:
        return RetrievalContext(
            chunks=results,
            collection_id=collection_id,
            query=query,
            reason=reason,
            extra={
                "top_score": results[0].score if results else None,
                "result_count": len(results),
                "reranked": False,
                "fetch_k": initial_k,
            },
        )

    reranker = get_reranker()
    reranked: list[RerankedResult] = await reranker.rerank(query, results, top_k=top_k)
    final_chunks = [r.original for r in reranked]

    return RetrievalContext(
        chunks=final_chunks,
        collection_id=collection_id,
        query=query,
        reason=reason,
        extra={
            "top_score": reranked[0].rerank_score if reranked else None,
            "result_count": len(final_chunks),
            "reranked": True,
            "fetch_k": initial_k,
            "rerank_scores": [r.rerank_score for r in reranked],
            "original_ranks": [r.original_rank for r in reranked],
        },
    )

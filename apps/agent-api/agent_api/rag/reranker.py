"""Reranker — orders retrieved chunks by true query-document relevance.

Uses sentence-transformers' CrossEncoder with the bge-reranker-base model.
The cross-encoder takes (query, document) pairs and returns relevance
scores; we sort by score and keep the top-K.

The model is loaded lazily on first use to keep startup fast. Once loaded
it stays in memory for the life of the process.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from dataclasses import dataclass
from typing import Any

from agent_api.ingest.qdrant_store import SearchResult
from agent_api.settings import settings


logger = logging.getLogger(__name__)


@dataclass
class RerankedResult:
    """A search result with its rerank score attached."""

    original: SearchResult
    rerank_score: float
    original_rank: int


class Reranker:
    """Lazy-loaded sentence-transformers CrossEncoder wrapper.

    Thread-safe: the underlying model is loaded once behind a lock.
    The compute_scores call is offloaded to a thread for async use.
    """

    def __init__(self, model_name: str) -> None:
        self._model_name = model_name
        self._model: Any | None = None
        self._load_lock = threading.Lock()

    def _ensure_loaded(self) -> Any:
        """Load the model on first use. Idempotent and thread-safe."""
        if self._model is not None:
            return self._model
        with self._load_lock:
            if self._model is not None:
                return self._model
            logger.info(f"Loading reranker model: {self._model_name}")
            from sentence_transformers import CrossEncoder
            # CrossEncoder picks the best device automatically (MPS on Apple Silicon,
            # CUDA on NVIDIA, else CPU). max_length=512 matches bge-reranker-base's
            # native context.
            self._model = CrossEncoder(self._model_name, max_length=512)
            logger.info("Reranker model loaded")
            return self._model

    def _score_sync(self, query: str, texts: list[str]) -> list[float]:
        """Synchronous scoring. Returns one score per text."""
        model = self._ensure_loaded()
        if not texts:
            return []
        pairs = [(query, t) for t in texts]
        # predict returns numpy array of raw logits; we apply sigmoid to map to [0,1]
        import numpy as np
        raw_scores = model.predict(pairs)
        # Sigmoid for interpretability. Range of raw bge-reranker logits is ~[-10, 10].
        sigmoid_scores = 1.0 / (1.0 + np.exp(-raw_scores))
        return [float(s) for s in sigmoid_scores]

    async def rerank(
        self,
        query: str,
        results: list[SearchResult],
        top_k: int,
    ) -> list[RerankedResult]:
        """Rerank a list of search results, return top-K by rerank score.

        Offloads the scoring work to a thread so we don't block the event loop.
        """
        if not results:
            return []

        texts = [r.text for r in results]
        scores = await asyncio.to_thread(self._score_sync, query, texts)

        ranked = [
            RerankedResult(original=r, rerank_score=float(s), original_rank=i + 1)
            for i, (r, s) in enumerate(zip(results, scores))
        ]
        ranked.sort(key=lambda r: r.rerank_score, reverse=True)
        return ranked[:top_k]


_reranker: Reranker | None = None


def get_reranker() -> Reranker:
    """Return the singleton reranker instance."""
    global _reranker
    if _reranker is None:
        _reranker = Reranker(model_name=settings.reranker_model)
    return _reranker


def reranker_enabled() -> bool:
    """Whether reranking is enabled in settings."""
    return settings.rerank_enabled

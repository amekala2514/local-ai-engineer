"""Query transformation for retrieval: query rewriting and HyDE.

Both transform the user's query into something that embeds closer to relevant
document chunks, before retrieval. They are pure(ish) functions of a query
string -> a query string, independent of which retrieval path calls them, so
they can later be reused for memory/search retrieval, not just RAG.

- rewrite_query: clean/expand a conversational query into a search-optimized
  one (expand abbreviations, add domain terms, drop chat filler).
- generate_hyde_doc: generate a short hypothetical ANSWER to the query; the
  caller embeds that instead of the question. Answer-to-answer matching often
  retrieves better than question-to-answer when the corpus is documentation.

Both are best-effort: on any failure (model error, empty output) they return
the original query, so retrieval degrades to baseline rather than breaking.
Both are synchronous-friendly via an async client call; callers await them.
"""

from __future__ import annotations

from agent_api.models.ollama import OllamaClient
from agent_api.models.base import ChatMessage
from agent_api.settings import settings


_REWRITE_SYSTEM = """You rewrite a user's question into a concise search query \
for a documentation retrieval system. Expand abbreviations, add precise \
technical terms the answer would contain, and remove conversational filler. \
Output ONLY the rewritten query as a single line — no preamble, no quotes, no \
explanation."""

_HYDE_SYSTEM = """You write a brief, factual passage that would plausibly \
answer the user's question, as if excerpted from technical documentation. \
Write 2-4 sentences in a neutral, declarative style using the specific terms \
such a document would use. Do not hedge, do not say 'the documentation says' — \
just write the passage as if it were the documentation itself. If you are \
unsure of exact facts, still write plausibly using correct terminology."""


async def rewrite_query(query: str, client: OllamaClient) -> str:
    """Rewrite a query into a search-optimized form. Falls back to original."""
    try:
        resp = await client.chat(
            messages=[
                ChatMessage(role="system", content=_REWRITE_SYSTEM),
                ChatMessage(role="user", content=query),
            ],
            model=settings.query_transform_model,
            temperature=0.0,
        )
        out = (resp.content or "").strip()
        # Guard against the model returning nothing or echoing instructions.
        if not out or len(out) > 500:
            return query
        return out
    except Exception:
        return query


async def generate_hyde_doc(query: str, client: OllamaClient) -> str:
    """Generate a hypothetical answer passage to embed instead of the query.
    Falls back to the original query on failure."""
    try:
        resp = await client.chat(
            messages=[
                ChatMessage(role="system", content=_HYDE_SYSTEM),
                ChatMessage(role="user", content=query),
            ],
            model=settings.query_transform_model,
            temperature=0.0,
        )
        out = (resp.content or "").strip()
        if not out:
            return query
        # Prepend the original query so the embedding retains the question's
        # key terms too — a common HyDE refinement that hedges against a
        # hypothetical doc that drifts off-topic.
        return f"{query}\n\n{out}"
    except Exception:
        return query

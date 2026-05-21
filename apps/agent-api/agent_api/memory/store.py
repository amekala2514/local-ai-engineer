"""Memory store — Qdrant-backed semantic recall of past conversation turn-pairs.

Separate Qdrant collection ('memory') from the RAG document collection so the
two corpora never cross-contaminate. Each point is one turn-pair (a user
message + its assistant reply), embedded together.

Mirrors the patterns in ingest/qdrant_store.py (module-level functions, the
same _client() shape, uuid string IDs, query_points search) but adds payload
filtering to exclude the current conversation on retrieval.
"""

import uuid
from dataclasses import dataclass

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from agent_api.ingest.embedder import embed, embedding_dim
from agent_api.settings import settings


MEMORY_COLLECTION = "memory"

# Cap each side of a turn-pair before embedding. The full text is still stored
# in the payload; only the embedding input is truncated, so a very long reply
# doesn't produce a poor (diluted) embedding.
_EMBED_CHAR_CAP = 1000


@dataclass
class MemoryHit:
    """A retrieved past turn-pair with its similarity score."""
    score: float
    conversation_id: str
    turn_index: int
    user_text: str
    assistant_text: str
    created_at: str


def _client() -> QdrantClient:
    host = settings.qdrant_host
    if host == "qdrant":
        host = "localhost"
    return QdrantClient(host=host, port=settings.qdrant_port)


def _embed_text(user_text: str, assistant_text: str) -> str:
    """The text actually embedded — capped per side."""
    return (
        f"User: {user_text[:_EMBED_CHAR_CAP]}\n\n"
        f"Assistant: {assistant_text[:_EMBED_CHAR_CAP]}"
    )


def ensure_memory_collection() -> None:
    """Create the memory collection if it doesn't exist."""
    c = _client()
    existing = {col.name for col in c.get_collections().collections}
    if MEMORY_COLLECTION in existing:
        return
    c.create_collection(
        collection_name=MEMORY_COLLECTION,
        vectors_config=qmodels.VectorParams(
            size=embedding_dim(),
            distance=qmodels.Distance.COSINE,
        ),
    )


def upsert_turn_pair(
    tenant_id: str,
    conversation_id: str,
    turn_index: int,
    user_text: str,
    assistant_text: str,
) -> str:
    """Embed a turn-pair and upsert it. Returns the Qdrant point ID.

    Full user/assistant text is stored in the payload; the embedding uses the
    capped version. Caller is responsible for deciding whether to remember
    (see _should_remember in the write path).
    """
    vector = embed(_embed_text(user_text, assistant_text))
    point_id = str(uuid.uuid4())
    payload = {
        "tenant_id": tenant_id,
        "conversation_id": conversation_id,
        "turn_index": turn_index,
        "user_text": user_text,
        "assistant_text": assistant_text,
        "created_at": _now_iso(),
    }
    c = _client()
    c.upsert(
        collection_name=MEMORY_COLLECTION,
        points=[qmodels.PointStruct(id=point_id, vector=vector, payload=payload)],
    )
    return point_id


def search_memory(
    query: str,
    tenant_id: str,
    exclude_conversation_id: str | None,
    top_k: int = 3,
    fetch_k: int = 10,
    score_threshold: float = 0.70,
) -> list[MemoryHit]:
    """Retrieve relevant past turn-pairs.

    Over-fetches fetch_k, excludes the current conversation via a payload
    must_not filter, drops anything below score_threshold, returns top_k.
    Returns [] if the collection is empty or nothing clears the threshold.
    """
    c = _client()

    existing = {col.name for col in c.get_collections().collections}
    if MEMORY_COLLECTION not in existing:
        return []

    query_vector = embed(query)

    must = [
        qmodels.FieldCondition(
            key="tenant_id", match=qmodels.MatchValue(value=tenant_id)
        )
    ]
    must_not = []
    if exclude_conversation_id is not None:
        must_not.append(
            qmodels.FieldCondition(
                key="conversation_id",
                match=qmodels.MatchValue(value=exclude_conversation_id),
            )
        )
    qfilter = qmodels.Filter(must=must, must_not=must_not)

    response = c.query_points(
        collection_name=MEMORY_COLLECTION,
        query=query_vector,
        limit=fetch_k,
        query_filter=qfilter,
        with_payload=True,
    )

    hits: list[MemoryHit] = []
    for p in response.points:
        if p.score < score_threshold:
            continue
        payload = p.payload or {}
        hits.append(
            MemoryHit(
                score=p.score,
                conversation_id=payload.get("conversation_id", ""),
                turn_index=payload.get("turn_index", 0),
                user_text=payload.get("user_text", ""),
                assistant_text=payload.get("assistant_text", ""),
                created_at=payload.get("created_at", ""),
            )
        )
        if len(hits) >= top_k:
            break

    return hits


def memory_info() -> dict | None:
    """Basic stats about the memory collection, or None if absent."""
    c = _client()
    existing = {col.name for col in c.get_collections().collections}
    if MEMORY_COLLECTION not in existing:
        return None
    info = c.get_collection(collection_name=MEMORY_COLLECTION)
    return {
        "name": MEMORY_COLLECTION,
        "points_count": info.points_count,
        "status": info.status.value if hasattr(info.status, "value") else str(info.status),
    }


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()

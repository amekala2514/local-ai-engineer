"""Memory write orchestration.

Ties together the Qdrant upsert (vector) and the SQLite memory_entries record
(metadata) behind one call the chat endpoints use after a turn completes.

_should_remember is the option-b hook: today it remembers everything, but it's
the single place to add selective-embedding logic later (skip trivial turns,
length thresholds, router-flagged low-value turns) without touching callers.
"""

from __future__ import annotations

from agent_api.memory.store import upsert_turn_pair
from agent_api.storage.interfaces import Storage


def _should_remember(user_text: str, assistant_text: str) -> bool:
    """Decide whether a turn-pair is worth storing.

    Option a (current): remember everything; retrieval-time similarity
    threshold filters noise. Option b (future): add heuristics here.
    """
    return True


async def remember_turn_pair(
    storage: Storage,
    tenant_id: str,
    conversation_id: str,
    turn_index: int,
    user_text: str,
    assistant_text: str,
) -> bool:
    """Embed + store a turn-pair as memory, and record its metadata.

    Returns True if stored, False if skipped (per _should_remember) or if the
    storage backend doesn't support memory metadata. Best-effort: never raises
    into the caller — a memory-write failure must not break the chat response.
    """
    if not _should_remember(user_text, assistant_text):
        return False

    # Only SQLite backend has the memory_entries store wired.
    memory_entries = getattr(storage, "memory_entries", None)
    if memory_entries is None:
        return False

    try:
        point_id = upsert_turn_pair(
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            turn_index=turn_index,
            user_text=user_text,
            assistant_text=assistant_text,
        )
        await memory_entries.record(
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            turn_index=turn_index,
            qdrant_point_id=point_id,
            char_count=len(user_text) + len(assistant_text),
        )
        return True
    except Exception:
        # Memory is non-critical; swallow failures so the chat turn succeeds.
        # (When O2/O3 observability lands, this is a place to emit a metric.)
        return False

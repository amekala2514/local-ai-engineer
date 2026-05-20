"""Rate limiting for web search.

Hard daily quota: if the tenant has made settings.search_daily_limit
successful queries in the last 24 hours, further queries are rejected.
This is the primary defense against runaway costs.

Scoped per-tenant_id. The helper does NOT run the search — it only
decides whether the search may proceed. The endpoint wires this in.

(Idempotency caching is deferred — see Day 18a design notes. The
compute_query_hash helper is kept for audit-table consistency.)
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from agent_api.settings import settings
from agent_api.storage.interfaces import SearchQueryStore


@dataclass
class LimitDecision:
    """The decision returned by check_daily_limit.

    - allow=True              → search is permitted
    - allow=False, reason=msg → reject (429), include reason in response
    """
    allow: bool
    reason: str | None = None
    current_count: int = 0
    limit: int = 0


def compute_query_hash(query: str) -> str:
    """Deterministic hash for audit-table consistency.

    Normalize whitespace and case so 'Python ' and 'python' map to the
    same hash. SHA-256; collisions not a concern at this scale.
    """
    normalized = " ".join(query.lower().split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


async def check_daily_limit(
    store: SearchQueryStore,
    tenant_id: str,
) -> LimitDecision:
    """Check whether the tenant is under the daily quota.

    Returns LimitDecision with allow=False if at or over limit.
    """
    now = datetime.now(timezone.utc)
    one_day_ago = now - timedelta(hours=24)
    count = await store.count_since(tenant_id, one_day_ago)
    limit = settings.search_daily_limit

    if count >= limit:
        return LimitDecision(
            allow=False,
            reason=(
                f"Daily search limit reached ({count}/{limit}). "
                f"Limit resets 24h after each query."
            ),
            current_count=count,
            limit=limit,
        )

    return LimitDecision(allow=True, current_count=count, limit=limit)

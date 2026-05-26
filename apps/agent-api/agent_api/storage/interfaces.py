"""Abstract storage interfaces.

The application talks to storage only through these interfaces. Concrete
backends (SQLite for local, Postgres for cloud) implement them.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


@dataclass
class Conversation:
    """A conversation thread."""

    id: str
    tenant_id: str
    title: str | None
    created_at: datetime
    updated_at: datetime
    collection_id: str | None = None  # Knowledge collection attached, if any


@dataclass
class StoredMessage:
    """A message stored as part of a conversation."""

    id: int
    conversation_id: str
    tenant_id: str
    role: str
    content: str
    model: str | None
    created_at: datetime


class ConversationStore(ABC):
    @abstractmethod
    async def create(
        self,
        tenant_id: str,
        title: str | None = None,
        collection_id: str | None = None,
    ) -> Conversation:
        raise NotImplementedError

    @abstractmethod
    async def get(self, tenant_id: str, conversation_id: str) -> Conversation | None:
        raise NotImplementedError

    @abstractmethod
    async def list(self, tenant_id: str, limit: int = 50) -> list[Conversation]:
        raise NotImplementedError


class MessageStore(ABC):
    @abstractmethod
    async def append(
        self,
        conversation_id: str,
        tenant_id: str,
        role: str,
        content: str,
        model: str | None = None,
    ) -> StoredMessage:
        raise NotImplementedError

    @abstractmethod
    async def list_for_conversation(
        self,
        conversation_id: str,
        tenant_id: str,
    ) -> list[StoredMessage]:
        raise NotImplementedError


@dataclass
class SearchQueryRecord:
    """A logged search query — used for audit + rate limit + idempotency."""
    id: int
    tenant_id: str
    query: str
    query_hash: str
    result_count: int
    status: str  # 'ok', 'error', 'cached'
    error: str | None
    created_at: datetime


class SearchQueryStore(ABC):
    """Audit + rate-limit + idempotency cache for web search calls.

    All methods scoped by tenant_id so future multi-tenant deployments
    don't need migration.
    """

    @abstractmethod
    async def count_since(self, tenant_id: str, since: datetime) -> int:
        """Return number of 'ok' or 'cached' queries since `since`. Errors don't count
        against the rate limit (so a misconfigured Brave key doesn't lock the user out).
        """
        raise NotImplementedError

    @abstractmethod
    async def find_cached(
        self, tenant_id: str, query_hash: str, since: datetime,
    ) -> SearchQueryRecord | None:
        """Return the most recent successful query record with this hash since `since`,
        or None. Used for the 60-second idempotency cache.
        """
        raise NotImplementedError

    @abstractmethod
    async def record(
        self,
        tenant_id: str,
        query: str,
        query_hash: str,
        result_count: int,
        status: str,
        error: str | None = None,
    ) -> SearchQueryRecord:
        """Insert an audit row and return it."""
        raise NotImplementedError


@dataclass
class RequestMetricsRecord:
    """A logged chat request — token usage + which context sources fired."""
    id: int
    tenant_id: str
    conversation_id: str | None
    model: str
    task_type: str
    routing_reason: str | None
    rag_used: bool
    url_used: bool
    search_used: bool
    memory_used: bool
    status: str  # 'completed', 'aborted', 'error'
    prompt_tokens: int | None
    completion_tokens: int | None
    duration_ms: int | None
    created_at: datetime


class RequestMetricsStore(ABC):
    """Per-request observability metrics. Scoped by tenant_id.

    Records token usage and context-source flags for every chat request.
    Token/duration fields are None for non-completed requests (aborted or
    error), because Ollama only emits token counts in the final stream
    chunk, which aborted/errored requests never reach.
    """

    @abstractmethod
    async def record(
        self,
        tenant_id: str,
        conversation_id: str | None,
        model: str,
        task_type: str,
        routing_reason: str | None,
        rag_used: bool,
        url_used: bool,
        search_used: bool,
        status: str,
        memory_used: bool = False,
        prompt_tokens: int | None = None,
        completion_tokens: int | None = None,
        duration_ms: int | None = None,
    ) -> RequestMetricsRecord:
        """Insert a metrics row and return it."""
        raise NotImplementedError

    @abstractmethod
    async def aggregate_since(self, tenant_id: str, since: datetime) -> list[dict]:
        """Return aggregates since `since`, grouped by
        (model, status, rag_used, url_used, search_used). Each dict:
        {model, status, rag_used, url_used, search_used, request_count,
         total_prompt_tokens, total_completion_tokens, avg_duration_ms}.
        Powers the /metrics endpoint. Token sums count only completed rows.
        """
        raise NotImplementedError


@dataclass
class MemoryEntryRecord:
    """Metadata for one stored turn-pair memory. The text lives in Qdrant;
    this row links to it via qdrant_point_id and supports stats + future
    pruning (option b) without scanning the vector store."""
    id: int
    tenant_id: str
    conversation_id: str
    turn_index: int
    qdrant_point_id: str
    char_count: int
    created_at: datetime


class MemoryEntryStore(ABC):
    """Metadata index for cross-conversation memory entries. Scoped by tenant_id.

    Mirrors what's upserted to the Qdrant 'memory' collection. The vector store
    does similarity search; this is the source of truth for what exists.
    """

    @abstractmethod
    async def record(
        self,
        tenant_id: str,
        conversation_id: str,
        turn_index: int,
        qdrant_point_id: str,
        char_count: int,
    ) -> MemoryEntryRecord:
        """Insert a memory-entry row and return it."""
        raise NotImplementedError

    @abstractmethod
    async def count(self, tenant_id: str) -> int:
        """Total memory entries for the tenant."""
        raise NotImplementedError


class PolicyAuditStore(ABC):
    """Append-only audit trail of Phase C policy decisions. One row per
    decision; approved + execution_result are filled as the action progresses
    (proposed -> approved -> executed). Intent is stored as JSON for forensics.
    """
    @abstractmethod
    async def record_decision(self, intent, result, threat_model_version: str) -> int:
        """Log a decision; return the audit row id."""
        raise NotImplementedError

    @abstractmethod
    async def mark_approved(self, audit_id: int, approved: bool) -> None:
        """Record the human's approve/reject for an approval-required action."""
        raise NotImplementedError

    @abstractmethod
    async def record_execution(self, audit_id: int, execution_result: str) -> None:
        """Record the outcome once the tool actually runs (Day 31+)."""
        raise NotImplementedError


class Storage(ABC):
    conversations: ConversationStore
    messages: MessageStore
    search_queries: SearchQueryStore
    request_metrics: RequestMetricsStore
    memory_entries: MemoryEntryStore
    policy_audit: PolicyAuditStore

    @abstractmethod
    async def initialize(self) -> None:
        raise NotImplementedError

    @abstractmethod
    async def close(self) -> None:
        raise NotImplementedError

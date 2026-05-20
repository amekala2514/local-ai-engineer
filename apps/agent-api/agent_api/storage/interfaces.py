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


class Storage(ABC):
    conversations: ConversationStore
    messages: MessageStore
    search_queries: SearchQueryStore

    @abstractmethod
    async def initialize(self) -> None:
        raise NotImplementedError

    @abstractmethod
    async def close(self) -> None:
        raise NotImplementedError

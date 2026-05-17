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


class Storage(ABC):
    conversations: ConversationStore
    messages: MessageStore

    @abstractmethod
    async def initialize(self) -> None:
        raise NotImplementedError

    @abstractmethod
    async def close(self) -> None:
        raise NotImplementedError

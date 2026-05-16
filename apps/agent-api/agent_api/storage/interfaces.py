"""Abstract storage interfaces.

The application talks to storage only through these interfaces. Concrete
backends (SQLite for local, Postgres for cloud) implement them. This is
the seam that keeps the application code free of database specifics.
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


@dataclass
class StoredMessage:
    """A message stored as part of a conversation.

    Distinct from ChatMessage (the in-flight model-facing type) so that
    storage concerns don't leak into the model layer.
    """

    id: int
    conversation_id: str
    tenant_id: str
    role: str  # "system", "user", "assistant"
    content: str
    model: str | None
    created_at: datetime


class ConversationStore(ABC):
    """Storage for conversation threads."""

    @abstractmethod
    async def create(self, tenant_id: str, title: str | None = None) -> Conversation:
        """Create a new conversation and return it."""
        raise NotImplementedError

    @abstractmethod
    async def get(self, tenant_id: str, conversation_id: str) -> Conversation | None:
        """Get a conversation by ID, or None if not found."""
        raise NotImplementedError

    @abstractmethod
    async def list(self, tenant_id: str, limit: int = 50) -> list[Conversation]:
        """List conversations for a tenant, most recent first."""
        raise NotImplementedError


class MessageStore(ABC):
    """Storage for individual messages in conversations."""

    @abstractmethod
    async def append(
        self,
        conversation_id: str,
        tenant_id: str,
        role: str,
        content: str,
        model: str | None = None,
    ) -> StoredMessage:
        """Append a message to a conversation."""
        raise NotImplementedError

    @abstractmethod
    async def list_for_conversation(
        self,
        conversation_id: str,
        tenant_id: str,
    ) -> list[StoredMessage]:
        """Return all messages in a conversation, oldest first."""
        raise NotImplementedError


class Storage(ABC):
    """Combined storage handle."""

    conversations: ConversationStore
    messages: MessageStore

    @abstractmethod
    async def initialize(self) -> None:
        """Create tables / run migrations as needed."""
        raise NotImplementedError

    @abstractmethod
    async def close(self) -> None:
        """Release resources."""
        raise NotImplementedError

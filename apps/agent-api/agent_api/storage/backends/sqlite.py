"""SQLite storage backend."""

import uuid
from datetime import datetime, timezone
from pathlib import Path

import aiosqlite

from agent_api.storage.interfaces import (
    Conversation,
    ConversationStore,
    MessageStore,
    Storage,
    StoredMessage,
)


SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    title TEXT,
    collection_id TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_conversations_tenant_updated
    ON conversations(tenant_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id TEXT NOT NULL,
    tenant_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    model TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id)
);

CREATE INDEX IF NOT EXISTS idx_messages_conversation
    ON messages(conversation_id, created_at);

CREATE TABLE IF NOT EXISTS retrieval_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id TEXT NOT NULL,
    tenant_id TEXT NOT NULL,
    collection_id TEXT NOT NULL,
    query TEXT NOT NULL,
    top_score REAL,
    chunk_count INTEGER NOT NULL,
    chunk_ids TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_retrieval_log_conversation
    ON retrieval_log(conversation_id, created_at);
"""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_iso(s: str) -> datetime:
    return datetime.fromisoformat(s)


class SQLiteConversationStore(ConversationStore):
    def __init__(self, db: aiosqlite.Connection) -> None:
        self._db = db

    async def create(
        self,
        tenant_id: str,
        title: str | None = None,
        collection_id: str | None = None,
    ) -> Conversation:
        conv_id = str(uuid.uuid4())
        now = _now_iso()
        await self._db.execute(
            "INSERT INTO conversations (id, tenant_id, title, collection_id, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (conv_id, tenant_id, title, collection_id, now, now),
        )
        await self._db.commit()
        return Conversation(
            id=conv_id,
            tenant_id=tenant_id,
            title=title,
            collection_id=collection_id,
            created_at=_parse_iso(now),
            updated_at=_parse_iso(now),
        )

    async def get(self, tenant_id: str, conversation_id: str) -> Conversation | None:
        async with self._db.execute(
            "SELECT id, tenant_id, title, collection_id, created_at, updated_at "
            "FROM conversations WHERE id = ? AND tenant_id = ?",
            (conversation_id, tenant_id),
        ) as cursor:
            row = await cursor.fetchone()
        if row is None:
            return None
        return Conversation(
            id=row[0],
            tenant_id=row[1],
            title=row[2],
            collection_id=row[3],
            created_at=_parse_iso(row[4]),
            updated_at=_parse_iso(row[5]),
        )

    async def list(self, tenant_id: str, limit: int = 50) -> list[Conversation]:
        async with self._db.execute(
            "SELECT id, tenant_id, title, collection_id, created_at, updated_at FROM conversations "
            "WHERE tenant_id = ? ORDER BY updated_at DESC LIMIT ?",
            (tenant_id, limit),
        ) as cursor:
            rows = await cursor.fetchall()
        return [
            Conversation(
                id=r[0],
                tenant_id=r[1],
                title=r[2],
                collection_id=r[3],
                created_at=_parse_iso(r[4]),
                updated_at=_parse_iso(r[5]),
            )
            for r in rows
        ]

    async def touch(self, conversation_id: str, tenant_id: str) -> None:
        await self._db.execute(
            "UPDATE conversations SET updated_at = ? WHERE id = ? AND tenant_id = ?",
            (_now_iso(), conversation_id, tenant_id),
        )
        await self._db.commit()


class SQLiteMessageStore(MessageStore):
    def __init__(
        self,
        db: aiosqlite.Connection,
        conversations: SQLiteConversationStore,
    ) -> None:
        self._db = db
        self._conversations = conversations

    async def append(
        self,
        conversation_id: str,
        tenant_id: str,
        role: str,
        content: str,
        model: str | None = None,
    ) -> StoredMessage:
        now = _now_iso()
        cursor = await self._db.execute(
            "INSERT INTO messages (conversation_id, tenant_id, role, content, model, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (conversation_id, tenant_id, role, content, model, now),
        )
        await self._db.commit()
        await self._conversations.touch(conversation_id, tenant_id)
        return StoredMessage(
            id=cursor.lastrowid or 0,
            conversation_id=conversation_id,
            tenant_id=tenant_id,
            role=role,
            content=content,
            model=model,
            created_at=_parse_iso(now),
        )

    async def list_for_conversation(
        self,
        conversation_id: str,
        tenant_id: str,
    ) -> list[StoredMessage]:
        async with self._db.execute(
            "SELECT id, conversation_id, tenant_id, role, content, model, created_at "
            "FROM messages WHERE conversation_id = ? AND tenant_id = ? "
            "ORDER BY created_at ASC, id ASC",
            (conversation_id, tenant_id),
        ) as cursor:
            rows = await cursor.fetchall()
        return [
            StoredMessage(
                id=r[0],
                conversation_id=r[1],
                tenant_id=r[2],
                role=r[3],
                content=r[4],
                model=r[5],
                created_at=_parse_iso(r[6]),
            )
            for r in rows
        ]


class SQLiteStorage(Storage):
    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._db: aiosqlite.Connection | None = None
        self.conversations: SQLiteConversationStore = None  # type: ignore[assignment]
        self.messages: SQLiteMessageStore = None  # type: ignore[assignment]

    async def initialize(self) -> None:
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        self._db = await aiosqlite.connect(self._db_path)
        await self._db.executescript(SCHEMA)
        await self._db.commit()
        self.conversations = SQLiteConversationStore(self._db)
        self.messages = SQLiteMessageStore(self._db, self.conversations)

    async def close(self) -> None:
        if self._db is not None:
            await self._db.close()
            self._db = None

    async def log_retrieval(
        self,
        conversation_id: str,
        tenant_id: str,
        collection_id: str,
        query: str,
        top_score: float | None,
        chunk_count: int,
        chunk_ids: list[str],
    ) -> None:
        """Log a retrieval call for later analysis (Phase B auto-detect work)."""
        import json
        await self._db.execute(
            "INSERT INTO retrieval_log "
            "(conversation_id, tenant_id, collection_id, query, top_score, chunk_count, chunk_ids, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                conversation_id, tenant_id, collection_id, query,
                top_score, chunk_count, json.dumps(chunk_ids), _now_iso(),
            ),
        )
        await self._db.commit()

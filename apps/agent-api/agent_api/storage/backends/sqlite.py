"""SQLite storage backend."""

import uuid
from datetime import datetime, timezone
from pathlib import Path

import aiosqlite

from agent_api.storage.interfaces import (
    Conversation,
    ConversationStore,
    MemoryEntryRecord,
    MemoryEntryStore,
    MessageStore,
    RequestMetricsRecord,
    RequestMetricsStore,
    SearchQueryRecord,
    SearchQueryStore,
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

CREATE TABLE IF NOT EXISTS search_queries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id TEXT NOT NULL,
    query TEXT NOT NULL,
    query_hash TEXT NOT NULL,
    result_count INTEGER NOT NULL,
    status TEXT NOT NULL,
    error TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_search_queries_tenant_created
    ON search_queries(tenant_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_search_queries_tenant_hash_created
    ON search_queries(tenant_id, query_hash, created_at DESC);
CREATE TABLE IF NOT EXISTS request_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id TEXT NOT NULL,
    conversation_id TEXT,
    model TEXT NOT NULL,
    task_type TEXT NOT NULL,
    routing_reason TEXT,
    rag_used INTEGER NOT NULL,
    url_used INTEGER NOT NULL,
    search_used INTEGER NOT NULL,
    status TEXT NOT NULL,
    prompt_tokens INTEGER,
    completion_tokens INTEGER,
    duration_ms INTEGER,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_request_metrics_tenant_created
    ON request_metrics(tenant_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_request_metrics_tenant_model_created
    ON request_metrics(tenant_id, model, created_at DESC);
CREATE TABLE IF NOT EXISTS memory_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id TEXT NOT NULL,
    conversation_id TEXT NOT NULL,
    turn_index INTEGER NOT NULL,
    qdrant_point_id TEXT NOT NULL,
    char_count INTEGER NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_memory_entries_tenant_conversation
    ON memory_entries(tenant_id, conversation_id);
CREATE INDEX IF NOT EXISTS idx_memory_entries_tenant_created
    ON memory_entries(tenant_id, created_at DESC);
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

    async def delete(self, tenant_id: str, conversation_id: str) -> bool:
        """Delete a conversation and all its messages. Returns True if deleted."""
        await self._db.execute(
            "DELETE FROM messages WHERE conversation_id = ? AND tenant_id = ?",
            (conversation_id, tenant_id),
        )
        cursor = await self._db.execute(
            "DELETE FROM conversations WHERE id = ? AND tenant_id = ?",
            (conversation_id, tenant_id),
        )
        await self._db.commit()
        return cursor.rowcount > 0

    async def rename(
        self, tenant_id: str, conversation_id: str, new_title: str
    ) -> bool:
        """Update a conversation's title. Returns True if updated."""
        cursor = await self._db.execute(
            "UPDATE conversations SET title = ?, updated_at = ? WHERE id = ? AND tenant_id = ?",
            (new_title, _now_iso(), conversation_id, tenant_id),
        )
        await self._db.commit()
        return cursor.rowcount > 0


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

    async def delete_after(
        self,
        conversation_id: str,
        tenant_id: str,
        message_id: int,
    ) -> int:
        """Delete all messages in conversation with id > message_id. Used by regenerate."""
        cursor = await self._db.execute(
            "DELETE FROM messages WHERE conversation_id = ? AND tenant_id = ? AND id >= ?",
            (conversation_id, tenant_id, message_id),
        )
        await self._db.commit()
        return cursor.rowcount


class SQLiteSearchQueryStore(SearchQueryStore):
    """SQLite-backed audit + rate-limit + idempotency store for web search."""

    def __init__(self, db: aiosqlite.Connection) -> None:
        self._db = db

    async def count_since(self, tenant_id: str, since: datetime) -> int:
        async with self._db.execute(
            "SELECT COUNT(*) FROM search_queries "
            "WHERE tenant_id = ? AND created_at >= ? AND status IN ('ok', 'cached')",
            (tenant_id, since.isoformat()),
        ) as cursor:
            row = await cursor.fetchone()
            return int(row[0]) if row else 0

    async def find_cached(
        self, tenant_id: str, query_hash: str, since: datetime,
    ) -> SearchQueryRecord | None:
        async with self._db.execute(
            "SELECT id, tenant_id, query, query_hash, result_count, status, error, created_at "
            "FROM search_queries "
            "WHERE tenant_id = ? AND query_hash = ? AND created_at >= ? AND status = 'ok' "
            "ORDER BY created_at DESC LIMIT 1",
            (tenant_id, query_hash, since.isoformat()),
        ) as cursor:
            row = await cursor.fetchone()
            if row is None:
                return None
            return SearchQueryRecord(
                id=row[0], tenant_id=row[1], query=row[2], query_hash=row[3],
                result_count=row[4], status=row[5], error=row[6],
                created_at=_parse_iso(row[7]),
            )

    async def record(
        self,
        tenant_id: str,
        query: str,
        query_hash: str,
        result_count: int,
        status: str,
        error: str | None = None,
    ) -> SearchQueryRecord:
        created_at = _now_iso()
        cursor = await self._db.execute(
            "INSERT INTO search_queries "
            "(tenant_id, query, query_hash, result_count, status, error, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (tenant_id, query, query_hash, result_count, status, error, created_at),
        )
        await self._db.commit()
        return SearchQueryRecord(
            id=cursor.lastrowid or 0,
            tenant_id=tenant_id, query=query, query_hash=query_hash,
            result_count=result_count, status=status, error=error,
            created_at=_parse_iso(created_at),
        )


class SQLiteRequestMetricsStore(RequestMetricsStore):
    """SQLite-backed per-request token + context-source metrics."""

    def __init__(self, db: aiosqlite.Connection) -> None:
        self._db = db

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
        prompt_tokens: int | None = None,
        completion_tokens: int | None = None,
        duration_ms: int | None = None,
    ) -> RequestMetricsRecord:
        created_at = _now_iso()
        cursor = await self._db.execute(
            "INSERT INTO request_metrics "
            "(tenant_id, conversation_id, model, task_type, routing_reason, "
            "rag_used, url_used, search_used, status, prompt_tokens, "
            "completion_tokens, duration_ms, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                tenant_id, conversation_id, model, task_type, routing_reason,
                int(rag_used), int(url_used), int(search_used), status,
                prompt_tokens, completion_tokens, duration_ms, created_at,
            ),
        )
        await self._db.commit()
        return RequestMetricsRecord(
            id=cursor.lastrowid or 0,
            tenant_id=tenant_id, conversation_id=conversation_id,
            model=model, task_type=task_type, routing_reason=routing_reason,
            rag_used=rag_used, url_used=url_used, search_used=search_used,
            status=status, prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens, duration_ms=duration_ms,
            created_at=_parse_iso(created_at),
        )

    async def aggregate_since(self, tenant_id: str, since: datetime) -> list[dict]:
        async with self._db.execute(
            "SELECT model, status, rag_used, url_used, search_used, "
            "COUNT(*) AS request_count, "
            "SUM(prompt_tokens) AS total_prompt_tokens, "
            "SUM(completion_tokens) AS total_completion_tokens, "
            "AVG(duration_ms) AS avg_duration_ms "
            "FROM request_metrics "
            "WHERE tenant_id = ? AND created_at >= ? "
            "GROUP BY model, status, rag_used, url_used, search_used",
            (tenant_id, since.isoformat()),
        ) as cursor:
            rows = await cursor.fetchall()
            return [
                {
                    "model": r[0],
                    "status": r[1],
                    "rag_used": bool(r[2]),
                    "url_used": bool(r[3]),
                    "search_used": bool(r[4]),
                    "request_count": int(r[5]),
                    "total_prompt_tokens": int(r[6]) if r[6] is not None else 0,
                    "total_completion_tokens": int(r[7]) if r[7] is not None else 0,
                    "avg_duration_ms": float(r[8]) if r[8] is not None else None,
                }
                for r in rows
            ]


class SQLiteMemoryEntryStore(MemoryEntryStore):
    """SQLite-backed metadata index for cross-conversation memory entries."""

    def __init__(self, db: aiosqlite.Connection) -> None:
        self._db = db

    async def record(
        self,
        tenant_id: str,
        conversation_id: str,
        turn_index: int,
        qdrant_point_id: str,
        char_count: int,
    ) -> MemoryEntryRecord:
        created_at = _now_iso()
        cursor = await self._db.execute(
            "INSERT INTO memory_entries "
            "(tenant_id, conversation_id, turn_index, qdrant_point_id, char_count, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (tenant_id, conversation_id, turn_index, qdrant_point_id, char_count, created_at),
        )
        await self._db.commit()
        return MemoryEntryRecord(
            id=cursor.lastrowid or 0,
            tenant_id=tenant_id, conversation_id=conversation_id,
            turn_index=turn_index, qdrant_point_id=qdrant_point_id,
            char_count=char_count, created_at=_parse_iso(created_at),
        )

    async def count(self, tenant_id: str) -> int:
        async with self._db.execute(
            "SELECT COUNT(*) FROM memory_entries WHERE tenant_id = ?",
            (tenant_id,),
        ) as cursor:
            row = await cursor.fetchone()
            return int(row[0]) if row else 0


class SQLiteStorage(Storage):
    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._db: aiosqlite.Connection | None = None
        self.conversations: SQLiteConversationStore = None  # type: ignore[assignment]
        self.messages: SQLiteMessageStore = None  # type: ignore[assignment]
        self.search_queries: SQLiteSearchQueryStore = None  # type: ignore[assignment]
        self.request_metrics: SQLiteRequestMetricsStore = None  # type: ignore[assignment]
        self.memory_entries: SQLiteMemoryEntryStore = None  # type: ignore[assignment]

    async def initialize(self) -> None:
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        self._db = await aiosqlite.connect(self._db_path)
        await self._db.executescript(SCHEMA)
        await self._db.commit()
        self.conversations = SQLiteConversationStore(self._db)
        self.messages = SQLiteMessageStore(self._db, self.conversations)
        self.search_queries = SQLiteSearchQueryStore(self._db)
        self.request_metrics = SQLiteRequestMetricsStore(self._db)
        self.memory_entries = SQLiteMemoryEntryStore(self._db)

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
        """Log a retrieval call for later analysis."""
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

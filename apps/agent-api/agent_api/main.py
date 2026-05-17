"""Agent API entry point.

Phase A Day 12: upload + ingest through UI, plus collection management endpoints.
"""

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import (
    Cookie,
    Depends,
    FastAPI,
    File,
    Form,
    Header,
    HTTPException,
    Response,
    UploadFile,
)
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from agent_api.auth.session_store import session_store
from agent_api.ingest.async_runner import ingest_file_async
from agent_api.ingest.qdrant_store import (
    _client as qdrant_client_factory,
    drop_collection,
    ensure_collection,
)
from agent_api.ingest.uploads import save_upload
from agent_api.models.base import ChatMessage
from agent_api.models.ollama import OllamaClient
from agent_api.models.router import pick_model
from agent_api.rag.prompt import build_rag_system_prompt
from agent_api.rag.retriever import RetrievalContext, retrieve_for_query
from agent_api.settings import ENV_FILE, settings
from agent_api.storage.backends.sqlite import SQLiteStorage
from agent_api.storage.factory import make_storage
from agent_api.storage.interfaces import Storage


SESSION_COOKIE_NAME = "session"

_model_client: OllamaClient | None = None
_storage: Storage | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _model_client, _storage
    _model_client = OllamaClient(host=settings.ollama_host)
    _storage = make_storage()
    await _storage.initialize()
    yield
    await _model_client.close()
    await _storage.close()


app = FastAPI(
    title="Local AI Engineering Assistant",
    description="Agent API for the local-ai-engineer project",
    version="0.8.0",
    lifespan=lifespan,
)


# ---------- Auth ----------


def require_auth(
    authorization: Annotated[str | None, Header()] = None,
    session: Annotated[str | None, Cookie(alias=SESSION_COOKIE_NAME)] = None,
) -> str:
    if authorization is not None:
        if not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Authorization must use Bearer scheme")
        token = authorization.removeprefix("Bearer ").strip()
        if token != settings.agent_api_token:
            raise HTTPException(status_code=401, detail="Invalid token")
        return "bearer"
    if session is not None:
        if session_store.get(session) is not None:
            return "session"
        raise HTTPException(status_code=401, detail="Invalid or expired session")
    raise HTTPException(
        status_code=401,
        detail="Authentication required (Authorization header or session cookie)",
    )


def get_model_client() -> OllamaClient:
    if _model_client is None:
        raise HTTPException(status_code=503, detail="Model client not initialized")
    return _model_client


def get_storage() -> Storage:
    if _storage is None:
        raise HTTPException(status_code=503, detail="Storage not initialized")
    return _storage


# ---------- Schemas ----------


class LoginRequest(BaseModel):
    token: str = Field(..., description="The bearer token to authenticate with")


class CreateConversationRequest(BaseModel):
    title: str | None = Field(default=None)
    collection_id: str | None = Field(default=None)


class CreateCollectionRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)


class ChatRequest(BaseModel):
    message: str = Field(..., description="The user's message")
    task_type: str = Field(default="auto")
    system_prompt: str | None = Field(default=None)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    conversation_id: str | None = Field(default=None)
    collection_id: str | None = Field(default=None)


class ChatReply(BaseModel):
    reply: str
    model_used: str
    task_type: str
    routing_reason: str
    conversation_id: str
    rag_used: bool = False
    sources: list[dict] = Field(default_factory=list)


class ConversationSummary(BaseModel):
    id: str
    title: str | None
    collection_id: str | None
    created_at: str
    updated_at: str


class MessageItem(BaseModel):
    id: int
    role: str
    content: str
    model: str | None
    created_at: str


class CollectionInfo(BaseModel):
    name: str
    points_count: int


class IngestResultPayload(BaseModel):
    filename: str
    chunks_created: int
    chunks_stored: int
    errors: list[str] = Field(default_factory=list)


# ---------- Helpers ----------


def _chunk_to_source_dict(chunk) -> dict:
    from pathlib import Path
    return {
        "score": round(chunk.score, 4),
        "source_file": Path(chunk.source_file).name,
        "document_title": chunk.document_title,
        "section_path": chunk.section_path,
        "page_number": chunk.page_number,
        "text": chunk.text,
    }


async def _resolve_or_create_conversation(
    storage: Storage,
    tenant_id: str,
    conversation_id: str | None,
    collection_id: str | None,
    first_message_preview: str,
) -> tuple[str, str | None]:
    if conversation_id is not None:
        existing = await storage.conversations.get(tenant_id, conversation_id)
        if existing is None:
            raise HTTPException(
                status_code=404,
                detail=f"Conversation {conversation_id} not found",
            )
        return existing.id, existing.collection_id

    title = first_message_preview.strip()[:60]
    new_conv = await storage.conversations.create(
        tenant_id, title=title, collection_id=collection_id,
    )
    return new_conv.id, new_conv.collection_id


async def _build_message_history(
    storage: Storage,
    tenant_id: str,
    conversation_id: str,
    system_prompt: str | None,
    new_user_message: str,
) -> list[ChatMessage]:
    history = await storage.messages.list_for_conversation(conversation_id, tenant_id)
    messages: list[ChatMessage] = []
    if system_prompt:
        messages.append(ChatMessage(role="system", content=system_prompt))
    for m in history:
        messages.append(ChatMessage(role=m.role, content=m.content))
    messages.append(ChatMessage(role="user", content=new_user_message))
    return messages


def _build_messages_with_rag(
    rag_context: RetrievalContext | None,
    history_messages: list[ChatMessage],
    user_message: str,
) -> list[ChatMessage]:
    out: list[ChatMessage] = []
    if rag_context is not None:
        out.append(ChatMessage(role="system", content=build_rag_system_prompt(rag_context)))
    for m in history_messages:
        if m.role == "system" and rag_context is not None:
            continue
        out.append(m)
    return out


async def _maybe_retrieve(
    collection_id: str | None,
    user_message: str,
) -> RetrievalContext | None:
    if not collection_id:
        return None
    return retrieve_for_query(
        query=user_message,
        collection_id=collection_id,
        top_k=5,
        reason="collection_attached",
    )


# ---------- Auth endpoints ----------


@app.post("/api/auth/login")
async def login(request: LoginRequest, response: Response) -> dict:
    if request.token != settings.agent_api_token:
        raise HTTPException(status_code=401, detail="Invalid token")
    new_session = session_store.create()
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=new_session.id,
        httponly=True,
        samesite="strict",
        secure=False,
        max_age=int((new_session.expires_at - new_session.created_at).total_seconds()),
        path="/",
    )
    return {"ok": True, "expires_at": new_session.expires_at.isoformat()}


@app.post("/api/auth/logout")
async def logout(
    response: Response,
    session: Annotated[str | None, Cookie(alias=SESSION_COOKIE_NAME)] = None,
) -> dict:
    if session is not None:
        session_store.delete(session)
    response.delete_cookie(key=SESSION_COOKIE_NAME, path="/")
    return {"ok": True}


@app.get("/api/auth/me")
async def me(auth_mode: Annotated[str, Depends(require_auth)]) -> dict:
    return {"authenticated": True, "auth_mode": auth_mode}


# ---------- Core endpoints ----------


@app.get("/api/health")
async def health() -> dict:
    ollama_ok = False
    if _model_client is not None:
        ollama_ok = await _model_client.health_check()
    return {
        "status": "ok",
        "service": "agent-api",
        "version": app.version,
        "tenant_id": settings.tenant_id,
        "ollama_reachable": ollama_ok,
        "storage_backend": settings.storage_backend,
    }


# ---------- Collections ----------


@app.get("/api/collections", response_model=list[CollectionInfo])
async def list_collections(
    _: Annotated[str, Depends(require_auth)],
) -> list[CollectionInfo]:
    try:
        c = qdrant_client_factory()
        cols = c.get_collections().collections
        result = []
        for col in cols:
            info = c.get_collection(collection_name=col.name)
            result.append(CollectionInfo(
                name=col.name,
                points_count=info.points_count or 0,
            ))
        return result
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Qdrant unavailable: {e}") from e


@app.post("/api/collections", response_model=CollectionInfo, status_code=201)
async def create_collection(
    request: CreateCollectionRequest,
    _: Annotated[str, Depends(require_auth)],
) -> CollectionInfo:
    """Create an empty collection."""
    # Same safe-name rules we use for filesystem
    from agent_api.ingest.uploads import safe_filename
    if safe_filename(request.name) != request.name:
        raise HTTPException(
            status_code=400,
            detail="Collection name must contain only letters, digits, dots, hyphens, or underscores",
        )
    try:
        ensure_collection(request.name)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Failed to create collection: {e}") from e
    return CollectionInfo(name=request.name, points_count=0)


@app.delete("/api/collections/{name}", status_code=204)
async def delete_collection(
    name: str,
    _: Annotated[str, Depends(require_auth)],
) -> Response:
    """Drop a collection. Idempotent: deleting an absent collection returns 204."""
    try:
        drop_collection(name)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Failed to drop collection: {e}") from e
    return Response(status_code=204)


@app.post(
    "/api/collections/{name}/files",
    response_model=IngestResultPayload,
)
async def upload_to_collection(
    name: str,
    _: Annotated[str, Depends(require_auth)],
    file: Annotated[UploadFile, File(...)],
) -> IngestResultPayload:
    """Upload a file and ingest it into the named collection.

    Synchronous: the response returns once ingestion completes.
    """
    # Read upload content
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty file")

    # Save to disk (validates extension + size)
    try:
        saved_path = save_upload(name, file.filename or "upload", content)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    # Ingest. ingest_file_async handles thread-pool offloading internally.
    try:
        result = await ingest_file_async(saved_path, name)
    except Exception as e:
        # Leave the file on disk so the user can retry; just surface the error.
        raise HTTPException(
            status_code=500,
            detail=f"Ingestion failed: {type(e).__name__}: {e}",
        ) from e

    return IngestResultPayload(
        filename=saved_path.name,
        chunks_created=result.chunks_created,
        chunks_stored=result.chunks_stored,
        errors=result.errors,
    )


# ---------- Conversations ----------


@app.post("/api/conversations", response_model=ConversationSummary)
async def create_conversation(
    request: CreateConversationRequest,
    _: Annotated[str, Depends(require_auth)],
    storage: Annotated[Storage, Depends(get_storage)],
) -> ConversationSummary:
    conv = await storage.conversations.create(
        tenant_id=settings.tenant_id,
        title=request.title,
        collection_id=request.collection_id,
    )
    return ConversationSummary(
        id=conv.id,
        title=conv.title,
        collection_id=conv.collection_id,
        created_at=conv.created_at.isoformat(),
        updated_at=conv.updated_at.isoformat(),
    )


@app.get("/api/conversations", response_model=list[ConversationSummary])
async def list_conversations(
    _: Annotated[str, Depends(require_auth)],
    storage: Annotated[Storage, Depends(get_storage)],
    limit: int = 50,
) -> list[ConversationSummary]:
    convs = await storage.conversations.list(settings.tenant_id, limit=limit)
    return [
        ConversationSummary(
            id=c.id, title=c.title, collection_id=c.collection_id,
            created_at=c.created_at.isoformat(),
            updated_at=c.updated_at.isoformat(),
        )
        for c in convs
    ]


@app.get(
    "/api/conversations/{conversation_id}/messages",
    response_model=list[MessageItem],
)
async def list_messages(
    conversation_id: str,
    _: Annotated[str, Depends(require_auth)],
    storage: Annotated[Storage, Depends(get_storage)],
) -> list[MessageItem]:
    conv = await storage.conversations.get(settings.tenant_id, conversation_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    msgs = await storage.messages.list_for_conversation(
        conversation_id, settings.tenant_id
    )
    return [
        MessageItem(
            id=m.id, role=m.role, content=m.content,
            model=m.model, created_at=m.created_at.isoformat(),
        )
        for m in msgs
    ]


# ---------- Chat ----------


@app.post("/api/chat", response_model=ChatReply)
async def chat(
    request: ChatRequest,
    _: Annotated[str, Depends(require_auth)],
    client: Annotated[OllamaClient, Depends(get_model_client)],
    storage: Annotated[Storage, Depends(get_storage)],
) -> ChatReply:
    tenant_id = settings.tenant_id
    conversation_id, collection_id = await _resolve_or_create_conversation(
        storage, tenant_id, request.conversation_id, request.collection_id, request.message
    )
    history = await _build_message_history(
        storage, tenant_id, conversation_id, request.system_prompt, request.message
    )
    rag_context = await _maybe_retrieve(collection_id, request.message)
    messages = _build_messages_with_rag(rag_context, history[:-1], request.message)
    messages.append(ChatMessage(role="user", content=request.message))

    decision = pick_model(request.task_type, request.message)

    try:
        response = await client.chat(
            messages=messages, model=decision.model, temperature=request.temperature
        )
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"Model backend error: {type(e).__name__}: {e}",
        ) from e

    await storage.messages.append(
        conversation_id=conversation_id, tenant_id=tenant_id,
        role="user", content=request.message,
    )
    await storage.messages.append(
        conversation_id=conversation_id, tenant_id=tenant_id,
        role="assistant", content=response.content, model=response.model,
    )

    if rag_context and isinstance(storage, SQLiteStorage):
        await storage.log_retrieval(
            conversation_id=conversation_id,
            tenant_id=tenant_id,
            collection_id=rag_context.collection_id,
            query=request.message,
            top_score=rag_context.extra.get("top_score"),
            chunk_count=len(rag_context.chunks),
            chunk_ids=[c.source_file for c in rag_context.chunks],
        )

    return ChatReply(
        reply=response.content,
        model_used=response.model,
        task_type=decision.task_type,
        routing_reason=decision.reason,
        conversation_id=conversation_id,
        rag_used=rag_context is not None,
        sources=[_chunk_to_source_dict(c) for c in rag_context.chunks] if rag_context else [],
    )


@app.post("/api/chat/stream")
async def chat_stream(
    request: ChatRequest,
    _: Annotated[str, Depends(require_auth)],
    client: Annotated[OllamaClient, Depends(get_model_client)],
    storage: Annotated[Storage, Depends(get_storage)],
) -> StreamingResponse:
    tenant_id = settings.tenant_id
    conversation_id, collection_id = await _resolve_or_create_conversation(
        storage, tenant_id, request.conversation_id, request.collection_id, request.message
    )
    history = await _build_message_history(
        storage, tenant_id, conversation_id, request.system_prompt, request.message
    )
    rag_context = await _maybe_retrieve(collection_id, request.message)
    messages = _build_messages_with_rag(rag_context, history[:-1], request.message)
    messages.append(ChatMessage(role="user", content=request.message))

    decision = pick_model(request.task_type, request.message)

    await storage.messages.append(
        conversation_id=conversation_id, tenant_id=tenant_id,
        role="user", content=request.message,
    )

    async def event_generator() -> AsyncIterator[str]:
        sources = []
        if rag_context:
            sources = [_chunk_to_source_dict(c) for c in rag_context.chunks]
        meta = {
            "conversation_id": conversation_id,
            "model": decision.model,
            "task_type": decision.task_type,
            "routing_reason": decision.reason,
            "rag_used": rag_context is not None,
            "sources": sources,
        }
        yield f"data: {json.dumps(meta)}\n\n"

        accumulated: list[str] = []
        final_model = decision.model
        try:
            async for chunk in client.stream_chat(
                messages=messages, model=decision.model, temperature=request.temperature
            ):
                accumulated.append(chunk.content)
                final_model = chunk.model
                payload = {
                    "content": chunk.content,
                    "model": chunk.model,
                    "done": chunk.done,
                }
                if chunk.finish_reason:
                    payload["finish_reason"] = chunk.finish_reason
                yield f"data: {json.dumps(payload)}\n\n"

            full_reply = "".join(accumulated)
            await storage.messages.append(
                conversation_id=conversation_id, tenant_id=tenant_id,
                role="assistant", content=full_reply, model=final_model,
            )

            if rag_context and isinstance(storage, SQLiteStorage):
                await storage.log_retrieval(
                    conversation_id=conversation_id,
                    tenant_id=tenant_id,
                    collection_id=rag_context.collection_id,
                    query=request.message,
                    top_score=rag_context.extra.get("top_score"),
                    chunk_count=len(rag_context.chunks),
                    chunk_ids=[c.source_file for c in rag_context.chunks],
                )

            yield "data: [DONE]\n\n"
        except Exception as e:
            err = {"error": f"{type(e).__name__}: {e}"}
            yield f"data: {json.dumps(err)}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ---------- Static UI ----------

if ENV_FILE is not None:
    _frontend_dir = ENV_FILE.parent / "apps" / "frontend"
    if _frontend_dir.exists():
        app.mount("/", StaticFiles(directory=str(_frontend_dir), html=True), name="frontend")

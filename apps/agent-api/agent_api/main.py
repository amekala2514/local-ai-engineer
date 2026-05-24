"""Agent API entry point.

Phase A Day 13a: adds conversation delete, rename, and regenerate endpoints
on top of the Day 12 file-upload feature set.
"""

import hmac
import json
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from typing import Annotated, Literal

from fastapi import (
    Cookie,
    Depends,
    FastAPI,
    File,
    Header,
    HTTPException,
    Request,
    Response,
    UploadFile,
)
from fastapi.responses import PlainTextResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from agent_api.auth.session_store import session_store
from agent_api.auth.rate_limit import login_limiter
from agent_api.middleware.security_headers import SecurityHeadersMiddleware
from agent_api.web.fetcher import FetchError, fetch_url as _fetch_url
from agent_api.web.sanitizer import sanitize_response
from agent_api.web.prompt import build_untrusted_url_prompt, build_search_results_prompt
from agent_api.memory.writer import remember_turn_pair
from agent_api.memory.store import search_memory, MemoryHit
from agent_api.memory.prompt import build_memory_prompt
from agent_api.files.generate import to_markdown, to_pdf, sanitize_filename
from agent_api.rag.query_transform import generate_hyde_doc, rewrite_query
from agent_api.ingest.qdrant_store import hybrid_search
from agent_api.observability.tracing import setup_tracing, get_tracer
from agent_api.web.search import SearchError, search as _brave_search
from agent_api.web.rate_limit import check_daily_limit, compute_query_hash
from agent_api.web.validator import validate_url
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
    version="0.9.0",
    lifespan=lifespan,
)

# O2: OpenTelemetry tracing. No-op if tracing_enabled is False; degrades
# silently if Tempo is unreachable — never blocks the app.
setup_tracing(app)

app.add_middleware(SecurityHeadersMiddleware)


# ---------- Auth ----------


def require_auth(
    authorization: Annotated[str | None, Header()] = None,
    session: Annotated[str | None, Cookie(alias=SESSION_COOKIE_NAME)] = None,
) -> str:
    if authorization is not None:
        if not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Authorization must use Bearer scheme")
        token = authorization.removeprefix("Bearer ").strip()
        if not hmac.compare_digest(token, settings.agent_api_token):
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
    title: str | None = Field(default=None, max_length=200)
    collection_id: str | None = Field(default=None, max_length=64)


class PatchConversationRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)


class CreateCollectionRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)


class ChatRequest(BaseModel):
    message: str = Field(
        ...,
        description="The user's message",
        min_length=1,
        max_length=32000,
    )
    task_type: str = Field(default="auto", max_length=32)
    system_prompt: str | None = Field(default=None, max_length=8000)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    conversation_id: str | None = Field(default=None, max_length=64)
    collection_id: str | None = Field(default=None, max_length=64)
    attached_url: str | None = Field(
        default=None,
        max_length=2048,
        description="Optional URL to fetch and include as untrusted reference content",
    )
    search_query: str | None = Field(
        default=None,
        max_length=400,
        description="Optional web search query; top results included as untrusted reference content",
    )


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


async def _maybe_fetch_url(url: str | None) -> dict | None:
    """If a URL is attached, fetch and sanitize it. Returns a context dict or None.

    Returned dict shape:
        {"url": <final url after redirects>, "title": str|None,
         "content": <sanitized text>, "truncated": bool}

    Returns None if no URL is attached. Raises HTTPException(400) on validation
    or fetch failure — the caller propagates this to the client so the user can
    correct the URL.
    """
    if not url:
        return None
    try:
        fetched = await _fetch_url(url)
    except FetchError as e:
        raise HTTPException(status_code=400, detail=f"URL fetch failed: {e}") from e

    result = sanitize_response(fetched.content_type, fetched.body, fetched.encoding)
    return {
        "url": fetched.url,
        "title": result.title,
        "content": result.text,
        "truncated": result.truncated,
    }


async def _maybe_retrieve(
    collection_id: str | None,
    user_message: str,
    client: "OllamaClient | None" = None,
) -> RetrievalContext | None:
    if not collection_id:
        return None
    # Query transformation (Day 24-25). HyDE embeds a hypothetical answer
    # instead of the question (eval: 77% -> 95% hit rate on phase-a). Rewrite
    # is available but off (it regressed hits in the eval). Both degrade to the
    # original query on failure, so retrieval never breaks. HyDE adds one LLM
    # generation of latency per RAG query — visible in /metrics.
    tracer = get_tracer()

    # Query transformation (Day 24-25). HyDE embeds a hypothetical answer.
    query = user_message
    if client is not None:
        if settings.hyde_enabled:
            with tracer.start_as_current_span("hyde_generation") as span:
                span.set_attribute("transform", "hyde")
                span.set_attribute("model", settings.query_transform_model)
                query = await generate_hyde_doc(user_message, client)
                span.set_attribute("transformed", query != user_message)
        elif settings.query_rewrite_enabled:
            with tracer.start_as_current_span("query_rewrite") as span:
                span.set_attribute("transform", "rewrite")
                query = await rewrite_query(user_message, client)

    # Hybrid retrieval (Day 26): dense + BM25 sparse fused with DBSF. Falls back
    # to dense on any error (non-critical: a hybrid failure must not break RAG).
    if settings.hybrid_enabled and collection_id == "phase-a":
        try:
            with tracer.start_as_current_span("retrieve") as span:
                span.set_attribute("mode", "hybrid_dbsf")
                span.set_attribute("collection", settings.hybrid_collection)
                chunks = hybrid_search(
                    settings.hybrid_collection,
                    dense_query_text=query,
                    sparse_query_text=user_message,
                    top_k=5,
                )
                span.set_attribute("result_count", len(chunks))
                if chunks:
                    span.set_attribute("top_score", float(chunks[0].score))
            return RetrievalContext(
                chunks=chunks,
                collection_id=settings.hybrid_collection,
                query=query,
                reason="hybrid_dbsf",
                extra={"top_score": chunks[0].score if chunks else None,
                       "result_count": len(chunks), "hybrid": True},
            )
        except Exception:
            pass  # fall through to dense

    with tracer.start_as_current_span("retrieve") as span:
        span.set_attribute("mode", "dense")
        span.set_attribute("collection", collection_id)
        ctx = await retrieve_for_query(
            query=query,
            collection_id=collection_id,
            top_k=5,
            reason="collection_attached",
        )
        span.set_attribute("result_count", len(ctx.chunks) if ctx else 0)
        return ctx


async def _maybe_retrieve_memory(
    user_message: str,
    current_conversation_id: str | None,
) -> list[MemoryHit] | None:
    """Retrieve relevant past turn-pairs, excluding the current conversation.

    Mirrors _maybe_retrieve (RAG). Returns None when disabled or when nothing
    clears the similarity threshold, so the endpoint's `is not None` check
    matches the RAG/URL/search pattern.
    """
    if not settings.memory_enabled:
        return None
    try:
        hits = search_memory(
            query=user_message,
            tenant_id=settings.tenant_id,
            exclude_conversation_id=current_conversation_id,
            top_k=settings.memory_top_k,
            fetch_k=settings.memory_fetch_k,
            score_threshold=settings.memory_score_threshold,
        )
    except Exception:
        # Memory is a non-critical enhancement: if the vector store is down
        # or retrieval fails, proceed without memory rather than failing the
        # whole chat request. (O2/O3 observability: emit a metric here.)
        return None
    return hits or None


# ---------- Auth endpoints ----------


@app.post("/api/auth/login")
async def login(
    request: LoginRequest,
    response: Response,
    http_request: Request,
) -> dict:
    client_ip = http_request.client.host if http_request.client else "unknown"
    allowed, retry_after = login_limiter.check(client_ip)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail=f"Too many attempts. Try again in {retry_after}s.",
            headers={"Retry-After": str(retry_after)},
        )
    if not hmac.compare_digest(request.token, settings.agent_api_token):
        raise HTTPException(status_code=401, detail="Invalid token")
    login_limiter.reset(client_ip)
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
    """Drop a collection. Idempotent."""
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
    """Upload a file and ingest it into the named collection."""
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty file")

    try:
        saved_path = save_upload(name, file.filename or "upload", content)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    try:
        result = await ingest_file_async(saved_path, name)
    except Exception as e:
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


@app.patch("/api/conversations/{conversation_id}", response_model=ConversationSummary)
async def patch_conversation(
    conversation_id: str,
    request: PatchConversationRequest,
    _: Annotated[str, Depends(require_auth)],
    storage: Annotated[Storage, Depends(get_storage)],
) -> ConversationSummary:
    """Update conversation fields. Currently supports renaming."""
    if request.title is None:
        raise HTTPException(status_code=400, detail="No fields to update")
    ok = await storage.conversations.rename(
        settings.tenant_id, conversation_id, request.title
    )
    if not ok:
        raise HTTPException(status_code=404, detail="Conversation not found")
    conv = await storage.conversations.get(settings.tenant_id, conversation_id)
    return ConversationSummary(
        id=conv.id, title=conv.title, collection_id=conv.collection_id,
        created_at=conv.created_at.isoformat(),
        updated_at=conv.updated_at.isoformat(),
    )


@app.delete("/api/conversations/{conversation_id}", status_code=204)
async def delete_conversation(
    conversation_id: str,
    _: Annotated[str, Depends(require_auth)],
    storage: Annotated[Storage, Depends(get_storage)],
) -> Response:
    """Delete a conversation and all its messages."""
    ok = await storage.conversations.delete(settings.tenant_id, conversation_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return Response(status_code=204)


@app.post("/api/conversations/{conversation_id}/regenerate", response_model=ChatReply)
async def regenerate_last(
    conversation_id: str,
    _: Annotated[str, Depends(require_auth)],
    client: Annotated[OllamaClient, Depends(get_model_client)],
    storage: Annotated[Storage, Depends(get_storage)],
) -> ChatReply:
    """Drop the last assistant message and regenerate it (non-streaming)."""
    tenant_id = settings.tenant_id
    conv = await storage.conversations.get(tenant_id, conversation_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    msgs = await storage.messages.list_for_conversation(conversation_id, tenant_id)
    if len(msgs) < 2 or msgs[-1].role != "assistant":
        raise HTTPException(status_code=400, detail="Nothing to regenerate")

    last_user = None
    for m in reversed(msgs[:-1]):
        if m.role == "user":
            last_user = m
            break
    if last_user is None:
        raise HTTPException(status_code=400, detail="No prior user message found")

    # Delete the last assistant message (and any messages after the user's, just in case)
    await storage.messages.delete_after(conversation_id, tenant_id, last_user.id + 1)

    history = await storage.messages.list_for_conversation(conversation_id, tenant_id)
    history_msgs: list[ChatMessage] = [
        ChatMessage(role=m.role, content=m.content) for m in history
    ]

    rag_context = await _maybe_retrieve(conv.collection_id, last_user.content)
    # Regenerate doesn't re-fetch URLs (the original turn had its web context if any).
    # web_context stays None so the source-construction block below skips URL append.
    web_context = None
    messages = _build_messages_with_rag(rag_context, history_msgs[:-1], last_user.content)
    messages.append(ChatMessage(role="user", content=last_user.content))

    decision = pick_model("auto", last_user.content)

    try:
        response = await client.chat(
            messages=messages, model=decision.model, temperature=0.7
        )
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"Model backend error: {type(e).__name__}: {e}",
        ) from e

    await storage.messages.append(
        conversation_id=conversation_id, tenant_id=tenant_id,
        role="assistant", content=response.content, model=response.model,
    )

    sources = [_chunk_to_source_dict(c) for c in rag_context.chunks] if rag_context else []
    if web_context is not None:
        sources.append({
            "type": "url",
            "url": web_context["url"],
            "title": web_context["title"],
            "truncated": web_context["truncated"],
        })

    return ChatReply(
        reply=response.content,
        model_used=response.model,
        task_type=decision.task_type,
        routing_reason=decision.reason,
        conversation_id=conversation_id,
        rag_used=rag_context is not None,
        sources=sources,
    )


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
    rag_context = await _maybe_retrieve(collection_id, request.message, client)
    memory_context = await _maybe_retrieve_memory(request.message, conversation_id)
    web_context = await _maybe_fetch_url(request.attached_url)
    search_context = await _run_search(storage, request.search_query) if request.search_query else None
    messages = _build_messages_with_rag(rag_context, history[:-1], request.message)
    # Retrieved/external context is prepended as its own system messages so the
    # framing isn't conflated with the trusted system prompt. Ordering is
    # [RAG][memory][URL][search] before the user turn — most-trusted (the user's
    # own docs/past chats) furthest from the user turn, least-trusted (web)
    # closest. _insert_at grows as each source is added.
    _insert_at = 0 if rag_context is None else 1
    if memory_context is not None:
        messages.insert(
            _insert_at,
            ChatMessage(role="system", content=build_memory_prompt(memory_context)),
        )
        _insert_at += 1
    if web_context is not None:
        messages.insert(
            _insert_at,
            ChatMessage(
                role="system",
                content=build_untrusted_url_prompt(web_context["url"], web_context["content"]),
            ),
        )
        _insert_at += 1
    if search_context is not None:
        messages.insert(
            _insert_at,
            ChatMessage(
                role="system",
                content=build_search_results_prompt(search_context["query"], search_context["results"]),
            ),
        )
    messages.append(ChatMessage(role="user", content=request.message))

    decision = pick_model(request.task_type, request.message)

    try:
        with get_tracer().start_as_current_span("model_chat") as _span:
            _span.set_attribute("model", decision.model)
            _span.set_attribute("task_type", decision.task_type)
            response = await client.chat(
                messages=messages, model=decision.model, temperature=request.temperature
            )
            if response.prompt_tokens is not None:
                _span.set_attribute("prompt_tokens", response.prompt_tokens)
            if response.completion_tokens is not None:
                _span.set_attribute("completion_tokens", response.completion_tokens)
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

    sources = [_chunk_to_source_dict(c) for c in rag_context.chunks] if rag_context else []
    if web_context is not None:
        sources.append({
            "type": "url",
            "url": web_context["url"],
            "title": web_context["title"],
            "truncated": web_context["truncated"],
        })
    if search_context is not None:
        for _r in search_context["results"]:
            sources.append({
                "type": "url",
                "url": _r["url"],
                "title": _r["title"],
                "truncated": False,
            })
    if memory_context is not None:
        for _m in memory_context:
            sources.append({
                "type": "memory",
                "user_text": _m.user_text[:200],
                "assistant_text": _m.assistant_text[:200],
                "score": _m.score,
            })

    if isinstance(storage, SQLiteStorage):
        await storage.request_metrics.record(
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            model=response.model,
            task_type=decision.task_type,
            routing_reason=decision.reason,
            rag_used=rag_context is not None,
            url_used=web_context is not None,
            search_used=search_context is not None,
            memory_used=memory_context is not None,
            status="completed",
            prompt_tokens=response.prompt_tokens,
            completion_tokens=response.completion_tokens,
            duration_ms=(response.total_duration_ns // 1_000_000)
            if response.total_duration_ns is not None else None,
        )
        await remember_turn_pair(
            storage=storage,
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            turn_index=0,
            user_text=request.message,
            assistant_text=response.content,
        )

    return ChatReply(
        reply=response.content,
        model_used=response.model,
        task_type=decision.task_type,
        routing_reason=decision.reason,
        conversation_id=conversation_id,
        rag_used=rag_context is not None,
        sources=sources,
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
    rag_context = await _maybe_retrieve(collection_id, request.message, client)
    memory_context = await _maybe_retrieve_memory(request.message, conversation_id)
    web_context = await _maybe_fetch_url(request.attached_url)
    search_context = await _run_search(storage, request.search_query) if request.search_query else None
    messages = _build_messages_with_rag(rag_context, history[:-1], request.message)
    # Ordering [RAG][memory][URL][search] before the user turn (see chat()).
    _insert_at = 0 if rag_context is None else 1
    if memory_context is not None:
        messages.insert(
            _insert_at,
            ChatMessage(role="system", content=build_memory_prompt(memory_context)),
        )
        _insert_at += 1
    if web_context is not None:
        messages.insert(
            _insert_at,
            ChatMessage(
                role="system",
                content=build_untrusted_url_prompt(web_context["url"], web_context["content"]),
            ),
        )
        _insert_at += 1
    if search_context is not None:
        messages.insert(
            _insert_at,
            ChatMessage(
                role="system",
                content=build_search_results_prompt(search_context["query"], search_context["results"]),
            ),
        )
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
        if web_context is not None:
            sources.append({
                "type": "url",
                "url": web_context["url"],
                "title": web_context["title"],
                "truncated": web_context["truncated"],
            })
        if search_context is not None:
            for _r in search_context["results"]:
                sources.append({
                    "type": "url",
                    "url": _r["url"],
                    "title": _r["title"],
                    "truncated": False,
                })
        if memory_context is not None:
            for _m in memory_context:
                sources.append({
                    "type": "memory",
                    "user_text": _m.user_text[:200],
                    "assistant_text": _m.assistant_text[:200],
                    "score": _m.score,
                })
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
        final_prompt_tokens: int | None = None
        final_completion_tokens: int | None = None
        final_duration_ns: int | None = None
        try:
            async for chunk in client.stream_chat(
                messages=messages, model=decision.model, temperature=request.temperature
            ):
                accumulated.append(chunk.content)
                final_model = chunk.model
                if chunk.done:
                    final_prompt_tokens = chunk.prompt_tokens
                    final_completion_tokens = chunk.completion_tokens
                    final_duration_ns = chunk.total_duration_ns
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

            if isinstance(storage, SQLiteStorage):
                await storage.request_metrics.record(
                    tenant_id=tenant_id,
                    conversation_id=conversation_id,
                    model=final_model,
                    task_type=decision.task_type,
                    routing_reason=decision.reason,
                    rag_used=rag_context is not None,
                    url_used=web_context is not None,
                    search_used=search_context is not None,
                    memory_used=memory_context is not None,
                    status="completed",
                    prompt_tokens=final_prompt_tokens,
                    completion_tokens=final_completion_tokens,
                    duration_ms=(final_duration_ns // 1_000_000)
                    if final_duration_ns is not None else None,
                )
                await remember_turn_pair(
                    storage=storage,
                    tenant_id=tenant_id,
                    conversation_id=conversation_id,
                    turn_index=0,
                    user_text=request.message,
                    assistant_text=full_reply,
                )

            yield "data: [DONE]\n\n"
        except Exception as e:
            if isinstance(storage, SQLiteStorage):
                try:
                    await storage.request_metrics.record(
                        tenant_id=tenant_id,
                        conversation_id=conversation_id,
                        model=decision.model,
                        task_type=decision.task_type,
                        routing_reason=decision.reason,
                        rag_used=rag_context is not None,
                        url_used=web_context is not None,
                        search_used=search_context is not None,
                        status="error",
                    )
                except Exception:
                    pass
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


# ---------- Day 16a: URL fetch endpoint ----------


class FetchUrlRequest(BaseModel):
    url: str = Field(..., min_length=1, max_length=2048)


class FetchUrlResponse(BaseModel):
    url: str
    title: str | None
    content: str
    truncated: bool
    content_type: str


@app.post("/api/fetch_url", response_model=FetchUrlResponse)
async def fetch_url_endpoint(
    request: FetchUrlRequest,
    _: Annotated[str, Depends(require_auth)],
) -> FetchUrlResponse:
    """Fetch a user-provided URL, sanitize it, and return clean text.

    This endpoint is the sole entry point for web content in Phase B6.
    The returned content is intended for the LLM to read as untrusted
    reference material — the chat endpoint frames it accordingly.
    """
    # Up-front validation rejects obviously-bad URLs without any network calls
    pre = validate_url(request.url, resolve_dns=False)
    if not pre.valid:
        raise HTTPException(status_code=400, detail=pre.reason)

    try:
        fetched = await _fetch_url(request.url)
    except FetchError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    result = sanitize_response(fetched.content_type, fetched.body, fetched.encoding)

    return FetchUrlResponse(
        url=fetched.url,
        title=result.title,
        content=result.text,
        truncated=result.truncated,
        content_type=fetched.content_type,
    )


# ---------- Day 18a: Search endpoint ----------


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=400)


class SearchResultModel(BaseModel):
    title: str
    url: str
    description: str


class SearchResponseModel(BaseModel):
    query: str
    results: list[SearchResultModel]
    current_count: int  # number of queries already made in the last 24h (post-this-call)
    limit: int          # configured daily limit


async def _run_search(storage: Storage, query: str) -> dict:
    """Run a rate-limited, audited web search. Shared by /api/search and chat.

    Returns {'query', 'results': [{title,url,description}...], 'current_count', 'limit'}.

    Raises HTTPException on: search disabled (503), wrong backend (503),
    rate limit (429), or Brave error (502). Callers propagate these so the
    user sees a clear error rather than a silently search-less response.
    """
    if not settings.search_enabled:
        raise HTTPException(status_code=503, detail="Search is disabled (SEARCH_ENABLED=false)")
    if not isinstance(storage, SQLiteStorage):
        raise HTTPException(status_code=503, detail="Search requires SQLite storage backend")

    tenant_id = settings.tenant_id
    query = query.strip()
    query_hash = compute_query_hash(query)

    decision = await check_daily_limit(storage.search_queries, tenant_id)
    if not decision.allow:
        raise HTTPException(status_code=429, detail=decision.reason or "Rate limit reached")

    try:
        result = await _brave_search(query)
    except SearchError as e:
        await storage.search_queries.record(
            tenant_id=tenant_id, query=query, query_hash=query_hash,
            result_count=0, status="error", error=str(e),
        )
        raise HTTPException(status_code=502, detail=f"Search failed: {e}") from e

    await storage.search_queries.record(
        tenant_id=tenant_id, query=query, query_hash=query_hash,
        result_count=len(result.results), status="ok", error=None,
    )

    return {
        "query": result.query,
        "results": [
            {"title": r.title, "url": r.url, "description": r.description}
            for r in result.results
        ],
        "current_count": decision.current_count + 1,
        "limit": decision.limit,
    }


@app.post("/api/search", response_model=SearchResponseModel)
async def search_endpoint(
    request: SearchRequest,
    _: Annotated[str, Depends(require_auth)],
    storage: Annotated[Storage, Depends(get_storage)],
) -> SearchResponseModel:
    """Run a web search and return sanitized snippets.

    Rate limited per tenant by SEARCH_DAILY_LIMIT. Results are NOT sent to
    the LLM by this endpoint — callers decide how to use them. Chat
    integration calls the shared _run_search helper directly.
    """
    data = await _run_search(storage, request.query)
    return SearchResponseModel(
        query=data["query"],
        results=[
            SearchResultModel(**r) for r in data["results"]
        ],
        current_count=data["current_count"],
        limit=data["limit"],
    )


# ---------- Day 19/O1: Prometheus metrics endpoint ----------


def _prom_labels(row: dict) -> str:
    """Build a Prometheus label set from an aggregate row."""
    return (
        f'model="{row["model"]}",'
        f'status="{row["status"]}",'
        f'rag="{str(row["rag_used"]).lower()}",'
        f'url="{str(row["url_used"]).lower()}",'
        f'search="{str(row["search_used"]).lower()}",'
        f'memory="{str(row["memory_used"]).lower()}"'
    )


def format_prometheus(aggregates: list[dict]) -> str:
    """Render aggregate rows as Prometheus text exposition format.

    Emits all-time counters (the table is the source of truth); Prometheus
    and Grafana compute rates/windows from these.
    """
    lines: list[str] = []

    lines.append("# HELP agent_chat_requests_total Total chat requests recorded.")
    lines.append("# TYPE agent_chat_requests_total counter")
    for row in aggregates:
        lines.append(f'agent_chat_requests_total{{{_prom_labels(row)}}} {row["request_count"]}')

    lines.append("# HELP agent_prompt_tokens_total Total prompt (input) tokens.")
    lines.append("# TYPE agent_prompt_tokens_total counter")
    for row in aggregates:
        lines.append(f'agent_prompt_tokens_total{{{_prom_labels(row)}}} {row["total_prompt_tokens"]}')

    lines.append("# HELP agent_completion_tokens_total Total completion (output) tokens.")
    lines.append("# TYPE agent_completion_tokens_total counter")
    for row in aggregates:
        lines.append(f'agent_completion_tokens_total{{{_prom_labels(row)}}} {row["total_completion_tokens"]}')

    lines.append("# HELP agent_request_duration_ms_avg Average request duration (ms) per group.")
    lines.append("# TYPE agent_request_duration_ms_avg gauge")
    for row in aggregates:
        if row["avg_duration_ms"] is not None:
            lines.append(f'agent_request_duration_ms_avg{{{_prom_labels(row)}}} {row["avg_duration_ms"]:.1f}')

    return "\n".join(lines) + "\n"


@app.get("/metrics", response_class=PlainTextResponse)
async def metrics_endpoint(
    storage: Annotated[Storage, Depends(get_storage)],
) -> str:
    """Prometheus metrics endpoint. All-time counters from request_metrics.

    Unauthenticated by convention (Prometheus scrapes it); safe on a local
    single-user bind. Returns empty metric families if no SQLite backend.
    """
    if not isinstance(storage, SQLiteStorage):
        return "# storage backend does not support metrics\n"
    epoch = datetime.fromtimestamp(0, tz=timezone.utc)
    aggregates = await storage.request_metrics.aggregate_since(settings.tenant_id, epoch)
    return format_prometheus(aggregates)


# ---------- File generation ----------

class FileGenerateRequest(BaseModel):
    content: str = Field(..., max_length=100_000)
    format: Literal["markdown", "pdf"]
    filename: str | None = Field(default=None, max_length=120)


@app.post("/api/files/generate")
async def generate_file(
    request: FileGenerateRequest,
    _: Annotated[str, Depends(require_auth)],
) -> Response:
    """Generate an ephemeral downloadable file (Markdown or PDF) from content.

    The content is the user's own (a chat response or requested text); it is
    rendered and returned in-request, never stored. The filename is sanitized
    to a safe basename to prevent path tricks in the Content-Disposition header.
    """
    if request.format == "markdown":
        data = to_markdown(request.content)
        media_type = "text/markdown; charset=utf-8"
        fname = sanitize_filename(request.filename, "document", "md")
    else:
        data = to_pdf(request.content, title=request.filename or "Document")
        media_type = "application/pdf"
        fname = sanitize_filename(request.filename, "document", "pdf")
    return Response(
        content=data,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


# ---------- Static UI ----------

if ENV_FILE is not None:
    _frontend_dir = ENV_FILE.parent / "apps" / "frontend"
    if _frontend_dir.exists():
        app.mount("/", StaticFiles(directory=str(_frontend_dir), html=True), name="frontend")

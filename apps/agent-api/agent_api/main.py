"""Agent API entry point.

Phase A Day 8: serves a static chat UI, supports cookie-based auth for
the browser and bearer-token auth for CLI clients.
"""

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import (
    Cookie,
    Depends,
    FastAPI,
    Header,
    HTTPException,
    Response,
)
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from agent_api.auth.session_store import session_store
from agent_api.models.base import ChatMessage
from agent_api.models.ollama import OllamaClient
from agent_api.models.router import pick_model
from agent_api.settings import ENV_FILE, settings
from agent_api.storage.factory import make_storage
from agent_api.storage.interfaces import Storage


# ---------- Constants ----------

SESSION_COOKIE_NAME = "session"


# ---------- Module state ----------

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
    version="0.5.0",
    lifespan=lifespan,
)


# ---------- Auth ----------


def require_auth(
    authorization: Annotated[str | None, Header()] = None,
    session: Annotated[str | None, Cookie(alias=SESSION_COOKIE_NAME)] = None,
) -> str:
    """Accept either a bearer token (CLI) or a session cookie (browser).

    Returns a string describing the auth mode used. Raises 401 if neither
    method validates.
    """
    # Path 1: bearer token
    if authorization is not None:
        if not authorization.startswith("Bearer "):
            raise HTTPException(
                status_code=401, detail="Authorization must use Bearer scheme"
            )
        token = authorization.removeprefix("Bearer ").strip()
        if token != settings.agent_api_token:
            raise HTTPException(status_code=401, detail="Invalid token")
        return "bearer"

    # Path 2: session cookie
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


class ChatRequest(BaseModel):
    message: str = Field(..., description="The user's message")
    task_type: str = Field(default="general")
    system_prompt: str | None = Field(default=None)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    conversation_id: str | None = Field(default=None)


class ChatReply(BaseModel):
    reply: str
    model_used: str
    task_type: str
    conversation_id: str


class ConversationSummary(BaseModel):
    id: str
    title: str | None
    created_at: str
    updated_at: str


class MessageItem(BaseModel):
    id: int
    role: str
    content: str
    model: str | None
    created_at: str


class AvailableModels(BaseModel):
    general: str
    code: str
    code_heavy: str


# ---------- Helpers ----------


async def _resolve_or_create_conversation(
    storage: Storage,
    tenant_id: str,
    conversation_id: str | None,
    first_message_preview: str,
) -> str:
    if conversation_id is not None:
        existing = await storage.conversations.get(tenant_id, conversation_id)
        if existing is None:
            raise HTTPException(
                status_code=404,
                detail=f"Conversation {conversation_id} not found",
            )
        return existing.id
    title = first_message_preview.strip()[:60]
    new_conv = await storage.conversations.create(tenant_id, title=title)
    return new_conv.id


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


# ---------- Auth endpoints ----------


@app.post("/api/auth/login")
async def login(request: LoginRequest, response: Response) -> dict:
    """Exchange a bearer token for a session cookie.

    This is the browser-facing login endpoint. The token submitted here
    must match settings.agent_api_token. On success, sets an HttpOnly
    cookie and returns success metadata.
    """
    if request.token != settings.agent_api_token:
        raise HTTPException(status_code=401, detail="Invalid token")

    new_session = session_store.create()
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=new_session.id,
        httponly=True,
        samesite="strict",
        secure=False,  # Set True when serving over HTTPS in production
        max_age=int((new_session.expires_at - new_session.created_at).total_seconds()),
        path="/",
    )
    return {"ok": True, "expires_at": new_session.expires_at.isoformat()}


@app.post("/api/auth/logout")
async def logout(
    response: Response,
    session: Annotated[str | None, Cookie(alias=SESSION_COOKIE_NAME)] = None,
) -> dict:
    """Invalidate the current session and clear the cookie."""
    if session is not None:
        session_store.delete(session)
    response.delete_cookie(key=SESSION_COOKIE_NAME, path="/")
    return {"ok": True}


@app.get("/api/auth/me")
async def me(
    auth_mode: Annotated[str, Depends(require_auth)],
) -> dict:
    """Confirm the current request is authenticated. Used by the UI on load."""
    return {"authenticated": True, "auth_mode": auth_mode}


# ---------- Core endpoints ----------


@app.get("/api/health")
async def health() -> dict:
    """Unauthenticated health check."""
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


@app.get("/api/whoami")
async def whoami(
    _: Annotated[str, Depends(require_auth)],
) -> dict:
    return {
        "tenant_id": settings.tenant_id,
        "storage_backend": settings.storage_backend,
        "models": {
            "general": settings.model_general,
            "code": settings.model_code,
            "code_heavy": settings.model_code_heavy,
        },
    }


@app.get("/api/models", response_model=AvailableModels)
async def list_models(
    _: Annotated[str, Depends(require_auth)],
) -> AvailableModels:
    return AvailableModels(
        general=settings.model_general,
        code=settings.model_code,
        code_heavy=settings.model_code_heavy,
    )


@app.post("/api/chat", response_model=ChatReply)
async def chat(
    request: ChatRequest,
    _: Annotated[str, Depends(require_auth)],
    client: Annotated[OllamaClient, Depends(get_model_client)],
    storage: Annotated[Storage, Depends(get_storage)],
) -> ChatReply:
    tenant_id = settings.tenant_id
    conversation_id = await _resolve_or_create_conversation(
        storage, tenant_id, request.conversation_id, request.message
    )
    messages = await _build_message_history(
        storage, tenant_id, conversation_id, request.system_prompt, request.message
    )
    model = pick_model(request.task_type)

    try:
        response = await client.chat(
            messages=messages, model=model, temperature=request.temperature
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

    return ChatReply(
        reply=response.content,
        model_used=response.model,
        task_type=request.task_type,
        conversation_id=conversation_id,
    )


@app.post("/api/chat/stream")
async def chat_stream(
    request: ChatRequest,
    _: Annotated[str, Depends(require_auth)],
    client: Annotated[OllamaClient, Depends(get_model_client)],
    storage: Annotated[Storage, Depends(get_storage)],
) -> StreamingResponse:
    tenant_id = settings.tenant_id
    conversation_id = await _resolve_or_create_conversation(
        storage, tenant_id, request.conversation_id, request.message
    )
    messages = await _build_message_history(
        storage, tenant_id, conversation_id, request.system_prompt, request.message
    )
    model = pick_model(request.task_type)

    await storage.messages.append(
        conversation_id=conversation_id, tenant_id=tenant_id,
        role="user", content=request.message,
    )

    async def event_generator() -> AsyncIterator[str]:
        yield f"data: {json.dumps({'conversation_id': conversation_id, 'model': model})}\n\n"
        accumulated: list[str] = []
        final_model = model
        try:
            async for chunk in client.stream_chat(
                messages=messages, model=model, temperature=request.temperature
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


@app.get("/api/conversations", response_model=list[ConversationSummary])
async def list_conversations(
    _: Annotated[str, Depends(require_auth)],
    storage: Annotated[Storage, Depends(get_storage)],
    limit: int = 50,
) -> list[ConversationSummary]:
    convs = await storage.conversations.list(settings.tenant_id, limit=limit)
    return [
        ConversationSummary(
            id=c.id, title=c.title,
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


# ---------- Static UI ----------

if ENV_FILE is not None:
    _frontend_dir = ENV_FILE.parent / "apps" / "frontend"
    if _frontend_dir.exists():
        app.mount("/", StaticFiles(directory=str(_frontend_dir), html=True), name="frontend")

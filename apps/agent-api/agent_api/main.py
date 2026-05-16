"""Agent API entry point.

Phase 1, Day 7: persistent conversations with SQLite storage.
"""

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from agent_api.models.base import ChatMessage
from agent_api.models.ollama import OllamaClient
from agent_api.models.router import pick_model
from agent_api.settings import settings
from agent_api.storage.factory import make_storage
from agent_api.storage.interfaces import Storage


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
    version="0.4.0",
    lifespan=lifespan,
)


def require_bearer_token(
    authorization: Annotated[str | None, Header()] = None,
) -> str:
    if authorization is None:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401, detail="Authorization must use Bearer scheme"
        )
    token = authorization.removeprefix("Bearer ").strip()
    if token != settings.agent_api_token:
        raise HTTPException(status_code=401, detail="Invalid token")
    return token


def get_model_client() -> OllamaClient:
    if _model_client is None:
        raise HTTPException(status_code=503, detail="Model client not initialized")
    return _model_client


def get_storage() -> Storage:
    if _storage is None:
        raise HTTPException(status_code=503, detail="Storage not initialized")
    return _storage


# ---------- Schemas ----------


class ChatRequest(BaseModel):
    message: str = Field(..., description="The user's message")
    task_type: str = Field(default="general")
    system_prompt: str | None = Field(default=None)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    conversation_id: str | None = Field(
        default=None,
        description="If provided, continues an existing conversation. "
                    "If omitted, a new conversation is created.",
    )


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


# ---------- Helpers ----------


async def _resolve_or_create_conversation(
    storage: Storage,
    tenant_id: str,
    conversation_id: str | None,
    first_message_preview: str,
) -> str:
    """Return a valid conversation_id, creating a new one if needed."""
    if conversation_id is not None:
        existing = await storage.conversations.get(tenant_id, conversation_id)
        if existing is None:
            raise HTTPException(
                status_code=404,
                detail=f"Conversation {conversation_id} not found",
            )
        return existing.id
    # Use the first 60 chars of the user's message as a title
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
    """Construct the full message list to send to the model."""
    history = await storage.messages.list_for_conversation(conversation_id, tenant_id)

    messages: list[ChatMessage] = []
    if system_prompt:
        messages.append(ChatMessage(role="system", content=system_prompt))
    for m in history:
        messages.append(ChatMessage(role=m.role, content=m.content))
    messages.append(ChatMessage(role="user", content=new_user_message))
    return messages


# ---------- Endpoints ----------


@app.get("/health")
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


@app.get("/whoami")
async def whoami(
    _: Annotated[str, Depends(require_bearer_token)],
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


@app.post("/chat", response_model=ChatReply)
async def chat(
    request: ChatRequest,
    _: Annotated[str, Depends(require_bearer_token)],
    client: Annotated[OllamaClient, Depends(get_model_client)],
    storage: Annotated[Storage, Depends(get_storage)],
) -> ChatReply:
    tenant_id = settings.tenant_id
    conversation_id = await _resolve_or_create_conversation(
        storage, tenant_id, request.conversation_id, request.message
    )

    messages = await _build_message_history(
        storage, tenant_id, conversation_id,
        request.system_prompt, request.message,
    )

    model = pick_model(request.task_type)

    try:
        response = await client.chat(
            messages=messages,
            model=model,
            temperature=request.temperature,
        )
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"Model backend error: {type(e).__name__}: {e}",
        ) from e

    # Persist both sides of the exchange
    await storage.messages.append(
        conversation_id=conversation_id,
        tenant_id=tenant_id,
        role="user",
        content=request.message,
    )
    await storage.messages.append(
        conversation_id=conversation_id,
        tenant_id=tenant_id,
        role="assistant",
        content=response.content,
        model=response.model,
    )

    return ChatReply(
        reply=response.content,
        model_used=response.model,
        task_type=request.task_type,
        conversation_id=conversation_id,
    )


@app.post("/chat/stream")
async def chat_stream(
    request: ChatRequest,
    _: Annotated[str, Depends(require_bearer_token)],
    client: Annotated[OllamaClient, Depends(get_model_client)],
    storage: Annotated[Storage, Depends(get_storage)],
) -> StreamingResponse:
    tenant_id = settings.tenant_id
    conversation_id = await _resolve_or_create_conversation(
        storage, tenant_id, request.conversation_id, request.message
    )

    messages = await _build_message_history(
        storage, tenant_id, conversation_id,
        request.system_prompt, request.message,
    )

    model = pick_model(request.task_type)

    # Persist user message before streaming starts
    await storage.messages.append(
        conversation_id=conversation_id,
        tenant_id=tenant_id,
        role="user",
        content=request.message,
    )

    async def event_generator() -> AsyncIterator[str]:
        # Send the conversation_id first so the client knows it
        yield f"data: {json.dumps({'conversation_id': conversation_id})}\n\n"

        accumulated = []
        final_model = model
        try:
            async for chunk in client.stream_chat(
                messages=messages,
                model=model,
                temperature=request.temperature,
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

            # Persist assistant message after streaming completes
            full_reply = "".join(accumulated)
            await storage.messages.append(
                conversation_id=conversation_id,
                tenant_id=tenant_id,
                role="assistant",
                content=full_reply,
                model=final_model,
            )
            yield "data: [DONE]\n\n"
        except Exception as e:
            error_payload = {"error": f"{type(e).__name__}: {e}"}
            yield f"data: {json.dumps(error_payload)}\n\n"
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


@app.get("/conversations", response_model=list[ConversationSummary])
async def list_conversations(
    _: Annotated[str, Depends(require_bearer_token)],
    storage: Annotated[Storage, Depends(get_storage)],
    limit: int = 50,
) -> list[ConversationSummary]:
    convs = await storage.conversations.list(settings.tenant_id, limit=limit)
    return [
        ConversationSummary(
            id=c.id,
            title=c.title,
            created_at=c.created_at.isoformat(),
            updated_at=c.updated_at.isoformat(),
        )
        for c in convs
    ]


@app.get(
    "/conversations/{conversation_id}/messages",
    response_model=list[MessageItem],
)
async def list_messages(
    conversation_id: str,
    _: Annotated[str, Depends(require_bearer_token)],
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
            id=m.id,
            role=m.role,
            content=m.content,
            model=m.model,
            created_at=m.created_at.isoformat(),
        )
        for m in msgs
    ]

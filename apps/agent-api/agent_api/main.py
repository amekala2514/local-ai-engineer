"""Agent API entry point.

Phase 1, Day 6: streaming chat endpoint added.
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


_model_client: OllamaClient | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _model_client
    _model_client = OllamaClient(host=settings.ollama_host)
    yield
    await _model_client.close()


app = FastAPI(
    title="Local AI Engineering Assistant",
    description="Agent API for the local-ai-engineer project",
    version="0.3.0",
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


class ChatRequest(BaseModel):
    message: str = Field(..., description="The user's message")
    task_type: str = Field(default="general")
    system_prompt: str | None = Field(default=None)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)


class ChatReply(BaseModel):
    reply: str
    model_used: str
    task_type: str


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
) -> ChatReply:
    """Non-streaming chat. Waits for the full response, then returns it."""
    model = pick_model(request.task_type)
    messages: list[ChatMessage] = []
    if request.system_prompt:
        messages.append(ChatMessage(role="system", content=request.system_prompt))
    messages.append(ChatMessage(role="user", content=request.message))

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

    return ChatReply(
        reply=response.content,
        model_used=response.model,
        task_type=request.task_type,
    )


@app.post("/chat/stream")
async def chat_stream(
    request: ChatRequest,
    _: Annotated[str, Depends(require_bearer_token)],
    client: Annotated[OllamaClient, Depends(get_model_client)],
) -> StreamingResponse:
    """Streaming chat using Server-Sent Events.

    Each event is a JSON object on a single line, prefixed with 'data: '.
    The stream ends with 'data: [DONE]'.
    """
    model = pick_model(request.task_type)
    messages: list[ChatMessage] = []
    if request.system_prompt:
        messages.append(ChatMessage(role="system", content=request.system_prompt))
    messages.append(ChatMessage(role="user", content=request.message))

    async def event_generator() -> AsyncIterator[str]:
        try:
            async for chunk in client.stream_chat(
                messages=messages,
                model=model,
                temperature=request.temperature,
            ):
                payload = {
                    "content": chunk.content,
                    "model": chunk.model,
                    "done": chunk.done,
                }
                if chunk.finish_reason:
                    payload["finish_reason"] = chunk.finish_reason
                yield f"data: {json.dumps(payload)}\n\n"
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
            "X-Accel-Buffering": "no",  # Disable nginx buffering if behind a proxy
        },
    )

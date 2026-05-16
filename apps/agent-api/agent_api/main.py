"""Agent API entry point.

Phase 1, Day 5: minimal chat endpoint that routes to Ollama.
"""

from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from agent_api.models.base import ChatMessage
from agent_api.models.ollama import OllamaClient
from agent_api.models.router import pick_model
from agent_api.settings import settings


# Single shared model client. Created on app startup, closed on shutdown.
_model_client: OllamaClient | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage the lifecycle of shared resources."""
    global _model_client
    _model_client = OllamaClient(host=settings.ollama_host)
    yield
    await _model_client.close()


app = FastAPI(
    title="Local AI Engineering Assistant",
    description="Agent API for the local-ai-engineer project",
    version="0.2.0",
    lifespan=lifespan,
)


def require_bearer_token(
    authorization: Annotated[str | None, Header()] = None,
) -> str:
    """FastAPI dependency enforcing bearer-token auth."""
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
    """FastAPI dependency providing the shared model client."""
    if _model_client is None:
        raise HTTPException(status_code=503, detail="Model client not initialized")
    return _model_client


# ---------- Request and response schemas ----------


class ChatRequest(BaseModel):
    """Body of a /chat request."""

    message: str = Field(..., description="The user's message")
    task_type: str = Field(
        default="general",
        description="One of: general, code, code_heavy",
    )
    system_prompt: str | None = Field(
        default=None,
        description="Optional system message to prepend",
    )
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)


class ChatReply(BaseModel):
    """Response body for /chat."""

    reply: str
    model_used: str
    task_type: str


# ---------- Endpoints ----------


@app.get("/health")
async def health() -> dict:
    """Unauthenticated health check.

    Reports both the API's own health and the model backend's health.
    """
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
    """Authenticated endpoint that confirms config is loaded correctly."""
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
    """Send a message to the assistant and get a reply.

    Routes to the appropriate model based on task_type.
    """
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
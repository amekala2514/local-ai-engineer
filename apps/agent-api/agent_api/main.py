"""Agent API entry point.

Phase 1, Day 4: minimal scaffold with a health-check endpoint and 
bearer-token authentication. No model integration yet.
"""

from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException

from agent_api.settings import settings


app = FastAPI(
    title="Local AI Engineering Assistant",
    description="Agent API for the local-ai-engineer project",
    version="0.1.0",
)


def require_bearer_token(
    authorization: Annotated[str | None, Header()] = None,
) -> str:
    """FastAPI dependency that enforces bearer-token auth.

    Returns the token string on success; raises 401 on failure.
    """
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


@app.get("/health")
async def health() -> dict:
    """Unauthenticated health check.

    Used by Docker, load balancers, and monitoring. Intentionally does
    not require auth so infrastructure can verify the service is up.
    """
    return {
        "status": "ok",
        "service": "agent-api",
        "version": app.version,
        "tenant_id": settings.tenant_id,
    }


@app.get("/whoami")
async def whoami(
    _: Annotated[str, Depends(require_bearer_token)],
) -> dict:
    """Authenticated endpoint - confirms the bearer token is working.

    Returns a summary of how this instance is configured.
    """
    return {
        "tenant_id": settings.tenant_id,
        "storage_backend": settings.storage_backend,
        "models": {
            "general": settings.model_general,
            "code": settings.model_code,
            "code_heavy": settings.model_code_heavy,
        },
    }

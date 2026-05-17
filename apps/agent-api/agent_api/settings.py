"""Application settings loaded from environment variables.

This is the single source of truth for configuration. Locally, values
come from .env at the project root. In cloud, they come from AWS Secrets
Manager / GCP Secret Manager via the runtime's environment.
"""

import os
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _find_env_file() -> Path | None:
    """Find .env at the project root, identified by the .git directory."""
    override = os.environ.get("AGENT_API_ENV_FILE")
    if override:
        path = Path(override)
        return path if path.exists() else None

    current = Path.cwd().resolve()
    for parent in [current, *current.parents]:
        if (parent / ".git").exists():
            env = parent / ".env"
            return env if env.exists() else None
    return None


ENV_FILE = _find_env_file()


class Settings(BaseSettings):
    """Typed application configuration."""

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE) if ENV_FILE else None,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    agent_api_token: str = Field(default="dev-token-change-me")
    agent_api_port: int = Field(default=8000)
    agent_api_host: str = Field(default="0.0.0.0")
    tenant_id: str = Field(default="local")
    ollama_host: str = Field(default="http://localhost:11434")
    storage_backend: str = Field(default="sqlite")
    sqlite_path: str = Field(default="./data/agent.sqlite")
    vector_backend: str = Field(default="qdrant_local")
    qdrant_host: str = Field(default="localhost")
    qdrant_port: int = Field(default=6333)
    model_general: str = Field(default="llama3.1:8b")
    model_code: str = Field(default="qwen2.5-coder:14b")
    model_code_heavy: str = Field(default="deepseek-coder-v2:16b")
    model_embedding: str = Field(default="nomic-embed-text")
    rerank_enabled: bool = Field(default=True)
    reranker_model: str = Field(default="BAAI/bge-reranker-base")
    reranker_fp16: bool = Field(default=True)
    log_level: str = Field(default="INFO")
    log_format: str = Field(default="json")


settings = Settings()

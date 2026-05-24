"""Application settings loaded from environment variables.

This is the single source of truth for configuration. Locally, values
come from .env at the project root. In cloud, they come from AWS Secrets
Manager / GCP Secret Manager via the runtime's environment.
"""

import os
from pathlib import Path

from pydantic import Field, model_validator
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
    # Day 18: Brave Search
    brave_api_key: str = Field(default="")
    search_enabled: bool = Field(default=False)
    search_daily_limit: int = Field(default=50)
    search_idempotency_ttl_seconds: int = Field(default=60)
    search_result_count: int = Field(default=5)
    search_timeout_seconds: int = Field(default=8)
    # Day 21: Memory (cross-conversation recall)
    memory_enabled: bool = Field(default=True)
    # Smoke test (Day 22, minimal data) suggests 0.70 may be conservative:
    # related-but-differently-phrased queries scored 0.57-0.63 (would miss),
    # while unrelated scored 0.40-0.42 — clear separation gives headroom.
    # Revisit toward 0.60-0.65 after accumulating real conversation data.
    memory_score_threshold: float = Field(default=0.70)
    memory_top_k: int = Field(default=3)
    memory_fetch_k: int = Field(default=10)
    # Day 24-25: Query transformation (retrieval). Off by default — opt-in
    # experiments, validated via the eval harness before any default-on.
    query_rewrite_enabled: bool = Field(default=False)
    hyde_enabled: bool = Field(default=True)  # Day 24-25: eval-validated (77%->95% on phase-a)
    query_transform_model: str = Field(default="llama3.1:8b")
    # Day 26: Hybrid search (dense + BM25 sparse, server-side RRF fusion)
    hybrid_enabled: bool = Field(default=True)  # Day 26: eval-validated (DBSF, 0 wrong-source misses on 22)
    hybrid_collection: str = Field(default="phase-a-hybrid")
    bm25_idf_path: str = Field(default="data/vector/bm25_idf.json")

    @model_validator(mode="after")
    def _resolve_relative_paths(self) -> "Settings":
        """Resolve relative sqlite_path against the .env file's directory.

        Prevents the bug where the database file lands in different
        locations depending on which CWD uvicorn or a script starts from.
        Absolute paths are left alone.
        """
        sqlite = Path(self.sqlite_path)
        if not sqlite.is_absolute() and ENV_FILE is not None:
            self.sqlite_path = str((ENV_FILE.parent / sqlite).resolve())
        idf = Path(self.bm25_idf_path)
        if not idf.is_absolute() and ENV_FILE is not None:
            self.bm25_idf_path = str((ENV_FILE.parent / idf).resolve())
        return self


settings = Settings()

"""Embedder that calls Ollama's embedding endpoint.

Uses the model configured in settings (nomic-embed-text by default).
Returns 768-dim vectors.
"""

import httpx

from agent_api.settings import settings


_client: httpx.Client | None = None


def _get_client() -> httpx.Client:
    global _client
    if _client is None:
        host = settings.ollama_host
        if "host.docker.internal" in host:
            host = host.replace("host.docker.internal", "localhost")
        _client = httpx.Client(base_url=host, timeout=60.0)
    return _client


def embed(text: str, model: str | None = None) -> list[float]:
    """Embed a single piece of text. Returns the embedding vector."""
    model_name = model or settings.model_embedding
    client = _get_client()
    response = client.post(
        "/api/embeddings",
        json={"model": model_name, "prompt": text},
    )
    if response.status_code != 200:
        # Surface useful context before letting the error propagate
        text_preview = text[:200].replace("\n", " ")
        text_chars = len(text)
        text_bytes = len(text.encode("utf-8"))
        body = response.text[:500]
        raise RuntimeError(
            f"Ollama embed failed: HTTP {response.status_code}\n"
            f"  text length: {text_chars} chars, {text_bytes} bytes\n"
            f"  text preview: {text_preview!r}\n"
            f"  response body: {body}"
        )
    data = response.json()
    return data["embedding"]


def embed_batch(texts: list[str], model: str | None = None) -> list[list[float]]:
    return [embed(t, model=model) for t in texts]


def embedding_dim() -> int:
    if "nomic" in settings.model_embedding.lower():
        return 768
    if "mxbai" in settings.model_embedding.lower():
        return 1024
    if "bge-large" in settings.model_embedding.lower():
        return 1024
    return len(embed("test"))


def close() -> None:
    global _client
    if _client is not None:
        _client.close()
        _client = None

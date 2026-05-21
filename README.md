# local-ai-engineer

A local-first AI engineering assistant for coding, project planning, and environment setup. Runs entirely on your machine, with bounded web access through approved tools and approval-gated guardrails for sensitive actions.

## Why

To reduce reliance on cloud AI services (Claude, OpenAI, Perplexity) for routine engineering work — coding, planning, and setup — while keeping a local-first execution model and a clean path to cloud deployment when needed.

## Architecture

- **Model runtime:** Ollama (Llama 3.1 8B, Qwen2.5-Coder 14B, DeepSeek-Coder-V2 16B)
- **Chat UI:** Browser-based, served by the Agent API; cookie sessions for auth
- **Agent backend:** FastAPI + LangGraph
- **Vector store:** Qdrant (local) → Postgres with pgvector (cloud)
- **Relational store:** SQLite (local) → Postgres (cloud)
- **Tool layer:** Sandboxed FastAPI service with workspace allowlists
- **Safety:** Three-tier approval model (auto / per-batch / explicit)

## Status

### Foundation
- [x] Day 1: Ollama + Open WebUI running locally
- [x] Day 2: Project skeleton committed
- [x] Day 3: Configuration files and Docker Compose
- [x] Day 4: Python project, Settings class, FastAPI scaffold with bearer auth
- [x] Day 5: Ollama integration via ModelClient abstraction, /chat endpoint
- [x] Day 6: Streaming chat via Server-Sent Events
- [x] Day 7: SQLite-backed persistent conversations

### Phase A — Usable Assistant (complete)
- [x] Day 8: Browser chat UI with cookie sessions and streaming
- [x] Day 9: Auto-routing with reason, conversation sidebar
- [x] Day 10: Document ingestion pipeline with mixed file-type support
- [x] Day 11: RAG integration with citation display
- [x] Day 12: File upload through UI, collection management
- [x] Day 13a: Eval harness + functional polish with baseline
- [x] Day 13b: Visual design system (Claude-warm, light + dark themes)

### Phase B — Smart Assistant (in progress)
- [x] Day 14: Reranking + input limits + login rate limiting
- [x] Day 15: Hardening pass + open-source readiness (LICENSE, SECURITY, CONTRIBUTING)
- [x] Day 16a: URL fetching with SSRF defense + HTML sanitization (endpoint only) + DOMPurify XSS defense
- [x] Day 16b: URL fetching wired to chat with untrusted-content framing
- [x] Day 18a: Brave Search backend with daily limit + audit (no chat integration yet)
- [x] Day 18b: Web search wired to chat with untrusted-content framing + strict citations
- [x] Observability O1: per-request token + context metrics + /metrics endpoint (app-side; full OTel stack deferred to O2/O3)
- [~] Days 20-22: Cross-conversation memory (Day 20 done: storage + write path)
- [ ] Day 23: File generation (Markdown, PDF)
- [ ] Days 24-25: Query rewriting / HyDE
- [ ] Day 26: Hybrid search (vector + BM25)
- [ ] Day 27: Eval re-baseline and reflection

### Phase C — Agentic Assistant (planned)
- [ ] Approval and policy engine
- [ ] File system tools
- [ ] Git tools
- [ ] Guarded shell execution
- [ ] Repo onboarding
- [ ] Code execution sandbox

## Getting started

Prerequisites:
- Docker Desktop
- Ollama (with models pulled — see `configs/models.yaml`)
- Python 3.12+

Setup:
\`\`\`
cp .env.example .env
# Edit .env with your local values
docker compose up -d
cd apps/agent-api
uv sync
.venv/bin/python -m uvicorn agent_api.main:app --reload --host 127.0.0.1 --port 8000
\`\`\`

Then visit \`http://localhost:8000/\` and sign in with the bearer token from your \`.env\`.

## Project structure

See the directory layout in \`/apps\`, \`/configs\`, \`/data\`, \`/docs\`, \`/evals\`, \`/infra\`, and \`/scripts\`. The roadmap is documented in \`/docs/roadmap_index.md\` with detail per phase in the same directory.

## Acknowledgments

Web search is powered by the [Brave Search API](https://brave.com/search/api/).

## License

Apache License 2.0 — see [LICENSE](LICENSE) and [NOTICE](NOTICE).

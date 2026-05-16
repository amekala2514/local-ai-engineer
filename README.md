# local-ai-engineer

A local-first AI engineering assistant for coding, project planning, and environment setup. Runs entirely on your machine, with bounded web access through approved tools and approval-gated guardrails for sensitive actions.

## Why

To reduce reliance on cloud AI services (Claude, OpenAI, Perplexity) for routine engineering work — coding, planning, and setup — while keeping a local-first execution model and a clean path to cloud deployment when needed.

## Architecture

- **Model runtime:** Ollama (Llama 3.1 8B, Qwen2.5-Coder 14B, DeepSeek-Coder-V2 16B)
- **Chat UI:** Open WebUI
- **Agent backend:** FastAPI + LangGraph
- **Vector store:** Qdrant (local) → Postgres with pgvector (cloud)
- **Relational store:** SQLite (local) → Postgres (cloud)
- **Tool layer:** Sandboxed FastAPI service with workspace allowlists
- **Safety:** Three-tier approval model (auto / per-batch / explicit)

## Status

- [x] Day 1: Ollama + Open WebUI running locally
- [x] Day 2: Project skeleton committed
- [x] Day 3: Configuration files and Docker Compose
- [x] Day 4: Python setup, FastAPI
- [x] Day 5: Ollama integration with model routing

- [ ] Phase 1: Agent API foundation
- [ ] Phase 2: Tools and safety
- [ ] Phase 3: Memory and knowledge
- [ ] Phase 4: Engineering workflows
- [ ] Phase 5: Hardening
- [ ] Phase 6: Cloud deployment

## Getting started

Prerequisites:
- Docker Desktop
- Ollama (with models pulled — see `configs/models.yaml`)
- Python 3.11+

Setup:
\`\`\`
cp .env.example .env
# Edit .env with your local values
docker compose up -d
\`\`\`

## Project structure

See the directory layout in `/apps`, `/configs`, `/data`, `/evals`, `/infra`, and `/scripts`. Each has a specific role described in the build plan.

## License

MIT

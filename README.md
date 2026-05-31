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
- [x] Observability O2: distributed tracing (OpenTelemetry -> Tempo -> Grafana); RAG-stage span breakdown, opt-in
- [x] Observability O3: Prometheus dashboards over /metrics (Grafana, pinned). Loki + OTel Collector deliberately deferred (low marginal value for single-host single-service)
- [x] Days 20-22: Cross-conversation memory (storage, write, retrieval, injection, hardening + threat model)
- [x] Day 23: File generation (Markdown, PDF) — ephemeral export, both formats, MD passthrough + fpdf2 renderer
- [x] Days 24-25: Query rewriting / HyDE — HyDE enabled for RAG (eval-validated 77%->95%), rewrite built but off
- [x] Day 26: Hybrid search (vector + BM25) — DBSF fusion, eval-validated (0 wrong-source misses on 22; rescued q22)
- [x] Day 27: Eval re-baseline and reflection — source-based scoring + MRR + latency; BASELINE.md canonical (shipped HyDE+hybrid: 22/22, MRR 0.977). **Phase B complete.**

### Phase C — Agentic Assistant (planned)
Threat model: trusted local copilot, mistakes-primary, supervised, own code.
Prompt-injection-via-repo-content is the one acknowledged adversarial vector
(hardened at repo onboarding). Docker sandbox now, behind a swappable interface
for stronger isolation (gVisor/microVM) later. Build order is safety-first:
the policy engine + audit log (Days 28-30) ship before any tool can act, then
tools in increasing risk order. See THREAT_MODEL.md.

- [x] Day 28: Foundation — threat-model T11 (phase-c-v1), tool-agnostic Intent schema, resource-sensitivity data (secret/config/normal). Contracts only; no logic yet.
- [x] Day 29: Policy engine — classifier + attribute-based evaluator (allow/approve/deny), data-table rules, 15/15 on the mock-intent suite (no tools yet).
- [x] Day 30: Audit log + rich approval object — policy_audit table (intent/decision/result, threat-model version stamped) + the gate (decide->log->present), proven on mock intents. Layer 1 complete.
- [x] Day 31: Filesystem tools — read/list (auto, secrets denied live) + two-phase write (propose->approve->confirm) with real backup rollback; gated by Layer 1, full audit lifecycle. First real actions.
- [x] Day 32: Git tools — status/diff/log (auto), commit two-phase with real tag-based rollback (verified by resetting a real commit), branch (approve), push (deny). Verified on actual repo with strict cleanup.
- [x] Day 33: Docker sandbox — Sandbox protocol (swappable) + DockerSandbox (python:3.12-slim pinned, network-off, RO host mount, non-root, capped memory/CPU/time/output). Seven empirical containment proofs PASS — host writes blocked, network blocked.
- [x] Day 34: Guarded shell v1 — three layers (allowlist + gate + sandbox) composing. Real commands run contained; non-allowlisted/chained/destructive refused. Fixed a multi_command false positive (;-in-code); Day 29 suite re-verified 15/15.
- [x] Day 35: Repo onboarding (capstone) — composes lower layers into structured repo understanding; secrets never read; repo content framed as untrusted data (mirrors web T3). Injection test passes; gate is the real backstop. Framing documented as mitigation not guarantee.
- [ ] Day 36: Phase C eval + reflection — decision-correctness baseline over a policy test suite (check for false-allows and excessive false-approvals); reflect and close Phase C

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

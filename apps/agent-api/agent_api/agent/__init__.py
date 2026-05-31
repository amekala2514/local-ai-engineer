"""Phase D agent loop. Provider-agnostic: the loop, gate, and tools speak the
canonical types in types.py. Each ModelProvider (Ollama now; Anthropic/OpenAI
later) normalizes its wire format to these. Tools resolve through ToolRegistry
(local now; MCP later). Every tool-call becomes a policy Intent through the
gate — the gate trusts neither the model nor the tool source."""

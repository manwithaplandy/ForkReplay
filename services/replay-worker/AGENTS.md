# services/replay-worker — durable branch replay

Executes branch replay jobs end-to-end: hydrates the original frame stream, splices in the
user's edit, drives the agent through the remaining turns, and writes the new branch frames
back. Runs as a **Temporal worker** (durable orchestration; replaces the deprecated
`workflows/cloudflare`). LLM routing is **pluggable** via config — OpenRouter, direct
OpenAI/Anthropic, or local Ollama (`LLM_PROVIDER`) — with deterministic routing (pinned
model, fixed seed where supported).

- Runtime: container (Python 3.12)
- Orchestration: Temporal (`TEMPORAL_HOST` / `TEMPORAL_NAMESPACE`)
- LLM routing: pluggable (`LLM_PROVIDER` / `LLM_API_BASE` / `LLM_API_KEY`)

See ../../AGENTS.md or root AGENTS.md for project-wide context.

# sdk/python — `forkreplay-sdk`

Python SDK published to PyPI as `forkreplay-sdk`. Provides the OTLP-emitting client (targets
the FastAPI OTLP endpoint) and optional framework integrations as extras:

- `forkreplay-sdk[auto]` — OpenTelemetry auto-instrumentation (detection only)
- `forkreplay-sdk[langgraph]` — LangGraph adapter
- `forkreplay-sdk[claude]` — Anthropic Claude adapter
- `forkreplay-sdk[openai-agents]` — OpenAI Agents adapter

V1 ships Python only — **no TypeScript SDK** (root AGENTS.md non-goal).

See ../../AGENTS.md or root AGENTS.md for project-wide context.

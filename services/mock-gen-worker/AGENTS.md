# services/mock-gen-worker — AI-mock generation

Generates AI mock responses for replay (e.g., when a downstream tool call needs a plausible
stand-in, or when the user wants to substitute an LLM response without re-invoking the
original model). Pulls the originating frame context and emits the mock back to the
replay-worker pipeline. LLM routing is **pluggable** via config (`LLM_PROVIDER`).

- Runtime: container (Python 3.12)
- LLM routing: pluggable (OpenRouter / direct OpenAI / direct Anthropic / Ollama)
- Consumer of: replay-worker job hand-offs (via Temporal activities)

See ../../AGENTS.md or root AGENTS.md for project-wide context.

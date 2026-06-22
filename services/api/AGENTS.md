# services/api — ForkReplay control plane

FastAPI service that exposes the public control-plane HTTP API: GoTrue JWT validation,
workspace/project CRUD, branch lifecycle reads, admin-panel operations, and `WorkspaceLimits`
management. It also hosts the **FastAPI OTLP ingress endpoint** (replacing the deprecated
`workers/otlp-gateway`) and the **FastAPI SSE endpoint backed by Redis pub/sub** (replacing
the deprecated `workers/sse-relay`). Write paths that mutate ClickHouse / object storage are
owned by the worker services. **No billing** — billing/metering was removed in the OSS pivot.

- Runtime: container (Python 3.12, FastAPI + Pydantic v2)
- Auth: GoTrue JWT validation (deployment-mode-agnostic; works in all `DB_MODE`s)
- Control-plane DB: pluggable Postgres (`DB_MODE=supabase|custom|compose`)
- Streaming: SSE backed by Redis

See ../../AGENTS.md or root AGENTS.md for project-wide context.

# ForkReplay — Docker Compose Deployment

The bundled all-in-one stack: the fastest way to run ForkReplay on a single host for local
development, evaluation, or a small single-node install.

> **Status:** This page describes the intended design and environment contract. The
> deployment artifact itself — `deploy/docker-compose/docker-compose.yml` — is authored in a
> future implementation phase. The commands below are the target quickstart UX.

> **ClickHouse is required.** It ships as a bundled OSS container in this stack; there is no
> way to run ForkReplay without it.

---

## What the stack brings up

A single `docker compose up` starts the full self-host stack:

**Backing services**

- **PostgreSQL** — control plane (`DB_MODE=compose`)
- **GoTrue** — auth (validates JWTs everywhere)
- **ClickHouse** — required span/frame analytics
- **MinIO** — S3-compatible object storage (frames, exports, audit archive)
- **NATS** — ingest queue (`QUEUE_BACKEND=nats`)
- **Redis** — SSE pub/sub
- **Temporal** — durable orchestration

**ForkReplay services**

- `api` (FastAPI — OTLP ingress + REST + SSE)
- `ingest`
- `replay-worker`
- `mock-gen-worker`
- `export-worker`
- `web` (Next.js standalone container)

---

## 5-minute quickstart

```bash
git clone https://github.com/forkreplay/forkreplay.git
cd forkreplay
cp .env.example .env.local      # the defaults work for local dev
docker compose up
```

Then open `http://localhost:3000`.

The bundled defaults configure `DB_MODE=compose`, `QUEUE_BACKEND=nats`, MinIO as the S3
endpoint, and a local Redis/Temporal. Set `LLM_PROVIDER` + `LLM_API_KEY` (or point
`LLM_PROVIDER=ollama` at a local Ollama) to execute live branches. `EMAIL_BACKEND=console`
prints GoTrue confirmation links to the logs so you can sign in without an SMTP server.

See [configuration.md](./configuration.md) for the full variable reference.

---

## Single-tenant default vs multi-tenant

The multi-tenant core (Postgres RLS + ClickHouse row policies) is always present. The
compose quickstart defaults to **single-tenant**: a pre-created **default workspace** so a
solo user can sign in and start forking immediately, without provisioning tenants.

To run multi-tenant, create additional workspaces through the app/admin panel; isolation is
already enforced at the data layer. No code or schema change is required to "turn on"
multi-tenancy — it is the same binary, exercised with more than one workspace.

---

## Data persistence

Each stateful service (Postgres, ClickHouse, MinIO, NATS, Redis, Temporal) uses a named
Docker volume so data survives `docker compose down`. Use `docker compose down -v` to wipe
all state. Back up the Postgres and ClickHouse volumes for any data you care about — see the
RPO/RTO guidance in the [readiness spec](../../implementation-readiness-spec.md) §8.

---

## When to graduate

Docker Compose is single-host: there is no built-in HA, autoscaling, or multi-node
ClickHouse. For production move to:

- [Helm](./helm.md) — Kubernetes, with external/HA backing services.
- [Terraform (AWS)](./terraform-aws.md) / [Terraform (Azure)](./terraform-azure.md) — cloud IaC.

The environment contract (the variables in `.env.example`) is identical across targets, so a
configuration that works in compose maps directly onto the other targets by swapping
endpoints and flipping `DB_MODE`.

# ForkReplay — Self-Host Architecture

How the pieces fit together when you run ForkReplay on your own infrastructure. This is the
authoritative design and environment contract; the deployment artifacts that implement it
(Compose file, Helm chart, Terraform modules under `deploy/`) are authored in a future
implementation phase.

> **ClickHouse is required in every deployment mode.** It is the columnar span/frame
> analytics store and has **no Postgres substitute**. The "pluggable Postgres" choice
> (`DB_MODE`) applies to the *control plane only*; the analytics plane is always ClickHouse.

---

## Topology

ForkReplay is a small set of Python services plus a Next.js web app, backed by open-source
data stores. Everything runs on infrastructure you control.

```
                          ┌─────────────────────────────────────────────┐
   Instrumented agent     │                ForkReplay                    │
   (forkreplay-sdk)       │                                              │
        │  OTLP            │   ┌────────────┐        ┌────────────────┐  │
        ├─────────────────┼──▶│  api       │◀──────▶│  Postgres      │  │
        │  (HTTP/gRPC)     │   │ (FastAPI)  │  RLS   │  (control      │  │
        │                  │   │ OTLP +     │        │   plane)       │  │
        │                  │   │ REST + SSE │        └────────────────┘  │
        │                  │   └─────┬──────┘                ▲           │
   Browser (workbench)     │         │ enqueue               │          │
        │  HTTPS           │         ▼                  ┌─────┴───────┐  │
        ├─────────────────┼──▶ ┌──────────┐            │  GoTrue     │  │
        │  + SSE           │    │  NATS    │  JWTs ────▶│  (auth)     │  │
        │                  │    │ (queue)  │            └─────────────┘  │
        │                  │    └────┬─────┘                             │
        │                  │         ▼                                   │
        │                  │   ┌────────────┐    ┌───────────────────┐  │
        │                  │   │  ingest    │───▶│  ClickHouse       │  │
        │                  │   │ (span →    │    │  (REQUIRED        │  │
        │                  │   │  frame)    │───▶│   span/frame      │  │
        │                  │   └────────────┘    │   analytics)      │  │
        │                  │         │           └───────────────────┘  │
        │                  │         ▼                                   │
        │                  │   ┌───────────────────┐                    │
        │                  │   │  S3-compatible    │  frames, exports,  │
        │                  │   │  object store     │  audit cold archive│
        │                  │   └───────────────────┘                    │
        │                  │                                            │
        │  fork a branch   │   ┌────────────┐     ┌─────────────────┐  │
        └──────────────────┼──▶│  Temporal  │────▶│ replay-worker   │──┼──▶ LLM provider
                           │   │ (durable   │     │ mock-gen-worker │  │   (OpenRouter /
                           │   │  orchestr.)│     │ export-worker   │  │    OpenAI /
                           │   └────────────┘     └─────────────────┘  │    Anthropic /
                           │         ▲                    │            │    Ollama)
                           │         │   progress events  ▼            │
                           │   ┌──────────┐        ┌────────────┐      │
                           │   │  Redis   │◀───────│  api SSE   │      │
                           │   │ (pub/sub)│  fan-out│  (FastAPI) │      │
                           │   └──────────┘        └────────────┘      │
                           └─────────────────────────────────────────────┘
```

---

## Components

| Component | Role | Selected by |
|-----------|------|-------------|
| `apps/web` (Next.js) | Standalone-container workbench UI | always on |
| `services/api` (FastAPI) | Control plane; **OTLP ingress**; REST product API; **Redis-backed SSE** | always on |
| `services/ingest` | NATS consumer; OTel span → frame projection; writes ClickHouse/S3/Postgres | always on |
| `services/replay-worker` | Durable replay execution (Temporal worker) | always on |
| `services/mock-gen-worker` | AI-mock generation | always on |
| `services/export-worker` | Test-case + promptfoo export | always on |
| `services/scheduler` (optional) | Slim partition/retention cron | optional |
| PostgreSQL | Control-plane DB (workspaces, users, branch metadata, audit) — tenant isolation via native RLS | `DB_MODE` |
| GoTrue | Auth provider in **all** modes; services validate GoTrue JWTs | always on |
| **ClickHouse** | **Required** columnar span/frame analytics store | always on |
| S3-compatible store | Frames, export bundles, audit cold archive | `S3_ENDPOINT` |
| NATS (or Redis Streams) | Ingest queue | `QUEUE_BACKEND` |
| Redis | SSE pub/sub (branch progress + system banners) | `REDIS_URL` |
| Temporal | Durable orchestration for fork/replay | `TEMPORAL_HOST` |
| LLM provider | Branch execution target | `LLM_PROVIDER` |

See [configuration.md](./configuration.md) for the full environment-variable reference and
[../operations/provisioning-template.md](../operations/provisioning-template.md) for a
sanitized provisioning worksheet.

---

## Data flow

### Ingest (capture → queryable trace)

1. An instrumented agent (the Python `forkreplay-sdk`) emits OpenTelemetry spans.
2. Spans arrive at the **FastAPI OTLP endpoint** in `services/api` (HTTP-protobuf or gRPC).
3. `api` enqueues raw span batches onto **NATS** (or Redis Streams when `QUEUE_BACKEND=redis`).
4. `services/ingest` consumes the queue, stitches spans into the frame/branch model, applies
   redaction, and writes:
   - the **span/frame analytics projection → ClickHouse** (required),
   - **frame payloads → the S3-compatible object store** (content-addressed,
     `<workspace_id>/...` prefixes),
   - **control-plane metadata → Postgres** (promote-on-demand step rows, branch metadata).

### Fork & replay (branch execution)

1. A user selects a fork point in the workbench and submits an intervention manifest.
2. `services/api` starts a **Temporal** workflow.
3. `services/replay-worker` (a Temporal worker) executes each branch step, resolving tool
   calls via `mock`, `ai_mock` (delegated to `services/mock-gen-worker`), or `block`, and
   calls the configured **LLM provider** for live steps.
4. Progress events are published to **Redis pub/sub**; `services/api` fans them out to the
   browser over **SSE** (Last-Event-ID resume).
5. `services/export-worker` produces test-case / promptfoo bundles into the object store on
   demand.

### Auth & isolation

- **GoTrue** issues JWTs; every service validates them the same way regardless of `DB_MODE`.
- Tenant isolation is defense-in-depth: workspace scoping on every query, native Postgres
  **RLS**, ClickHouse **row policies**, and object-store key-prefix isolation. A CI
  conformance test fails the build if any policy is missing.

---

## Deprecated Cloudflare/Vercel components → OSS replacements

The repo retains some Cloudflare/Vercel-era directories as transition references only
(secret-scrubbed). They are not part of the self-host stack and are slated for deletion in an
implementation phase.

| Deprecated | OSS replacement (this architecture) |
|------------|-------------------------------------|
| `workers/otlp-gateway` (CF Workers) | FastAPI OTLP endpoint in `services/api` / `services/ingest` |
| `workers/sse-relay` (CF Workers + Durable Object) | FastAPI SSE backed by Redis pub/sub |
| `workflows/cloudflare` (CF Workflows) | Temporal (self-hosted) |
| Vercel-hosted web | `apps/web` standalone container (deployable anywhere) |
| `services/billing-batch-worker` | Removed — no built-in billing; cron → optional `services/scheduler` |

---

## Where to go next

- [docker-compose.md](./docker-compose.md) — bundled all-in-one stack + 5-minute quickstart
- [helm.md](./helm.md) — Kubernetes chart design
- [terraform-aws.md](./terraform-aws.md) / [terraform-azure.md](./terraform-azure.md) — cloud IaC design
- [configuration.md](./configuration.md) — full environment-variable reference

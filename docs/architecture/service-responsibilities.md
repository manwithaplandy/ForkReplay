# ForkReplay — Service-Level Responsibilities

The per-service charter for the OSS self-host stack. This document pins down **what each
container/service owns** — and, just as importantly, what it does **not** own — before any
product code is written. It is the companion to
[../deployment/architecture.md](../deployment/architecture.md) (which describes how the
pieces wire together at runtime); here the focus is the **ownership boundary**, the
**upstream dependencies** each service consumes, the **downstream consumers** that depend on
it, and the required infrastructure each one touches.

> **Exit bar for this charter.** Every service below has a single, crisp ownership boundary,
> an explicit "does not own" list (so responsibilities do **not** overlap), named
> upstream/downstream edges, and the required infra it depends on. This reflects the locked
> OSS direction: the deprecated Cloudflare workers and the billing layer were **removed** and
> **replaced** by FastAPI / Temporal equivalents (see
> [Deprecated → replaced](#deprecated--replaced-mapping)).

> **ClickHouse is required in every deployment mode.** It is the columnar span/frame
> analytics store and has **no Postgres substitute**. The "pluggable Postgres" choice
> (`DB_MODE`) applies to the *control plane only*; the analytics plane is always ClickHouse.

---

## How to read this document

Each service gets a dedicated section with the same five fields:

- **Ownership boundary** — one crisp sentence, then detail. The single responsibility this
  service is accountable for.
- **Does NOT own** — responsibilities deliberately delegated elsewhere. This is how the
  charter proves there is **no overlap** between services.
- **Upstream dependencies** — what this service calls into or consumes from (its inputs).
- **Downstream consumers** — who depends on this service's output (its outputs).
- **Infra it uses** — which required infrastructure components this service touches.

A consolidated [dependency matrix](#service--infrastructure-dependency-matrix) and an
[ownership / non-overlap matrix](#ownership--non-overlap-matrix) follow the per-service
sections.

---

## Application & control-plane services

### `apps/web` — Workbench UI

- **Ownership boundary:** owns the **browser-facing workbench** — the Next.js 16 standalone
  container where users browse captured agent traces, choose a fork point, submit an
  intervention manifest, and inspect replay results. It owns presentation, client-side state,
  and the SSE subscription for live branch progress.
- **Does NOT own:** any persistence, business logic, OTLP ingestion, or replay execution. It
  holds no database credentials and never talks to Postgres, ClickHouse, NATS, Temporal, or
  the object store directly — all data access is mediated by `services/api`.
- **Upstream dependencies:** `services/api` (REST + SSE) for every read/write; **GoTrue** for
  the login flow and JWT issuance (`NEXT_PUBLIC_GOTRUE_URL`).
- **Downstream consumers:** the human operator's browser. No other service depends on
  `apps/web`.
- **Infra it uses:** none directly. It is a stateless container; its only network edges are
  the API base URL (`NEXT_PUBLIC_API_BASE_URL`) and GoTrue.

### `services/api` — control plane, OTLP ingress, SSE

- **Ownership boundary:** owns the **public control-plane HTTP surface**: GoTrue JWT
  validation, workspace/project CRUD, branch-lifecycle reads, admin-panel operations, and
  `WorkspaceLimits` enforcement. It additionally hosts the **FastAPI OTLP ingress endpoint**
  (HTTP-protobuf / gRPC) and the **FastAPI SSE endpoint backed by Redis pub/sub**.
- **Does NOT own:** the heavy write paths. It does **not** project spans into frames, does
  **not** write ClickHouse analytics rows or object-store blobs on the hot path, and does
  **not** execute replays — it *enqueues* and *orchestrates*, then reads results back. It owns
  no billing logic; billing/metering was **removed** in the OSS pivot and only operational
  `WorkspaceLimits` remain.
- **Upstream dependencies:** the `forkreplay-sdk` (OTLP spans arrive here); the browser
  (`apps/web`); **GoTrue** (token validation); **Postgres** (control-plane reads/writes);
  **Redis** (subscribe to progress events to fan out over SSE); **Temporal** (starts the
  fork/replay workflow); **NATS** / Redis Streams (enqueues raw span batches).
- **Downstream consumers:** `apps/web` (all REST + SSE traffic); `services/ingest` (consumes
  the span batches the API enqueues); `services/replay-worker` (executes the Temporal
  workflows the API starts).
- **Infra it uses:** Postgres (`DB_MODE`), GoTrue, Redis (`REDIS_URL`), NATS/Redis queue
  (`QUEUE_BACKEND`), Temporal (`TEMPORAL_HOST`). It reads ClickHouse for query endpoints but
  is not the writer.

---

## Worker services (data plane)

### `services/ingest` — OTel span → frame projection

- **Ownership boundary:** owns the **span-to-frame projection pipeline** — it is the single
  writer that consumes raw OTLP span batches off the queue, stitches them into the ForkReplay
  frame/branch model, applies redaction, and persists the result.
- **Does NOT own:** the OTLP *network endpoint* (that is `services/api`'s FastAPI ingress) and
  it does **not** serve any HTTP API or run replays. It is a pure queue consumer / projector.
- **Upstream dependencies:** **NATS** subject `forkreplay.otlp.ingest` (or Redis Streams when
  `QUEUE_BACKEND=redis`), populated by the FastAPI OTLP endpoint in `services/api`.
- **Downstream consumers:** every read path that queries traces — `services/api` query
  endpoints (and through them `apps/web`), `services/replay-worker` (hydrates original frames),
  and `services/export-worker` (materializes frames into test cases).
- **Infra it uses:** NATS/Redis queue (input), **ClickHouse** (required analytics projection),
  **Postgres** (control-plane frame-index rows), **S3-compatible object store** (frame
  payloads, content-addressed under `<workspace_id>/...` prefixes).

### `services/replay-worker` — durable branch replay

- **Ownership boundary:** owns **branch replay execution** — as a **Temporal worker** it
  hydrates the original frame stream, splices in the user's edit, drives the agent through the
  remaining turns with deterministic routing (pinned model, fixed seed where supported), and
  writes the new branch frames back.
- **Does NOT own:** workflow *scheduling* policy (Temporal owns durable orchestration; the API
  *starts* the workflow), AI-mock *generation* (delegated to `services/mock-gen-worker`), and
  export materialization (delegated to `services/export-worker`). It does not expose an HTTP
  API.
- **Upstream dependencies:** **Temporal** (work dispatched as activities/workflows started by
  `services/api`); the captured frame stream from `services/ingest`; the configured **LLM
  provider** (`LLM_PROVIDER` — OpenRouter / direct OpenAI / direct Anthropic / Ollama);
  `services/mock-gen-worker` for `ai_mock` tool resolutions.
- **Downstream consumers:** `services/api` / `apps/web` (read the resulting branch frames);
  **Redis** progress subscribers via the API's SSE fan-out.
- **Infra it uses:** Temporal (`TEMPORAL_HOST` / `TEMPORAL_NAMESPACE`), ClickHouse + S3 +
  Postgres (writes new branch frames through the same projection targets), Redis (publishes
  progress events), LLM provider.

### `services/mock-gen-worker` — AI-mock generation

- **Ownership boundary:** owns **AI-mock response generation** — when a downstream tool call
  needs a plausible stand-in, or a user substitutes an LLM response without re-invoking the
  original model, this worker pulls the originating frame context and emits the mock.
- **Does NOT own:** the replay loop itself (it is invoked *by* `services/replay-worker` via
  Temporal activities), frame persistence, or any HTTP API. It is a focused generation helper.
- **Upstream dependencies:** `services/replay-worker` job hand-offs (Temporal activities); the
  originating frame context; the configured **LLM provider** (`LLM_PROVIDER`).
- **Downstream consumers:** `services/replay-worker` (consumes the generated mock back into the
  branch pipeline).
- **Infra it uses:** Temporal (activity execution), LLM provider. It reads frame context but
  does not own a persistence path.

### `services/export-worker` — test-case + Promptfoo export

- **Ownership boundary:** owns **export materialization** — it turns a real trace or a forked
  replay into deterministic regression artifacts: Promptfoo YAML test cases, pytest fixture
  modules, and generic trajectory JSONL.
- **Does NOT own:** capture, projection, or replay. It is a read-then-write consumer of
  already-projected frames and does not mutate the live trace/branch model.
- **Upstream dependencies:** projected frames from `services/ingest` (read via the analytics
  store); export jobs requested through `services/api`.
- **Downstream consumers:** end users, who download artifacts as signed-URL bundles surfaced
  through `services/api`.
- **Infra it uses:** **S3-compatible object store** (`S3_BUCKET_BLOBS`, export bundles),
  ClickHouse / Postgres (reads frame data to materialize). Optionally Temporal if run as a
  durable activity.

### `services/scheduler` (optional) — partition/retention cron

- **Ownership boundary:** owns **low-frequency platform maintenance cron** — slim
  partition rotation and retention enforcement (e.g. dropping aged ClickHouse partitions,
  pruning expired object-store archives, applying `WorkspaceLimits` retention windows).
  Optional: operators who do not need automated retention can omit it.
- **Does NOT own:** any request-path logic, ingestion, replay, or export. It holds no
  user-facing surface and performs only scheduled batch maintenance.
- **Upstream dependencies:** a cron trigger (its own schedule); control-plane retention policy
  read from **Postgres**.
- **Downstream consumers:** none directly — its effect is observed as freed storage and
  enforced retention across ClickHouse / S3 / Postgres.
- **Infra it uses:** Postgres (policy + bookkeeping), ClickHouse (partition drops), S3 (archive
  pruning).

> **Origin note:** `services/scheduler` is the slim OSS successor for platform crons. The
> heavy billing batch jobs that **formerly** lived elsewhere were **removed**; only
> operational partition/retention cron remains here. See
> [Deprecated → replaced](#deprecated--replaced-mapping).

---

## Shared packages & SDK

### `sdk/python` — `forkreplay-sdk`

- **Ownership boundary:** owns the **client capture surface** — the PyPI-published
  `forkreplay-sdk` that emits OpenTelemetry spans to the FastAPI OTLP endpoint, plus optional
  framework adapters shipped as extras (`[auto]`, `[langgraph]`, `[claude]`,
  `[openai-agents]`).
- **Does NOT own:** any server-side processing, storage, or replay. It is purely an emitter
  living inside the user's instrumented agent. V1 ships **Python only** — there is no
  TypeScript client (an explicit non-goal).
- **Upstream dependencies:** the user's agent runtime (it instruments their code); the
  `packages/contracts` schemas it conforms to.
- **Downstream consumers:** `services/api`'s OTLP ingress, which receives the emitted spans.
- **Infra it uses:** none of the self-host stack directly — it only needs a network path to
  the API's OTLP endpoint.

### `packages/contracts` — OpenAPI + JSON schemas

- **Ownership boundary:** owns the **canonical wire contracts** — the OpenAPI spec and JSON
  schemas that every service and the SDK conform to. Dual-published as `@forkreplay/contracts`
  (JS, for `apps/web`) and `forkreplay-contracts` (Python, for services and the SDK).
- **Does NOT own:** any runtime behavior, persistence, or business logic. It is a
  build-time/shared dependency, not a running service.
- **Upstream dependencies:** none at runtime; schema edits are gated by the
  `docs-drift-check` workflow (a contract-surface change must be paired with a `docs/**`
  edit).
- **Downstream consumers:** `apps/web`, every `services/*`, and `sdk/python` — all depend on
  these schemas for request/response shapes.
- **Infra it uses:** none. It is published to package registries, not deployed.

---

## Required infrastructure components

These are the backing stores and platforms every deployment mode provisions. "Pluggable
Postgres" applies to the control plane only; **ClickHouse is required and never substituted.**

### PostgreSQL — control-plane database

- **Role:** workspaces, users, projects, branch metadata, frame-index rows, audit trail.
  Tenant isolation via native **RLS**.
- **Selected by:** `DB_MODE` (`supabase | custom | compose`).
- **Depended on by:** `services/api` (read/write), `services/ingest` (frame-index writes),
  `services/replay-worker` (branch metadata), `services/export-worker` (reads),
  `services/scheduler` (retention policy).

### GoTrue — authentication

- **Role:** issues JWTs; every service validates them identically regardless of `DB_MODE`.
- **Selected by:** bundled in `custom` / `compose` modes; always present.
- **Depended on by:** `apps/web` (login), `services/api` (token validation). Workers trust
  the API's validated context.

### ClickHouse — span/frame analytics (REQUIRED)

- **Role:** the columnar analytics store for spans and frames. No Postgres substitute.
- **Selected by:** always on, every mode.
- **Depended on by:** `services/ingest` (the writer), `services/api` (query reads),
  `services/replay-worker` (frame writes/reads), `services/export-worker` (reads),
  `services/scheduler` (partition maintenance).

### S3-compatible object store (MinIO / AWS S3 / Azure Blob)

- **Role:** frame payloads, export bundles, audit cold archive — content-addressed,
  workspace-prefixed.
- **Selected by:** `S3_*` config (`S3_ENDPOINT`, `S3_BUCKET_BLOBS`).
- **Depended on by:** `services/ingest` (frame blobs), `services/export-worker` (bundles),
  `services/scheduler` (archive pruning). `services/api` issues signed URLs.

### NATS (or Redis Streams) — ingest queue

- **Role:** durable buffer between OTLP ingress and the projection pipeline.
- **Selected by:** `QUEUE_BACKEND` (`nats` default; Redis Streams alternative).
- **Depended on by:** `services/api` (producer), `services/ingest` (consumer).

### Redis — SSE pub/sub

- **Role:** progress-event and system-banner pub/sub feeding the SSE fan-out.
- **Selected by:** `REDIS_URL`.
- **Depended on by:** `services/api` (subscriber + SSE relay), `services/replay-worker`
  (publisher). Reaches `apps/web` over SSE.

### Temporal — durable orchestration

- **Role:** durable workflow engine for the fork/replay loop (retries, timeouts, resumption).
- **Selected by:** `TEMPORAL_HOST` / `TEMPORAL_NAMESPACE`.
- **Depended on by:** `services/api` (starts workflows), `services/replay-worker` (worker),
  `services/mock-gen-worker` (activities), optionally `services/export-worker`.

> The **LLM provider** (`LLM_PROVIDER` — OpenRouter / direct OpenAI / direct Anthropic /
> Ollama) is a pluggable external target consumed by `services/replay-worker` and
> `services/mock-gen-worker`, not a store ForkReplay operates.

---

## Service ⇄ infrastructure dependency matrix

`W` = writes / produces, `R` = reads / consumes, `—` = no direct edge.

| Service | Postgres | GoTrue | ClickHouse | S3 store | NATS/Redis queue | Redis SSE | Temporal | LLM provider |
|---------|:--------:|:------:|:----------:|:--------:|:----------------:|:---------:|:--------:|:------------:|
| `apps/web` | — | R | — | — | — | R (SSE) | — | — |
| `services/api` | R/W | R | R | R (signed URLs) | W (enqueue) | R (fan-out) | W (start) | — |
| `services/ingest` | W (index) | — | W | W | R (consume) | — | — | — |
| `services/replay-worker` | R/W | — | R/W | R/W | — | W (progress) | R (worker) | R |
| `services/mock-gen-worker` | — | — | R | — | — | — | R (activity) | R |
| `services/export-worker` | R | — | R | W (bundles) | — | — | R (optional) | — |
| `services/scheduler` | R/W | — | W (drop) | W (prune) | — | — | — | — |
| `sdk/python` | — | — | — | — | — | — | — | — |
| `packages/contracts` | — | — | — | — | — | — | — | — |

`sdk/python` depends only on a network path to the `services/api` OTLP endpoint;
`packages/contracts` is a build-time shared dependency consumed by every service, `apps/web`,
and the SDK.

---

## Ownership / non-overlap matrix

Each responsibility has **exactly one** owning service — this is the proof there is no
overlap.

| Responsibility | Sole owner | Everyone else |
|----------------|-----------|---------------|
| Browser workbench / presentation | `apps/web` | consumes API only |
| Public REST + admin control plane | `services/api` | call it; do not duplicate |
| OTLP network endpoint (ingress) | `services/api` | spans flow in here |
| SSE fan-out | `services/api` | publish to Redis, do not relay |
| Span → frame projection (writer) | `services/ingest` | read projected frames |
| Branch replay execution | `services/replay-worker` | delegate to it via Temporal |
| AI-mock generation | `services/mock-gen-worker` | request via replay-worker |
| Export materialization | `services/export-worker` | request via API |
| Partition/retention cron | `services/scheduler` | no other cron owner |
| Client capture / instrumentation | `sdk/python` | server side never emits |
| Wire schemas (OpenAPI/JSON) | `packages/contracts` | conform, do not fork |

---

## Deprecated → replaced mapping

The repo retains some Cloudflare/Vercel-era directories and the billing layer **only as
transition references** (secret-scrubbed); they are **not** part of the self-host stack and
are **slated** for deletion in an implementation phase. Each was **replaced** by an OSS
equivalent in this charter.

| Deprecated / removed | Status | Replaced by (this charter) |
|----------------------|--------|----------------------------|
| `workers/otlp-gateway` (Cloudflare Workers) | deprecated | FastAPI OTLP endpoint in `services/api` (feeds `services/ingest`) |
| `workers/sse-relay` (Cloudflare Workers + Durable Object) | deprecated | FastAPI SSE backed by Redis pub/sub in `services/api` |
| `workflows/cloudflare` (Cloudflare Workflows) | deprecated | Temporal (self-hosted), driving `services/replay-worker` |
| Vercel-hosted web | legacy | `apps/web` standalone container (deployable anywhere) |
| `services/billing-batch-worker` | removed from core | billing dropped in the OSS pivot; partition/retention cron moved to optional `services/scheduler` |

The deprecated Cloudflare worker directories are **no longer** wired into any runtime path;
the `billing-batch-worker` directory is **frozen** and **slated** for deletion, with its
partition/retention cron **replaced** by `services/scheduler`.

---

## Where to go next

- [../deployment/architecture.md](../deployment/architecture.md) — runtime topology + data flow
- [../deployment/configuration.md](../deployment/configuration.md) — environment-variable reference
- `implementation-plan.md` §11 — the architecture-artifact checklist this charter satisfies
- `implementation-readiness-spec.md` — object model and audit-trail contracts

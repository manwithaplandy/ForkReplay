# ForkReplay — Agent Instructions

ForkReplay is an **open-source, self-hostable** product for forking and replaying captured
AI agent conversations. This file is the canonical project instruction for any AI coding
agent working in this repo.

> **AGENTS.md ⇄ CLAUDE.md:** `AGENTS.md` is the single source of truth (the tool-agnostic
> open standard). `CLAUDE.md` is a symlink to it so Claude and other agents read identical
> instructions — there is one source of truth per directory. Edit `AGENTS.md`; never
> replace the `CLAUDE.md` symlink with a divergent copy.

## Secrets & proprietary data — do NOT commit

**Never commit secrets or proprietary information** to this repository — credentials, API
keys, JWTs, database passwords, cloud account IDs, project refs, service endpoints,
customer data, or personal/operator PII — and not in code, comments, fixtures, or example
files either. This is an OSS project; everything here is public.

- Put real configuration in your secret manager and in local, gitignored files
  (`.env.local`, `*.local.md`). See `.gitignore`, `.env.example`, and `SECURITY.md`.
- Use `${PLACEHOLDER}` markers in committed templates (see
  `docs/operations/provisioning-template.md`).
- CI runs a secret scan (gitleaks) on PRs; do not disable it to land a change.
- If you find a committed secret, treat it as compromised: rotate it, then scrub it.

## Development discipline — strict TDD & objective validation (MANDATORY)

Every change follows **strict red/green TDD** and is gated on an **objective validation**.
This is a hard requirement, not a preference — it applies to product code, infra, SDK, and
fixtures alike.

### Red → green → refactor, in that order
- **Red:** write a failing test that pins the intended behavior *before* writing any
  production code. Run it and confirm it fails *for the expected reason* (not a typo, import
  error, or missing fixture).
- **Green:** write the minimum production code to make that test pass. Run it; confirm green.
- **Refactor:** clean up with the test still green, then re-run.
- Do **not** write production code that has no failing test driving it, and do not write the
  test *after* the code. A bug fix starts with a test that reproduces the bug (red), then the
  fix (green).

### Define the validation before starting a task
- For every task, **state the objective validation(s) up front** — something a machine can
  check and another engineer can re-run: a specific test command, a CI gate, a measurable
  threshold (e.g. a p95 latency, a query result, an HTTP status), a schema/contract check, or
  a reproducible command with its expected output.
- "Looks right", "should work", or "it compiles/imports" are **not** validations. Prefer the
  established acceptance gates where one applies (tenant-isolation
  conformance across all 3 DB modes, the 30-minute first-fork-grade-trace acceptance test,
  fork-start p95 < 3s, ingest 10k spans/sec/node, the SDK coverage bars, `docs-drift-check`,
  the self-host smoke gates).

### Affirm the validation actually passed before calling a task done
- A task is **complete only after you have run its validation and observed it pass.**
  Positively affirm this — cite the command you ran and its actual result. Never declare a
  task done from code inspection alone, or because the diff looks correct.
- If a validation reveals a failure, **report it with the real output** — do not paper over
  it, weaken the test, or narrow the assertion to make it pass.
- If a validation **cannot be run here, is blocked, or requires user interaction** —
  credentials, a live external service (provider API key, cloud account), a manual UI/browser
  step, a `terraform apply`, a real cluster — **stop and tell the user**: name the validation,
  explain why it can't be completed in this environment, and state what you need from them. Do
  not silently skip it or mark the task done on the assumption that it *would* pass.

## License & distribution

- **Apache-2.0** (permissive; patent grant). See `LICENSE`.
- Single self-hostable codebase. There is **no managed-SaaS layer** — self-host is the
  product. The project must remain fully customizable by the end user.

## Deployment modes (the product ships multiple)

- **docker-compose** — bundled all-in-one stack (quickstart). See `docs/deployment/docker-compose.md`.
- **Helm** — Kubernetes. See `docs/deployment/helm.md`.
- **Terraform (AWS / Azure)** — cloud IaC skeletons. See `docs/deployment/terraform-aws.md`, `docs/deployment/terraform-azure.md`.
- Control-plane Postgres is pluggable: **`DB_MODE=supabase | custom | compose`**.
- **ClickHouse is REQUIRED in every mode** — it is the columnar span/frame analytics store
  and has no Postgres substitute. "Pluggable Postgres" applies to the control plane only.

(Deployment artifacts under `deploy/` — compose file, Helm charts, Terraform modules — are
authored in a future implementation phase; this repo currently documents their design.)

## Canonical docs (read these first)
- `agent-trace-fork-prd.md` — v0.9 product requirements (OSS self-hostable)
- `implementation-readiness-spec.md` — v0.5 object model, contracts, audit trail
- `competitive_analysis.md` — v0.4 OSS market positioning
- `docs/deployment/` — self-host topology, configuration, and deployment-target docs
- `docs/architecture/` — design sketches: services, schemas, API surface, Temporal workflows, SDK, deployment modes

> The phased build sequence (Phase 0–6) is tracked as GitHub milestones, not as a
> checked-in plan doc.

## OSS V1 scope (do NOT expand without explicit approval)

These are explicit V1 constraints. Any PR adding them must be flagged as scope expansion:

- **Self-host is the product.** Single OSS codebase; no retained managed-SaaS layer.
- **No built-in billing/metering.** Stripe, replay credits, and the credit/meter object
  model are removed. Only operational `WorkspaceLimits` (concurrency/depth/wall-clock/
  retention/token volume) remain. Operators bring their own billing if they want it.
- **ClickHouse is a required dependency** (not optional, not Postgres-substitutable).
- **Python-only SDK.** No TypeScript SDK in V1.
- **Multi-tenant core retained** (Postgres RLS + ClickHouse row policies); the documented
  default quickstart is **single-tenant** (a default workspace).
- **Pluggable backends** are the design point: auth (GoTrue everywhere), DB (3 modes),
  object storage (S3-compatible), queue (NATS / Redis), LLM (OpenRouter / direct / Ollama),
  email (SMTP / Resend / console). Do not hard-code a single vendor.

## Service-by-service responsibilities

| Path | Runtime | Role |
|------|---------|------|
| `apps/web` | Next.js standalone container | Workbench UI (deployable anywhere) |
| `services/api` | Container (Python/FastAPI) | Control plane; FastAPI OTLP ingress; FastAPI SSE (Redis-backed) |
| `services/ingest` | Container (Python) | NATS consumer; OTel span → frame projection |
| `services/replay-worker` | Container (Python) | Durable replay execution (Temporal workers) |
| `services/mock-gen-worker` | Container (Python) | AI-mock generation |
| `services/export-worker` | Container (Python) | Test-case + promptfoo export |
| `services/scheduler` (optional) | Container (Python) | Slim partition/retention cron (replaces billing-batch-worker's cron) |
| `sdk/python` | PyPI | `forkreplay-sdk` + framework extras |
| `packages/contracts` | shared | OpenAPI + JSON schemas |

### Required infrastructure components (self-host stack)

| Component | Role | Selected by |
|-----------|------|-------------|
| PostgreSQL | Control-plane DB | `DB_MODE` |
| GoTrue | Auth (JWTs validated everywhere) | bundled in custom/compose |
| ClickHouse | **Required** span/frame analytics | always |
| S3-compatible store (MinIO / S3 / Azure Blob) | Frames, exports, audit archive | `S3_*` config |
| NATS (or Redis Streams) | Ingest queue | `QUEUE_BACKEND` |
| Redis | SSE pub/sub | `REDIS_URL` |
| Temporal | Durable orchestration | `TEMPORAL_*` |

### Deprecated — slated for removal (Cloudflare-specific; replaced by OSS equivalents)

| Path | Status | Replaced by |
|------|--------|-------------|
| `workers/otlp-gateway` | Deprecated | FastAPI OTLP endpoint in `services/ingest`/`services/api` |
| `workers/sse-relay` | Deprecated | FastAPI SSE backed by Redis pub/sub |
| `workflows/cloudflare` | Deprecated | Temporal (self-hosted) |
| `services/billing-batch-worker` | Removed from core | Billing removed; cron → optional `services/scheduler` |

These directories are retained (secret-scrubbed) only as transition references; deletion is
an implementation-phase task.

## Phase 0 first

Implementation work begins with the Phase 0 spikes, tracked as the **Phase 0 GitHub
milestone**. Critical-path order and the per-phase issue breakdown live in the GitHub
milestones (Phase 0–6); the OSS-pivot scope constraints are captured in the "OSS V1 scope"
section above.

## Per-directory AGENTS.md

Each top-level service directory has its own `AGENTS.md` (with a `CLAUDE.md` symlink) for
service-specific context. Read root + the relevant service file when working in a
sub-directory.

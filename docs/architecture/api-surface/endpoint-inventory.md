# ForkReplay — First OpenAPI Endpoint Inventory

The initial public-surface contract for ForkReplay's V1 self-host build. This inventory
enumerates the V1 public API across three surfaces:

1. **Control-plane REST** — the OpenAPI product/admin API served by `services/api` (FastAPI).
2. **OTLP ingest** — the native OpenTelemetry receiver served by the **FastAPI OTLP
   endpoint** in `services/api` / `services/ingest`.
3. **SSE** — the FastAPI Server-Sent-Events stream (Redis pub/sub backed) for branch
   progress and system banners.

> **Purpose / scope.** This document is the **design input for scaffolding the OpenAPI spec
> in `packages/contracts`** (`packages/contracts/openapi/`). It is an *inventory*, not the
> spec itself — this artifact does **not** author the OpenAPI document, JSON schemas, or any
> code under `packages/contracts/**`, `services/api/openapi/**`, or `sdk/python/**`. It
> exists so the contract authors (a later phase) have a complete, object-model-grounded list
> of methods, paths, auth requirements, and tenant-scoping rules to turn into the spec.
> Per the implementation plan §11, this is the "first OpenAPI endpoint inventory (including
> the FastAPI OTLP endpoint)."

Endpoints are grounded in the canonical object model in `implementation-readiness-spec.md`
§2 (Workspace, Member, ApiKey, Trace, Step, Frame, Branch, TrialSet, ExportSnapshot,
TestCase, AuditEvent, WorkspaceLimits) and the auth/governance rules in §8. The data-flow
context for ingest and SSE is in [`../../deployment/architecture.md`](../../deployment/architecture.md).

---

## Conventions

- **Versioning.** All endpoints live under the `/v1` prefix. Breaking changes bump the
  prefix; additive changes do not.
- **Tenancy.** ForkReplay is multi-tenant at the core (the documented quickstart is
  single-tenant with a default workspace). **Every** product resource belongs to exactly one
  workspace, so most control-plane paths are nested under
  `/v1/workspaces/{workspace_id}/...`. The `{workspace_id}` path segment is the primary
  tenant-scoping key; it is cross-checked against the caller's workspace membership (user
  JWT) or the key's workspace scope (API key) on every request.
- **Auth columns.** Each entry lists its auth requirement. ForkReplay bundles **GoTrue**
  (Supabase Auth OSS) as the auth provider in **all** `DB_MODE`s, and **every service
  validates GoTrue-issued JWTs the same way**. Two credential kinds appear:
  - **User JWT** — a GoTrue-issued bearer token for an interactive user (workbench, admin
    panel). Authorization is the user's `Member.role` (`admin` / `editor` / `viewer`) in the
    target workspace.
  - **API key** (a.k.a. workspace key / ingest key) — a workspace-scoped `ApiKey` with a
    verb-on-resource `scopes` taxonomy (`traces:write`, `traces:read`, `branches:write`,
    `branches:read`, `exports:write`, `exports:read`, `mocks:write`, `mocks:approve`,
    `workspace:admin`). Used by the SDK and programmatic clients.
- **Tenant-scope note column.** Names the path segment or token claim that pins the request
  to a workspace, plus the enforcement layer (workspace membership check + Postgres RLS;
  ClickHouse row policies and object-store key-prefix isolation apply on the read/write
  paths that reach those stores).
- **Authorization is defense-in-depth.** Beyond the route-level check, tenant isolation is
  enforced by native Postgres RLS, ClickHouse row policies, and object-store
  `<workspace_id>/...` key prefixes (per `implementation-readiness-spec.md` §8). A CI
  conformance test fails the build if any policy layer is missing.

---

## 1. Control-plane REST (OpenAPI)

Served by `services/api` (FastAPI + Pydantic v2). These are the endpoints the OpenAPI spec
in `packages/contracts` will formalize.

### 1.1 Workspaces

| Method | Path | Purpose | Auth | Tenant scope |
|--------|------|---------|------|--------------|
| GET | `/v1/workspaces` | List workspaces the caller is a member of | User JWT | Result filtered to the caller's memberships |
| POST | `/v1/workspaces` | Create a workspace (becomes its first admin) | User JWT | New workspace; creator gets `admin` membership |
| GET | `/v1/workspaces/{workspace_id}` | Read workspace settings (name, slug, policies, `llm_routing_status`) | User JWT (member) | `{workspace_id}` + membership |
| PATCH | `/v1/workspaces/{workspace_id}` | Update workspace name/slug/policy references | User JWT (`admin`) | `{workspace_id}` + membership |
| DELETE | `/v1/workspaces/{workspace_id}` | Delete/soft-delete a workspace | User JWT (`admin`) | `{workspace_id}` + membership |

### 1.2 Members

| Method | Path | Purpose | Auth | Tenant scope |
|--------|------|---------|------|--------------|
| GET | `/v1/workspaces/{workspace_id}/members` | List members and roles | User JWT (member) | `{workspace_id}` path + RLS |
| POST | `/v1/workspaces/{workspace_id}/members` | Invite a member (email + role) | User JWT (`admin`) | `{workspace_id}` path + RLS |
| GET | `/v1/workspaces/{workspace_id}/members/{member_id}` | Read a member | User JWT (member) | `{workspace_id}` path + RLS |
| PATCH | `/v1/workspaces/{workspace_id}/members/{member_id}` | Change role / status (`invited`→`active`, `disabled`) | User JWT (`admin`) | `{workspace_id}` path + RLS |
| DELETE | `/v1/workspaces/{workspace_id}/members/{member_id}` | Remove a member | User JWT (`admin`) | `{workspace_id}` path + RLS |

### 1.3 Auth policy

Workspace login policy (`auth_policy`: enabled login methods, allowed email domains, require
verified email). Backed by the `auth_policy_*` fields on `WorkspaceLimits`.

| Method | Path | Purpose | Auth | Tenant scope |
|--------|------|---------|------|--------------|
| GET | `/v1/workspaces/{workspace_id}/auth-policy` | Read the workspace auth policy | User JWT (`admin`) | `{workspace_id}` path + RLS |
| PUT | `/v1/workspaces/{workspace_id}/auth-policy` | Set enabled methods / allowed domains / verified-email requirement | User JWT (`admin`) | `{workspace_id}` path + RLS; audited |

### 1.4 API keys

| Method | Path | Purpose | Auth | Tenant scope |
|--------|------|---------|------|--------------|
| GET | `/v1/workspaces/{workspace_id}/api-keys` | List API keys (metadata only; secret never returned) | User JWT (`admin`) | `{workspace_id}` path + RLS |
| POST | `/v1/workspaces/{workspace_id}/api-keys` | Create a key with `scopes`; secret shown once | User JWT (`admin`) | `{workspace_id}` path + RLS; audited |
| DELETE | `/v1/workspaces/{workspace_id}/api-keys/{api_key_id}` | Revoke a key (`status=revoked`) | User JWT (`admin`) | `{workspace_id}` path + RLS; audited |

### 1.5 Traces

Immutable captured executions. Trace content (frames/messages) lives in ClickHouse + the
object store; these REST endpoints read the control-plane index and proxy redacted content.

| Method | Path | Purpose | Auth | Tenant scope |
|--------|------|---------|------|--------------|
| GET | `/v1/workspaces/{workspace_id}/traces` | List/search traces (status, service, tags, time window) | User JWT (member) or API key `traces:read` | `{workspace_id}` path + RLS + ClickHouse row policy |
| GET | `/v1/workspaces/{workspace_id}/traces/{trace_id}` | Read trace detail (summary, status, semconv) | User JWT (member) or API key `traces:read` | `{workspace_id}` path; per-trace ACL if `restricted` |
| GET | `/v1/workspaces/{workspace_id}/traces/{trace_id}/steps` | List reconstructed steps for a trace | User JWT (member) or API key `traces:read` | `{workspace_id}` path + ClickHouse row policy |
| GET | `/v1/workspaces/{workspace_id}/traces/{trace_id}/frames/{step_id}` | Read the forkable frame at a step boundary (redacted; fidelity badge) | User JWT (member) or API key `traces:read` | `{workspace_id}` path + object-store key prefix |
| DELETE | `/v1/workspaces/{workspace_id}/traces/{trace_id}` | Delete a trace (cascades per retention/`FrameReferences` GC) | User JWT (`admin`) | `{workspace_id}` path + RLS; audited |

> Trace *creation* is not a REST write — traces are produced by the OTLP ingest surface
> (§2) and projected by `services/ingest`.

### 1.6 Branches (fork / replay)

A `Branch` is a forked trajectory; fork/replay execution is orchestrated by Temporal
(`services/replay-worker`). REST starts the workflow and reads branch state; live progress
streams over SSE (§3).

| Method | Path | Purpose | Auth | Tenant scope |
|--------|------|---------|------|--------------|
| GET | `/v1/workspaces/{workspace_id}/branches` | List branches (status, owner, source trace) | User JWT (member) or API key `branches:read` | `{workspace_id}` path + RLS |
| POST | `/v1/workspaces/{workspace_id}/branches` | **Fork**: create a branch from a trace fork point + intervention manifest; starts the Temporal replay workflow | User JWT (`editor`/`admin`) or API key `branches:write` | `{workspace_id}` path + RLS; requires `valid_for_fork` frame; audited |
| GET | `/v1/workspaces/{workspace_id}/branches/{branch_id}` | Read branch detail (status, fidelity, cost estimate, effect summary) | User JWT (member) or API key `branches:read` | `{workspace_id}` path + RLS |
| POST | `/v1/workspaces/{workspace_id}/branches/{branch_id}/cancel` | **Cancel** a running branch (deterministic-boundary stop) | User JWT (`editor`/`admin`) or API key `branches:write` | `{workspace_id}` path + RLS |
| GET | `/v1/workspaces/{workspace_id}/branches/{branch_id}/frames` | List branch-owned frames (post-fork steps) | User JWT (member) or API key `branches:read` | `{workspace_id}` path + object-store key prefix |
| POST | `/v1/workspaces/{workspace_id}/trial-sets` | **Repeated trials**: fork the same intervention `k` times (`TrialSet`) | User JWT (`editor`/`admin`) or API key `branches:write` | `{workspace_id}` path + RLS; bounded by `max_repeated_trial_k` |
| GET | `/v1/workspaces/{workspace_id}/trial-sets/{trial_set_id}` | Read trial-set aggregate summary | User JWT (member) or API key `branches:read` | `{workspace_id}` path + RLS |

> Mock definitions (`MockDefinition`) used during replay are managed under
> `/v1/workspaces/{workspace_id}/mocks` with API-key scopes `mocks:write` / `mocks:approve`;
> enumerated here for completeness of the fork/replay surface and detailed when the spec is
> scaffolded.

### 1.7 Tests & exports

`TestCase` (trace-to-test) and `ExportSnapshot` (dataset/test export). Export execution runs
in `services/export-worker`; delivery URLs are signed and expire (30 days).

| Method | Path | Purpose | Auth | Tenant scope |
|--------|------|---------|------|--------------|
| GET | `/v1/workspaces/{workspace_id}/tests` | List test cases | User JWT (member) or API key `exports:read` | `{workspace_id}` path + RLS |
| POST | `/v1/workspaces/{workspace_id}/tests` | Create a test case from a trace/branch (assertions, target format) | User JWT (`editor`/`admin`) | `{workspace_id}` path + RLS |
| GET | `/v1/workspaces/{workspace_id}/tests/{test_case_id}` | Read a test case | User JWT (member) or API key `exports:read` | `{workspace_id}` path + RLS |
| PATCH | `/v1/workspaces/{workspace_id}/tests/{test_case_id}` | Edit assertions / approve (`draft`→`approved`) | User JWT (`editor`/`admin`) | `{workspace_id}` path + RLS |
| GET | `/v1/workspaces/{workspace_id}/exports` | List export snapshots | User JWT (member) or API key `exports:read` | `{workspace_id}` path + RLS |
| POST | `/v1/workspaces/{workspace_id}/exports` | Create an export snapshot (query → mapping → target dialect); enqueues `export-worker` | User JWT (`editor`/`admin`) or API key `exports:write` | `{workspace_id}` path + RLS; redaction policy version + audit; restricted traces require explicit confirmation |
| GET | `/v1/workspaces/{workspace_id}/exports/{export_snapshot_id}` | Read export status + validation report | User JWT (member) or API key `exports:read` | `{workspace_id}` path + RLS |
| GET | `/v1/workspaces/{workspace_id}/exports/{export_snapshot_id}/download` | Get a signed download URL (audited; expires after 30 days) | User JWT (member) or API key `exports:read` | `{workspace_id}` path + object-store key prefix; audited |

### 1.8 WorkspaceLimits (operational quotas)

`WorkspaceLimits` are operational guardrails (concurrency, depth, wall-clock, token volume,
retention) — **no billing or metering**; the billing/credit model was removed in the OSS
pivot. `LimitUsage` is the read-only current-usage view.

| Method | Path | Purpose | Auth | Tenant scope |
|--------|------|---------|------|--------------|
| GET | `/v1/workspaces/{workspace_id}/limits` | Read effective `WorkspaceLimits` | User JWT (member) | `{workspace_id}` path + RLS |
| PUT | `/v1/workspaces/{workspace_id}/limits` | Update operational limits (concurrency, depth, wall-clock, token thresholds, retries) | User JWT (`admin`) | `{workspace_id}` path + RLS; audited |
| GET | `/v1/workspaces/{workspace_id}/limits/usage` | Read current `LimitUsage` (rolling token volume, concurrent branches) | User JWT (member) | `{workspace_id}` path + RLS |

### 1.9 Retention & redaction policies

| Method | Path | Purpose | Auth | Tenant scope |
|--------|------|---------|------|--------------|
| GET | `/v1/workspaces/{workspace_id}/retention-policy` | Read retention policy (`retention_days`, deletion behavior) | User JWT (`admin`) | `{workspace_id}` path + RLS |
| PUT | `/v1/workspaces/{workspace_id}/retention-policy` | Update retention/deletion policy | User JWT (`admin`) | `{workspace_id}` path + RLS; audited |
| GET | `/v1/workspaces/{workspace_id}/redaction-policy` | Read redaction rules (regex, key/path, secret patterns, allow/drop) | User JWT (`admin`) | `{workspace_id}` path + RLS |
| PUT | `/v1/workspaces/{workspace_id}/redaction-policy` | Update redaction policy (versioned, applied at ingest, irreversible) | User JWT (`admin`) | `{workspace_id}` path + RLS; audited |

### 1.10 BYOK / LLM-routing config

Bring-Your-Own-Key provider credential for the configured `LLM_PROVIDER` (one key per
workspace), envelope-encrypted at rest with the optional pluggable KEK (`KEK_PROVIDER`).
The secret is write-only over the API; reads return status/metadata only.

| Method | Path | Purpose | Auth | Tenant scope |
|--------|------|---------|------|--------------|
| GET | `/v1/workspaces/{workspace_id}/byok` | Read LLM-routing config status (`llm_routing_status`, provider, key set?) — never returns plaintext | User JWT (`admin`) | `{workspace_id}` path + RLS |
| PUT | `/v1/workspaces/{workspace_id}/byok` | Set/replace the workspace provider key (write-only; envelope-encrypted) | User JWT (`admin`) | `{workspace_id}` path + RLS; audited |
| POST | `/v1/workspaces/{workspace_id}/byok/disable` | Disable BYOK without deleting saved config | User JWT (`admin`) | `{workspace_id}` path + RLS; audited |
| DELETE | `/v1/workspaces/{workspace_id}/byok` | Delete the saved provider key | User JWT (`admin`) | `{workspace_id}` path + RLS; audited |

### 1.11 Admin surfaces (operator)

Operator/admin-panel endpoints. The audit trail (`AuditEvent`) is append-only and read-only
over the API. System banners are operational ops-comm messages pushed to active workbench
sessions over SSE (§3).

| Method | Path | Purpose | Auth | Tenant scope |
|--------|------|---------|------|--------------|
| GET | `/v1/workspaces/{workspace_id}/audit-events` | Read the workspace audit trail (immutable) | User JWT (`admin`) | `{workspace_id}` path + RLS |
| GET | `/v1/internal/banners` | List active/scheduled system banners | User JWT (operator admin) | Operator-scoped (cross-workspace) |
| POST | `/v1/internal/banners` | Create/update a system banner (pushed via Redis pub/sub → SSE) | User JWT (operator admin) | Operator-scoped (cross-workspace) |
| GET | `/v1/healthz` | Liveness/readiness probe | None (unauthenticated) | Not tenant-scoped |

---

## 2. OTLP ingest (FastAPI OTLP endpoint)

The native OpenTelemetry ingest surface. The **FastAPI OTLP endpoint** in `services/api` /
`services/ingest` **replaces the deprecated Cloudflare Workers OTLP gateway** (the legacy
`workers/otlp-gateway`, slated for removal). Spans are accepted, then enqueued onto **NATS**
(subject `forkreplay.otlp.ingest`; Redis Streams is the documented alternative via
`QUEUE_BACKEND`) for `services/ingest` to stitch into the frame/branch model, redact, and
write to ClickHouse + the object store + the Postgres index.

Two transports are exposed (standard OTLP), so existing OpenTelemetry exporters and the
`forkreplay-sdk` can point at ForkReplay with no custom client:

| Transport | Method | Path / service | Purpose | Auth | Tenant scope |
|-----------|--------|----------------|---------|------|--------------|
| **OTLP/HTTP (protobuf)** | POST | `/v1/traces` | Receive an `ExportTraceServiceRequest` as HTTP-protobuf (`Content-Type: application/x-protobuf`) | API key `traces:write` (ingest key) via header; GoTrue-validated where a user JWT is used | Workspace resolved from the ingest API key; spans tagged with that `workspace_id` before enqueue |
| **OTLP/gRPC** | gRPC | `opentelemetry.proto.collector.trace.v1.TraceService/Export` | Receive the same `ExportTraceServiceRequest` over the gRPC `TraceService` | API key `traces:write` (ingest key) via gRPC metadata | Workspace resolved from the ingest API key; `workspace_id` attribution on enqueue |

Notes:

- **Auth.** Ingest is authenticated by a workspace-scoped `ApiKey` carrying the
  `traces:write` scope (the "ingest key"), supplied in the OTLP request headers
  (HTTP) or call metadata (gRPC). Revoked keys cannot ingest new spans. The same
  GoTrue-JWT validation path applies to any user-token-authenticated ingest.
- **Tenant scoping.** There is no `{workspace_id}` in the OTLP path (OTLP path shapes are
  fixed by the spec); instead the workspace is **derived from the presented ingest key**,
  and every projected span/frame is written under that `workspace_id` (Postgres RLS,
  ClickHouse row policy, and `frames/<workspace_id>/...` object-store key prefix).
- **Content / sampling.** `Trace.source` records `otlp_http` vs `otlp_grpc`. The SDK can
  pre-sample (`FORKREPLAY_AUTO_SAMPLE`) before spans reach this endpoint.
- **OpenAPI note.** The OTLP/HTTP `POST /v1/traces` request/response bodies are the OTLP
  protobuf messages, not ForkReplay-authored schemas; the OpenAPI spec in
  `packages/contracts` should document the route + auth + content type and reference the
  upstream OTLP proto rather than re-declaring it. The gRPC `TraceService` is described by
  the upstream OTLP proto, not OpenAPI.

---

## 3. SSE (FastAPI, Redis pub/sub backed)

The **FastAPI SSE endpoint** in `services/api` streams server-sent events to the workbench.
It is backed by **Redis pub/sub** and replaces the deprecated `workers/sse-relay` (CF
Workers + Durable Object). `services/replay-worker` publishes branch-progress events and the
admin panel publishes system banners to Redis; `services/api` fans them out to connected
browser sessions.

| Method | Path | Purpose | Auth | Tenant scope |
|--------|------|---------|------|--------------|
| GET | `/v1/workspaces/{workspace_id}/events/stream` | SSE stream of **branch progress** events + **system banners** for the workspace (`text/event-stream`) | User JWT (member) | `{workspace_id}` path; subscriber only receives events for workspaces it is a member of |

Semantics:

- **Event channels.** Two event families are multiplexed on the stream: per-branch progress
  (state transitions `queued`→`running`→`completed`/`failed`/`cancelled`, step progress,
  token/cost updates) and operator **system banners** (from the `/v1/internal/banners`
  admin surface).
- **`Last-Event-ID` resume.** Each SSE event carries a monotonic `id:`. On reconnect the
  browser sends the standard `Last-Event-ID` request header; the endpoint replays buffered
  events after that ID from the Redis-backed buffer so the client resumes without gaps.
- **Auth.** Connection requires a valid GoTrue JWT; the user must be a member of
  `{workspace_id}`. The connection is rejected (or downgraded to banners-only) if membership
  cannot be verified.
- **Tenant scoping.** The `{workspace_id}` path segment plus membership check confines the
  stream to one workspace; Redis channels are namespaced per workspace so no cross-tenant
  event fan-out is possible.

---

## Coverage summary (for the contracts authors)

This inventory is complete enough to scaffold the OpenAPI spec in `packages/contracts`:

- **Control-plane REST** — workspaces, members, auth-policy, API keys, traces, branches
  (fork/replay) + trial-sets, tests, exports, WorkspaceLimits, retention/redaction policies,
  BYOK config, and admin/audit/banner surfaces. Every entry has method, path, purpose, auth
  requirement (GoTrue JWT — user vs workspace/API key), and a tenant-scoping note.
- **OTLP ingest** — OTLP/HTTP-protobuf (`POST /v1/traces`) and OTLP/gRPC (`TraceService`)
  via the native FastAPI OTLP endpoint, replacing the deprecated Cloudflare Workers OTLP
  gateway; ingest-key auth and key-derived workspace attribution.
- **SSE** — the FastAPI SSE stream (Redis pub/sub) for branch progress + system banners,
  with `Last-Event-ID` resume, GoTrue JWT auth, and per-workspace scoping.

Open items the contract authors will resolve when authoring the spec: exact request/response
schemas (Pydantic models → JSON Schema), pagination/filtering parameters, error envelope
shape, and the mock-definition sub-resource detail.

# ForkReplay — Milestone Issue List (Execution-Ready)

> **Status: execution-ready issue list.** This is the Plan §11 deliverable that converts the
> phased build sequence in [`../../../implementation-plan.md`](../../../implementation-plan.md)
> into a concrete, ordered set of milestone issues engineering can file and pick up directly.
> Each issue below gives **scope**, **acceptance criteria**, **dependencies/blocks**, and
> **suggested labels** (`phase:*` / `type:*`) so it can be filed as a GitHub issue with no
> further translation.

This list complements the live GitHub milestones (Phase 0 → Phase 6 already exist as
milestones #2–#8; the parent epic **Architecture & Milestone Breakdown (§11)** is milestone
#1 / issue **#1**). Where the live milestones are the *containers*, this document is the
*ordered, dependency-aware contents* — the build sequence and the re-gate made fileable.

> **OSS-pivot scope reminder.** ForkReplay is open-source and self-hostable (Apache-2.0).
> The control-plane Postgres is pluggable (`DB_MODE=supabase|custom|compose`); **ClickHouse
> is required in every mode** (no Postgres substitute). The managed-SaaS layer and all
> billing were **removed** in the OSS pivot — see the
> [OSS-pivot re-gate](#critical-path--oss-pivot-re-gate) below and
> [`../../../READINESS-GATE-REPORT.md`](../../../READINESS-GATE-REPORT.md).

---

## How to read each issue

Every issue is written in the same shape so it can be filed verbatim:

- **Scope** — 1–3 lines: what the issue delivers (the boundary, not the prose plan).
- **Acceptance criteria** — objective, machine-checkable or re-runnable bars (a test command,
  a CI gate, a measured threshold, a schema/contract check).
- **Dependencies / blocks** — which issues or phases gate it, and what it blocks downstream.
- **Suggested labels** — the `phase:*` and `type:*` labels to file it under.

**Label taxonomy** (already defined in the repo):

- **Phase:** `phase:architecture`, `phase:0-spikes`, `phase:1-foundation`,
  `phase:2-capture-inspect`, `phase:3-fork-mvp`, `phase:4-beta-complete`,
  `phase:5-hardening`, `phase:6-packaging`.
- **Type:** `type:epic`, `type:spike`, `type:feature`, `type:infra`, `type:docs`,
  `type:sdk`, `type:security`, `type:testing`, `type:ci`.

---

## Entry point and the schema-lock gate

- **Phase 0 spikes are the entry point.** Implementation begins with the Phase 0
  dependency-validation spikes (issues `M0.x` below). No product schema is frozen and no
  Phase 1 foundation issue starts until the critical-path spikes have produced written
  results — this is the explicit kickoff per Plan §3 and the re-gate.
- **The Phase 1 schema lock is gated on the epic.** The control-plane + ClickHouse schema
  lock (`M1.2`) is **blocked by the Architecture & Milestone Breakdown epic (issue #1)** — it
  may not land until the §11 architecture artifacts (service responsibilities, schema
  sketches, `DB_MODE` matrix, endpoint inventory, Temporal sketches, SDK outline, deploy
  outline, and **this issue list**) are merged, and until the schema-shaping spikes
  (`M0.1` OTel import matrix, `M0.4` ClickHouse layout) are green. This dependency is the
  reason §11 exists before Phase 1.

```
#1 Architecture & Milestone Breakdown epic ──gates──> M1.2 Phase 1 schema lock
Phase 0 critical-path spikes (M0.1, M0.4, M0.8, M0.10, M0.11) ──feed──> M1.2
```

---

## Phase 0 — Dependency-Validation Spikes (entry point)

**Milestone:** Phase 0 — Dependency-Validation Spikes. **Theme:** time-boxed spikes that
de-risk the hardest contracts on the OSS stack before anything is frozen. Each spike
produces a short written result plus runnable proof. **`M0.8` / `M0.11` / `M0.10` are the
highest-risk critical-path items.** All Phase 0 issues carry `phase:0-spikes` + `type:spike`
(infra-heavy ones add `type:infra`; security ones add `type:security`).

> Spikes whose risk came from a managed vendor were re-grounded on the OSS replacement or
> **dropped**: the Stripe credit-grants/meters dry-run and the Supabase Vault availability
> spike are **dropped** (billing removed; no Vault dependency), and the Cloudflare Workflows
> cold-start spike is **replaced** by Temporal bootstrap timing. See the re-gate section.

### M0.1 — OTel GenAI import matrix
- **Scope:** define accepted passive-ingest mappings (`gen_ai.*`, OpenInference, generic OTLP
  fallback) and the required fields for `inspect-only` / `replay-assisted` / `fork-grade`.
- **Acceptance criteria:** a versioned mapping table + a documented redaction/content-capture
  rule set, complete enough to freeze the initial normalization schema.
- **Dependencies / blocks:** no deps. **Blocks** `M1.2` (schema lock) and `M2.2` (ingest).
- **Suggested labels:** `phase:0-spikes`, `type:spike`, `type:sdk`.

### M0.2 — FastAPI OTLP receiver spike
- **Scope:** validate OTLP/HTTP-protobuf + OTLP/gRPC ingest against the FastAPI OTLP endpoint
  (the receive path that supersedes the deprecated Cloudflare Workers gateway).
- **Acceptance criteria:** valid trace batches accepted over both transports; workspace
  ingest-key auth enforced; invalid payloads/bad keys rejected predictably; normalized facts
  emitted to the next stage.
- **Dependencies / blocks:** relates to `M0.10`. **Blocks** `M2.2`.
- **Suggested labels:** `phase:0-spikes`, `type:spike`, `type:infra`.

### M0.3 — GoTrue auth & session boundary
- **Scope:** prove the user/session model across Next.js + FastAPI + bundled GoTrue, with
  Postgres RLS as the tenant-isolation primitive and an API-key ingest path.
- **Acceptance criteria:** login/signup/refresh works against bundled GoTrue; one shared
  JWT-validation path across web/API/ingest/workers; privileged DB creds never reach the
  browser; JWT validation identical across all three `DB_MODE` values.
- **Dependencies / blocks:** feeds `M0.21`. **Blocks** `M1.2`.
- **Suggested labels:** `phase:0-spikes`, `type:spike`, `type:security`.

### M0.4 — ClickHouse schema & query spike
- **Scope:** validate the physical ClickHouse layout for raw spans, normalized steps,
  messages, tool calls/results, and trace/branch summaries on single-node OSS ClickHouse.
- **Acceptance criteria:** candidate tables defined; 10k-span fixture load test run; query
  benchmarks captured for trace-open, DAG/timeline, message/tool search, and compare; TTL
  sketch documented.
- **Dependencies / blocks:** no deps. **Blocks** `M1.2` (schema lock).
- **Suggested labels:** `phase:0-spikes`, `type:spike`, `type:infra`.

### M0.5 — Promptfoo export spike
- **Scope:** confirm the first bundled non-generic trace-to-test mapping (Promptfoo).
- **Acceptance criteria:** one trace/branch exported to Promptfoo-compatible JSON/JSONL with
  provenance preserved; unsupported assertions produce warnings, not silent loss.
- **Dependencies / blocks:** no deps. **Blocks** `M3.5` / `M4` exporters.
- **Suggested labels:** `phase:0-spikes`, `type:spike`.

### M0.6 — Branch streaming spike (FastAPI SSE + Redis)
- **Scope:** validate branch-event streaming via FastAPI SSE + Redis pub/sub with
  `Last-Event-ID` resume (the path that supersedes the deprecated Cloudflare SSE relay +
  Durable Object).
- **Acceptance criteria:** SSE endpoint fans out branch events from a Redis channel; browser
  demo reconnects/resumes across a worker restart; event-retention decision documented.
- **Dependencies / blocks:** no deps. **Blocks** `M3.4`.
- **Suggested labels:** `phase:0-spikes`, `type:spike`, `type:infra`.

### M0.7 — Graph renderer spike (React Flow + ELK)
- **Scope:** validate React Flow + ELK as the trace-DAG / branch-tree renderer up to the
  ≤2k-node interactive target with progressive disclosure above.
- **Acceptance criteria:** rendering at 100/500/1k/2k/5k nodes with collapse/expand,
  selection, inspector linking; performance notes + fallback recommendation captured.
- **Dependencies / blocks:** relates to `M0.12`. **Blocks** `M2.3` DAG view.
- **Suggested labels:** `phase:0-spikes`, `type:spike`.

### M0.8 — End-to-end fork-start latency spike (Temporal) — HIGHEST-RISK
- **Scope:** validate fork-start **p95 < 3s** with Temporal-orchestrates-every-step + a
  pre-warmed worker pattern on the actual OSS stack — Temporal **replaced** the Cloudflare
  Workflows fork-start gate, which is **dropped**.
- **Acceptance criteria:** throwaway stub measures click → API → Temporal start → first
  provider call → first SSE event across variants V0–V3; **V3 hits p95 < 3s e2e** (or p95
  ≈4s accepted, or >5s escalated before Phase 3); cold-path floor captured.
- **Dependencies / blocks:** depends on `M0.9`, `M0.14`. **Blocks** `M3.2`.
- **Suggested labels:** `phase:0-spikes`, `type:spike`, `type:infra`.

### M0.9 — Object-store read latency spike (MinIO / S3)
- **Scope:** characterize cold + warm frame-read latency through the `ObjectStore`
  S3-compatible abstraction for 100 KB / 1 MB / 5 MB frames across MinIO and AWS S3.
- **Acceptance criteria:** p50/p95/p99 read times for cold/warm on MinIO and S3; Redis
  cache-hit-rate target (1 GB/replica, LRU) set; abstraction overhead confirmed negligible.
- **Dependencies / blocks:** **Blocks** `M0.8`.
- **Suggested labels:** `phase:0-spikes`, `type:spike`, `type:infra`.

### M0.10 — OTLP receiver + NATS/Redis throughput spike — HIGH-RISK
- **Scope:** confirm the queue-buffered ingest path hits **10k spans/sec/node** on NATS and
  on the Redis Streams alternative behind the `QueueConsumer` interface.
- **Acceptance criteria:** synthetic load through FastAPI OTLP → NATS → consumers clears the
  goal; the same load clears it on Redis Streams; throughput/latency/queue-depth/consumer-lag
  captured for both backends.
- **Dependencies / blocks:** relates to `M0.2`. **Blocks** `M2.2` and the Phase-1 ingest lock.
- **Suggested labels:** `phase:0-spikes`, `type:spike`, `type:infra`.

### M0.11 — LiteLLM vs rolled-translator spike (E6) — HIGHEST-RISK
- **Scope:** decide LiteLLM vs a thin in-house translator for cross-provider `tool_use` /
  `reasoning_details` round-trips across the pluggable provider set (OpenRouter / direct
  OpenAI/Anthropic / Ollama).
- **Acceptance criteria:** comparison run on OpenAI/Anthropic/Gemini tool-use + reasoning
  round-trips through the provider interface; one-page recommendation + maintenance estimate;
  choice locked before Phase 3.
- **Dependencies / blocks:** no deps. **Blocks** `M3.2`.
- **Suggested labels:** `phase:0-spikes`, `type:spike`, `type:sdk`.

### M0.12 — Real-world DAG-size measurement spike
- **Scope:** validate the ≤2k interactive DAG target against real production traces.
- **Acceptance criteria:** 20–30 real traces (LangGraph + OpenAI Agents-SDK + Claude SDK)
  measured; A10 target confirmed or progressive-disclosure thresholds revised.
- **Dependencies / blocks:** feeds `M0.7`. **Blocks** `M2.3` DAG view.
- **Suggested labels:** `phase:0-spikes`, `type:spike`.

### M0.13 — GoTrue against custom Postgres spike
- **Scope:** verify bundled GoTrue boots, migrates, and issues JWTs against a vanilla
  operator-supplied Postgres (the `custom` `DB_MODE`). Replaces the dropped Supabase Vault
  availability spike (no Vault dependency in the OSS product).
- **Acceptance criteria:** GoTrue migrates on a plain Postgres; signup → confirmation-email →
  login → refresh round-trips (console/SMTP sink); required roles/extensions/grants documented.
- **Dependencies / blocks:** feeds `M0.21`. **Blocks** `M1.2`.
- **Suggested labels:** `phase:0-spikes`, `type:spike`, `type:security`.

### M0.14 — Temporal workflow bootstrap timing
- **Scope:** measure `WorkflowClient.start()` → first activity on a self-hosted Temporal
  cluster (warm pool + worker-restart cases). Replaces the dropped Cloudflare Workflows
  cold-start measurement.
- **Acceptance criteria:** p50/p90/p95/p99 start-to-first-activity for warm and post-restart
  pools; speculative-start (signal-gated) pattern compared; feeds the `M0.8` budget.
- **Dependencies / blocks:** **Blocks** `M0.8`.
- **Suggested labels:** `phase:0-spikes`, `type:spike`, `type:infra`.

### M0.15 — `redacted_thinking` passthrough spike
- **Scope:** confirm `redacted_thinking` blocks survive a replay round-trip with `data`
  intact on both the direct-Anthropic and OpenRouter adapters.
- **Acceptance criteria:** recorded round-trip on each adapter; Anthropic accepts the response
  and the tool-use loop continues, or the per-adapter workaround is identified.
- **Dependencies / blocks:** relates to `M0.11`. **Blocks** `M3.2`.
- **Suggested labels:** `phase:0-spikes`, `type:spike`, `type:sdk`.

### M0.16 — Interleaved-thinking beta header propagation spike
- **Scope:** verify `anthropic-beta: interleaved-thinking-2025-05-14` propagates on the
  direct-Anthropic and OpenRouter adapters.
- **Acceptance criteria:** propagation mechanism confirmed per adapter (header vs
  `extra_body`); replay-worker implementation note written.
- **Dependencies / blocks:** relates to `M0.11`. **Blocks** `M3.2`.
- **Suggested labels:** `phase:0-spikes`, `type:spike`, `type:sdk`.

### M0.17 — Claude Agent SDK fork-grade fixture spike (A3)
- **Scope:** validate Claude Agent SDK as fork-grade through the OpenInference/OTel
  instrumentor path.
- **Acceptance criteria:** a 2-tool Claude Agent SDK script's spans, hooks, `session_id`, and
  checkpoint UUIDs flow cleanly through OTLP into the normalized schema; fork-grade confirmed
  or gaps identified.
- **Dependencies / blocks:** relates to `M0.1`. **Blocks** `M2.1` Claude adapter.
- **Suggested labels:** `phase:0-spikes`, `type:spike`, `type:sdk`.

### M0.20 — Optional operator-managed KEK spike
- **Scope:** stand up the optional operator-managed KEK (age/libsodium) for envelope-encrypting
  workspace BYOK provider keys at rest, and confirm the app runs with the KEK enabled and unset.
  Simplified from the prior multi-recipient key-custody ceremony, which is **removed** as a
  ForkReplay-operated obligation.
- **Acceptance criteria:** envelope encrypt/decrypt of a BYOK secret round-trips through the
  app's secret accessor; KEK-unset is a supported mode with the tradeoff documented; rotation
  documented as operator guidance.
- **Dependencies / blocks:** no deps (operational; does not block engineering). **Feeds** `M1.2`.
- **Suggested labels:** `phase:0-spikes`, `type:spike`, `type:security`.

### M0.21 — Pluggable-DB matrix bring-up spike (NEW)
- **Scope:** bring the control plane up under all three `DB_MODE` values and confirm GoTrue,
  RLS, migrations, and JWT validation behave identically.
- **Acceptance criteria:** app + GoTrue boot/migrate green in each mode; the RLS
  tenant-isolation conformance test passes in all three modes; cross-mode JWT validation works;
  per-mode prerequisites tabulated.
- **Dependencies / blocks:** depends on `M0.3`, `M0.13`. **Blocks** `M1.2`, `M5` A8 gate.
- **Suggested labels:** `phase:0-spikes`, `type:spike`, `type:security`.

### M0.22 — S3 storage-abstraction conformance spike (NEW)
- **Scope:** prove the `ObjectStore` abstraction is conformant across MinIO, AWS S3, and
  Azure Blob.
- **Acceptance criteria:** a put/get/head/list/delete + multipart + content-hash conformance
  suite passes on all three backends; behavioral differences documented, not load-bearing in
  app code.
- **Dependencies / blocks:** relates to `M0.9`. **Blocks** `M6.1` `ObjectStore` productionization.
- **Suggested labels:** `phase:0-spikes`, `type:spike`, `type:infra`.

### M0.23 — docker-compose end-to-end smoke spike (NEW)
- **Scope:** stand up the full stack via a throwaway candidate `deploy/docker-compose` and run
  a minimal product round-trip.
- **Acceptance criteria:** `docker compose up` reaches healthy; signup → ingest fixture → open
  → fork → run → compare passes on one host; single-host resource footprint documented.
- **Dependencies / blocks:** feasibility check. **Blocks** `M6.2` compose artifact.
- **Suggested labels:** `phase:0-spikes`, `type:spike`, `type:infra`.

### M0.24 — Helm chart lint/template spike (NEW)
- **Scope:** validate a candidate Helm skeleton with `helm lint` + `helm template`, with
  ClickHouse and Temporal as required dependencies.
- **Acceptance criteria:** `helm lint` clean; `helm template` renders valid manifests for the
  full service set incl. required ClickHouse + Temporal and the `DB_MODE` toggle; no
  "disable ClickHouse" value exists.
- **Dependencies / blocks:** feasibility check. **Blocks** `M6.3` Helm artifact.
- **Suggested labels:** `phase:0-spikes`, `type:spike`, `type:infra`.

### M0.25 — Terraform validate/plan spike — AWS + Azure (NEW)
- **Scope:** validate Terraform skeletons for AWS and Azure with `terraform validate` +
  `terraform plan` (no apply).
- **Acceptance criteria:** `validate` clean for both skeletons; `plan` produces a coherent
  plan against each provider with the required-ClickHouse constraint represented; provider
  gaps documented.
- **Dependencies / blocks:** feasibility check. **Blocks** `M6.4` Terraform artifact.
- **Suggested labels:** `phase:0-spikes`, `type:spike`, `type:infra`.

**Phase 0 exit:** all spikes have written results + proof; `M0.8` fork-start, `M0.10`
throughput, `M0.11` translator, and the 3-mode matrix (`M0.21`) decisions are settled.

---

## Phase 1 — Foundation, Contracts & Operability

**Milestone:** Phase 1 — Foundation, Contracts & Operability. **Theme:** stand up the
deployable, observable platform spine — repo layout, control-plane persistence with RLS,
contracts, observability, test foundation, and agent-instruction scaffolding. All issues
carry `phase:1-foundation`. **The schema lock (`M1.2`) is the gated centerpiece.**

### M1.1 — Repository & service layout
- **Scope:** monorepo layout for the OSS stack — `apps/web`, `services/{api,ingest,replay-worker,mock-gen-worker,export-worker}`, optional `services/scheduler`, `sdk/python`, `packages/contracts`; per-service container build + image-publish definitions.
- **Acceptance criteria:** every service directory exists with its `AGENTS.md`; CI builds each
  image; the deprecated `workers/*` + `workflows/cloudflare` dirs are documented as
  slated-for-removal (not deleted this pass) and `services/billing-batch-worker` is removed.
- **Dependencies / blocks:** depends on epic #1. **Blocks** all other Phase 1 issues.
- **Suggested labels:** `phase:1-foundation`, `type:infra`, `type:ci`.

### M1.2 — Control-plane schema lock + RLS (the gated schema lock)
- **Scope:** the control-plane Postgres schema (identical across all `DB_MODE` values) —
  workspaces + `workspace_limits`, members/invites, API keys, traces, sessions,
  step_buildability, branches, intervention manifests, mocks, tool/capability definitions,
  frames (+ `object_key`, `content_hash`), `frame_references`, `branch_event`, trial sets,
  exports, test cases, `admin_review_item`, audit (monthly partitions), `system_banners`;
  RLS on every tenant-scoped table; ClickHouse row policies on `workspace_id`. The billing
  tables (rate cards, usage/credit/meter, Stripe webhook ledger) are **removed**.
- **Acceptance criteria:** migrations apply clean in all three `DB_MODE` values; the
  tenant-isolation conformance test (RLS + ClickHouse row policies) is **green in all three
  modes** (A8 exit gate); audit-partition automation creates partitions one month ahead.
- **Dependencies / blocks:** **blocked by epic #1** and by `M0.1`, `M0.4`, `M0.21`.
  **Blocks** `M2.2`, `M3.1`.
- **Suggested labels:** `phase:1-foundation`, `type:security`, `type:infra`.

### M1.3 — API & contract baseline
- **Scope:** REST/OpenAPI skeleton, canonical ID/versioning rules, problem-details errors,
  pagination/filter conventions, idempotency rules, initial contract tests.
- **Acceptance criteria:** OpenAPI document validates; contract tests run in CI; idempotency
  enforced on mutating endpoints.
- **Dependencies / blocks:** depends on `M1.1`. **Blocks** Phase 2/3 endpoints.
- **Suggested labels:** `phase:1-foundation`, `type:feature`, `type:testing`.

### M1.4 — Observability & operations baseline
- **Scope:** optional self-hosted OTel collector + Grafana/Prometheus sink (opt-in); structured
  logs; metrics for auth/ingest/normalization/Temporal/replay/branch/mock/export/queue/SSE;
  distributed tracing; reference dashboards + first alerts; runbook skeleton. All `billing.*`
  metrics are **removed**.
- **Acceptance criteria:** every service emits OTLP and runs with no external sink configured;
  the named metrics are emitted; reference dashboards render.
- **Dependencies / blocks:** depends on `M1.1`. **Blocks** `M5` load/alert tuning.
- **Suggested labels:** `phase:1-foundation`, `type:infra`.

### M1.5 — Test foundation
- **Scope:** per-service unit harnesses; integration harness against the bundled-compose stack
  (Postgres + GoTrue, ClickHouse, MinIO, NATS/Redis, Temporal test server); tenant-isolation
  test matrix; seed fixtures (small trace, 5-step/two-tool, multi-step replay, restricted trace).
- **Acceptance criteria:** integration harness boots the stack and runs green; the
  tenant-isolation matrix is wired into CI; fixtures load.
- **Dependencies / blocks:** depends on `M1.1`, `M1.2`. **Blocks** all later test gates.
- **Suggested labels:** `phase:1-foundation`, `type:testing`.

### M1.6 — Agent-instruction scaffolding & docs harness
- **Scope:** root + per-service `AGENTS.md`/`CLAUDE.md` (incl. the "V1 deliberately-constrained
  scope" section); `docs-update` agent skill; the `docs-drift-check` CI gate; scope-creep guard.
- **Acceptance criteria:** `docs-drift-check` fails a PR touching the guarded path-globs without
  a matching `docs/**` edit; the scope guard flags re-introducing removed scope (e.g. the
  TypeScript SDK, which is **deprecated**/off-roadmap for V1).
- **Dependencies / blocks:** depends on `M1.1`. **Blocks** Phase 2 docs workstream.
- **Suggested labels:** `phase:1-foundation`, `type:docs`, `type:ci`.

**Phase 1 exit:** a deployable, observable skeleton with GoTrue auth, RLS + ClickHouse
row-policy conformance green in all three DB modes, contracts, optional KEK BYOK encryption,
audit-partition automation, `system_banners` over FastAPI/Redis SSE, and the docs harness live.

---

## Phase 2 — Capture & Inspect Vertical Slice

**Milestone:** Phase 2 — Capture & Inspect Vertical Slice. **Theme:** a developer can capture
a fork-grade trace with the Python SDK, ingest it, and inspect it in the product. All issues
carry `phase:2-capture-inspect`. **Exit gate: clean signup → fork-grade trace in ≤30 minutes
following only public docs.**

### M2.1 — Python SDK core + adapters
- **Scope:** explicit-capture core API (`checkpoint`, `start_conversation`, `register_tool`,
  `capture_tool_call`, `capture_stream`, `mark_step_complete`, redaction hints) + decorator
  sugar; the 3 fork-grade adapters (LangGraph, OpenAI Agents-SDK, Claude Agent SDK) + 6
  inspect-only adapters; `forkreplay-auto` one-line bootstrap + `.pth` env-var bootstrap;
  OTLP export with redaction-before-egress. Python-only in V1; the TypeScript SDK is **deprecated**/off-roadmap.
- **Acceptance criteria:** SDK unit coverage ≥90% line / ≥85% branch on `_core/`; adapter
  integration smokes pass; `forkreplay-auto` import-order tests pass; SDK version starts 0.1.0.
- **Dependencies / blocks:** depends on `M0.1`, `M0.17`, `M0.11`. **Blocks** `M2.2`, `M2.4`.
- **Suggested labels:** `phase:2-capture-inspect`, `type:sdk`, `type:testing`.

### M2.2 — Ingest & projection
- **Scope:** FastAPI OTLP receiver wired through NATS/Redis to stitch/redact/write consumers;
  canonical normalization into ForkReplay trace objects; ClickHouse projection writes;
  `ObjectStore` frame/checkpoint storage; Postgres trace registry + readiness summary.
- **Acceptance criteria:** a fixture trace ingests end-to-end and is queryable in ClickHouse;
  server-side redaction validation runs; golden-OTLP contract tests pass.
- **Dependencies / blocks:** depends on `M1.2`, `M2.1`, `M0.2`, `M0.10`. **Blocks** `M2.3`.
- **Suggested labels:** `phase:2-capture-inspect`, `type:infra`, `type:feature`.

### M2.3 — Trace detail UI
- **Scope:** trace list, trace detail summary, step timeline, raw-span fallback,
  fork-readiness panel, per-step fidelity badging, sessions view, and the initial DAG/tree
  view (≤2k nodes interactive; progressive disclosure above).
- **Acceptance criteria:** a captured trace can be opened, its steps inspected, and its
  fork-readiness understood; DAG renders within the validated node bounds.
- **Dependencies / blocks:** depends on `M2.2`, `M0.7`, `M0.12`. **Blocks** `M3` fork UI.
- **Suggested labels:** `phase:2-capture-inspect`, `type:feature`.

### M2.4 — Docs workstream (dedicated docs owner starts)
- **Scope:** `docs/quickstart/python.md` (the 30-minute path), SDK + integration docs
  (LangGraph / OpenAI Agents-SDK / Claude Agent SDK / auto), and the Claude SDK migration note.
- **Acceptance criteria:** the 30-minute first-fork-grade-trace acceptance test is wired into
  CI and passes; docs validated weekly by a non-engineer/tester.
- **Dependencies / blocks:** depends on `M1.6`, `M2.1`. **Blocks** Phase-2 exit.
- **Suggested labels:** `phase:2-capture-inspect`, `type:docs`.

**Phase 2 exit:** the 30-minute first-fork-grade-trace acceptance gate (A11) is green in CI.

---

## Phase 3 — Fork MVP & Generic Regression Output

**Milestone:** Phase 3 — Fork MVP & Generic Regression Output. **Theme:** prove the central
value loop — fork a real trace, resolve tools, run the branch through Temporal, compare, and
save a generic regression test. All issues carry `phase:3-fork-mvp`.

### M3.1 — Branch domain
- **Scope:** branch records + intervention-manifest persistence; initial fork-point
  validation; first intervention types (system/message edit, forced tool result); preflight
  for missing mocks + blocked execution.
- **Acceptance criteria:** a branch can be created from a valid fork point with a manifest;
  preflight blocks an unsatisfiable fork with a clear reason.
- **Dependencies / blocks:** depends on `M1.2`, `M2.3`. **Blocks** `M3.2`.
- **Suggested labels:** `phase:3-fork-mvp`, `type:feature`.

### M3.2 — Durable replay execution (Temporal)
- **Scope:** the Temporal workflow for the branch lifecycle (orchestrates every step incl. the
  first); speculative-start gated on a `user-confirmed-run` signal; replay-worker activities;
  pluggable provider envelope + `validateModelSwap`; deterministic state machine; idempotency
  ledger; cancellation cascade (3s p95 cancel-to-abort); `workflow_step_retries` retry policy.
  This replaces the deprecated Cloudflare Workflows orchestration.
- **Acceptance criteria:** a branch runs end-to-end through Temporal; fork-start p95 < 3s holds
  (per `M0.8`, accept 4s slip); cancellation aborts within the 3s p95 budget; retries bounded
  by the `WorkspaceLimits` CHECK constraint.
- **Dependencies / blocks:** depends on `M3.1`, `M0.8`, `M0.11`, `M0.14`. **Blocks** `M3.4`.
- **Suggested labels:** `phase:3-fork-mvp`, `type:infra`, `type:feature`.

### M3.3 — Tool resolution
- **Scope:** `mock`, `ai_mock` draft-placeholder, and `block` states wired into execution;
  matcher engine (`jsonata-python` + conformance suite); output-template renderer; scratchpad
  lifecycle; runtime enforcement that live tools are never executed in V1.
- **Acceptance criteria:** a branch resolves a captured tool via a mock and a matcher rule; a
  blocked tool halts execution; the conformance suite passes; no live tool call escapes.
- **Dependencies / blocks:** depends on `M3.1`. **Blocks** `M3.4`.
- **Suggested labels:** `phase:3-fork-mvp`, `type:feature`, `type:security`.

### M3.4 — Branch progress & compare
- **Scope:** FastAPI SSE backed by Redis pub/sub reading the `branch_event` log with
  `Last-Event-ID` resume (replaces the deprecated Cloudflare SSE relay + Durable Object);
  branch-run UI with pause/failure/completion; original-vs-branch step compare; first-divergence
  display.
- **Acceptance criteria:** branch progress streams live and resumes after a worker restart;
  the compare view shows the first divergence between original and branch.
- **Dependencies / blocks:** depends on `M3.2`, `M3.3`, `M0.6`. **Blocks** `M3.5`.
- **Suggested labels:** `phase:3-fork-mvp`, `type:feature`.

### M3.5 — Generic test conversion
- **Scope:** convert a successful branch into generic JSON test output; basic assertion
  proposal/review; test-case persistence.
- **Acceptance criteria:** a successful branch is saved as a generic regression test with
  proposed assertions; the test case persists and is retrievable.
- **Dependencies / blocks:** depends on `M3.4`, `M0.5`. **Blocks** Phase-4 exporters.
- **Suggested labels:** `phase:3-fork-mvp`, `type:feature`.

**Phase 3 exit:** a user can fork a real trace, run the branch through durable orchestration,
compare, and save it as a generic regression test.

---

## Phase 4 — Beta-Complete Product Loop

**Milestone:** Phase 4 — Beta-Complete Product Loop. **Theme:** the V1 breadth for a serious
beta — full intervention surface, AI mocks, trials, BYOK, admin panel, and the 3 exporters.
The schema configuration engine and the V1.1 exporter preview surface are **out of scope**
(V1.1). All issues carry `phase:4-beta-complete`.

### M4.1 — Full intervention surface + AI-mock workflow
- **Scope:** the full guided intervention surface; AI-generated mock workflow with
  review/approve/disable; admin-configurable default AI-mock model; capability-contract
  auto-inference.
- **Acceptance criteria:** all PRD intervention types are usable; an AI mock can be generated,
  reviewed, approved, and disabled; capability-contract cache keys behave as specified.
- **Dependencies / blocks:** depends on `M3.3`. **Blocks** Phase-4 exit.
- **Suggested labels:** `phase:4-beta-complete`, `type:feature`.

### M4.2 — Trials, estimation & operational caps
- **Scope:** repeated trials + trial-set aggregation; branch effect summary; optional
  **informational** replay estimation (±20% token/latency range, not charge) + `WorkspaceLimits`
  hard caps. There is no credit line item and no reasoning-rate charge — billing was **removed**.
- **Acceptance criteria:** a trial set aggregates repeated runs; estimation surfaces an
  informational range; operational caps enforce at the workspace limit.
- **Dependencies / blocks:** depends on `M3.2`. **Blocks** Phase-4 exit.
- **Suggested labels:** `phase:4-beta-complete`, `type:feature`.

### M4.3 — BYOK, provider config & admin panel
- **Scope:** BYOK via the pluggable provider interface + optional KEK envelope encryption (no
  Supabase Vault, which is **removed**); cross-provider model-swap UX (drop `reasoning_details`
  with a warning); BYOK usage tracking as an operational signal; the V1 admin panel locked at 5
  surfaces (limits, auth-policy, members, BYOK/provider config, retention/redaction).
- **Acceptance criteria:** a workspace runs a branch on its own provider key; the 5 admin
  surfaces are editable without a code deploy; no rate-card/billing surfaces exist.
- **Dependencies / blocks:** depends on `M3.2`, `M0.20`. **Blocks** Phase-4 exit.
- **Suggested labels:** `phase:4-beta-complete`, `type:feature`, `type:security`.

### M4.4 — Audit, retention & branch-tree navigation
- **Scope:** audit coverage for critical actions; retention/deletion mechanics; branch-tree
  navigation + recursive forks; reasoning-token transparency + prompt-cache-bust compare.
- **Acceptance criteria:** critical actions emit audit rows; retention/deletion runs; recursive
  forks navigate correctly.
- **Dependencies / blocks:** depends on `M3.4`. **Blocks** Phase-4 exit.
- **Suggested labels:** `phase:4-beta-complete`, `type:feature`, `type:security`.

### M4.5 — Three V1 exporters
- **Scope:** generic trajectory JSONL, generic JSON test case, and Promptfoo exporters on a
  thin internal mapping interface (the V1.1 schema engine will replace it).
- **Acceptance criteria:** each exporter produces a valid artifact with provenance; unsupported
  assertions warn rather than silently drop.
- **Dependencies / blocks:** depends on `M3.5`, `M0.5`. **Blocks** `M5` export previews.
- **Suggested labels:** `phase:4-beta-complete`, `type:feature`.

**Phase 4 exit:** the primary debugging workflow works end-to-end with realistic failures,
repeated-trial confidence, approved mocks, operational caps, and the three exporters.

---

## Phase 5 — V1 Self-Host Bring-Up Hardening

**Milestone:** Phase 5 — V1 Self-Host Bring-Up Hardening. **Theme:** harden the product and
add smoke-level self-host gates. Pen-test, public-status-page, and billing/refund work are all
**removed** from this phase. All issues carry `phase:5-hardening`.

### M5.1 — Export previews + onboarding/docs
- **Scope:** export previews, validation reports, and delivery destinations for the 3 exporters;
  onboarding flow; the single-tenant (default-workspace) quickstart as the canonical self-host
  onboarding path; runbooks (ingest, replay, BYOK/provider, exports, deletion, backup/restore,
  KEK rotation).
- **Acceptance criteria:** each exporter shows a preview + validation report; the quickstart is
  documented end-to-end; runbooks exist for each named operation.
- **Dependencies / blocks:** depends on `M4.5`. **Blocks** Phase-5 exit.
- **Suggested labels:** `phase:5-hardening`, `type:docs`, `type:feature`.

### M5.2 — Load tests
- **Scope:** ingest throughput (10k spans/sec/node via NATS/Redis), trace-open latency
  (ClickHouse), branch-start latency (fork-start p95 < 3s on Temporal; accept 4s slip), compare
  query latency — run against the bundled-compose stack.
- **Acceptance criteria:** each load target is measured and meets its bar (or the accepted
  slip), with results recorded.
- **Dependencies / blocks:** depends on `M1.4`, `M3.2`, `M4`. **Blocks** Phase-5 exit.
- **Suggested labels:** `phase:5-hardening`, `type:testing`.

### M5.3 — Security verification (A8 enforcement gate)
- **Scope:** Postgres RLS + ClickHouse row-policy tests + tenant-isolation CI matrix **in all
  three DB modes**; GoTrue JWT negative tests (expired/forged/cross-mode); authz + API-key
  misuse tests; KEK access-boundary tests; logged-secret canary regression.
- **Acceptance criteria:** the A8 tenant-isolation matrix is **green in all three DB modes**
  (launch blocker); all negative tests pass; the secret canary catches a planted leak.
- **Dependencies / blocks:** depends on `M1.2`, `M0.21`, `M4.3`. **Blocks** launch.
- **Suggested labels:** `phase:5-hardening`, `type:security`, `type:testing`.

### M5.4 — Self-host smoke gates
- **Scope:** `docker compose up` end-to-end smoke (signup → ingest → fork → run → compare on
  one host); `helm lint` + `helm template` clean; `terraform validate` + `terraform plan`
  clean for AWS + Azure. Full live verification is deferred to Phase 6.
- **Acceptance criteria:** the compose smoke passes; `helm lint`/`template` are clean with
  ClickHouse + Temporal required (no disable toggle); both Terraform skeletons `validate`/`plan`.
- **Dependencies / blocks:** depends on `M0.23`, `M0.24`, `M0.25`. **Blocks** `M6`.
- **Suggested labels:** `phase:5-hardening`, `type:infra`, `type:testing`.

### M5.5 — Trust posture, drills & docs-drift audit
- **Scope:** the `TRUST.md` / trust-posture page (launch blocker); quarterly backup/restore
  drill runbook (operator-owned RPO); KEK-rotation + object-store-retrieval drills; a
  documentation-drift audit across all V1 GA features incl. deploy docs.
- **Acceptance criteria:** `TRUST.md` is live and reviewed; drill runbooks exist; every V1 GA
  feature has docs + a `docs-update` round-trip; the billing/refund exit gates are **removed**.
- **Dependencies / blocks:** depends on `M1.6`, `M4`. **Blocks** launch.
- **Suggested labels:** `phase:5-hardening`, `type:docs`, `type:security`.

**Phase 5 exit:** V1 is feature-complete, observable, test-backed; the A8 gate is green in all
three DB modes; `TRUST.md` is live; the three self-host smoke gates pass.

---

## Phase 6 — Deployment Packaging & Abstraction Layers (FUTURE)

**Milestone:** Phase 6 — Deployment Packaging & Abstraction Layers (FUTURE). **Theme:** produce
the actual deployment artifacts + productionized abstraction layers a self-hoster runs.
Sequenced as future work (smoke-level feasibility was proven in Phase 0 spikes + Phase 5
gates). All issues carry `phase:6-packaging`.

### M6.1 — Productionized abstraction layers
- **Scope:** harden `AuthProvider`/GoTrue client, `ObjectStore` (MinIO/S3/Azure Blob),
  `QueueConsumer` (NATS + Redis Streams), Temporal workers, the Redis SSE relay, and the
  FastAPI OTLP endpoint — the last of which replaces the deprecated Cloudflare Workers OTLP
  gateway.
- **Acceptance criteria:** `ObjectStore` passes the `M0.22` conformance suite in production
  form; one `QueueConsumer` interface drives both backends; the FastAPI OTLP/SSE paths replace
  the deprecated `workers/*` projects.
- **Dependencies / blocks:** depends on `M0.22`, `M5.4`. **Blocks** `M6.2`–`M6.4`.
- **Suggested labels:** `phase:6-packaging`, `type:infra`.

### M6.2 — docker-compose artifact (single-host / dev)
- **Scope:** `deploy/docker-compose/` bundling web + services + scheduler + GoTrue + Temporal +
  NATS + Redis + **required OSS ClickHouse** + MinIO + Postgres, plus an optional observability
  profile; `DB_MODE=compose` default; single-tenant default-workspace quickstart.
- **Acceptance criteria:** `docker compose up` end-to-end smoke passes on a clean host (the
  published quickstart); ClickHouse is present and required.
- **Dependencies / blocks:** depends on `M6.1`, `M0.23`. **Blocks** packaging exit.
- **Suggested labels:** `phase:6-packaging`, `type:infra`, `type:ci`.

### M6.3 — Helm chart (Kubernetes)
- **Scope:** `deploy/helm/` chart for the full service set with **ClickHouse and Temporal as
  required dependencies** (no disable toggle) and the `DB_MODE` value.
- **Acceptance criteria:** `helm lint` + `helm template` clean in CI; a full cluster `helm
  install` + smoke is the exit; no "disable ClickHouse" value exists.
- **Dependencies / blocks:** depends on `M6.1`, `M0.24`. **Blocks** packaging exit.
- **Suggested labels:** `phase:6-packaging`, `type:infra`, `type:ci`.

### M6.4 — Terraform skeletons (AWS + Azure)
- **Scope:** `deploy/terraform/aws/` + `deploy/terraform/azure/` — object store, managed-or-self
  ClickHouse, Temporal, container services, and `DB_MODE` wiring, with the required-ClickHouse
  constraint represented.
- **Acceptance criteria:** `terraform validate` + `plan` clean in CI; a guarded `apply` against
  a scratch account is the live-verification exit.
- **Dependencies / blocks:** depends on `M6.1`, `M0.25`. **Blocks** packaging exit.
- **Suggested labels:** `phase:6-packaging`, `type:infra`, `type:ci`.

### M6.5 — Remove deprecated workers/workflows projects
- **Scope:** delete the deprecated `workers/otlp-gateway`, `workers/sse-relay`, and
  `workflows/cloudflare` projects once their FastAPI/Temporal replacements are proven in this
  phase. (These were retained secret-scrubbed only as transition references.)
- **Acceptance criteria:** the deprecated projects are removed; CI/builds reference only the
  FastAPI/Temporal replacements; no Cloudflare-queue or Cloudflare-workflow code path remains.
- **Dependencies / blocks:** depends on `M6.1`. **Blocks** packaging exit.
- **Suggested labels:** `phase:6-packaging`, `type:infra`.

**Phase 6 exit:** a new operator can stand up ForkReplay from a public repo via any one of
docker-compose, Helm, or Terraform (AWS/Azure); ClickHouse is required in every path; the
abstraction layers are productionized; the deprecated `workers/*` + `workflows/cloudflare`
projects are removed.

---

## Critical path & OSS-pivot re-gate

This section captures the ordering from the build sequence and the **OSS-pivot re-gate** in
[`../../../READINESS-GATE-REPORT.md`](../../../READINESS-GATE-REPORT.md). The re-gate verdict
is **READY (re-gated)**: the product contract is unchanged by the pivot; the infrastructure
substrate is swapped to OSS and billing is removed.

### Critical-path ordering

```
Phase 0 spikes (ENTRY POINT)
  highest-risk: M0.8 fork-start, M0.11 translator, M0.10 ingest throughput
  schema-shaping: M0.1 OTel matrix, M0.4 ClickHouse layout
  OSS-stack: M0.21 3-mode matrix, M0.22 S3 conformance, M0.14 Temporal bootstrap
        │
        ▼
#1 Architecture & Milestone Breakdown epic ──gates──▶ M1.2 Phase 1 schema lock
        │
        ▼
Phase 1 foundation (M1.1 layout → M1.2 schema lock + RLS → M1.3 contracts → M1.4–M1.6)
        │
        ▼
Phase 2 capture/inspect (M2.1 SDK → M2.2 ingest → M2.3 trace UI; gate: 30-min trace)
        │
        ▼
Phase 3 fork MVP (M3.1 branch → M3.2 Temporal replay → M3.3 tools → M3.4 compare → M3.5 test)
        │
        ▼
Phase 4 beta-complete (interventions, AI mocks, trials, BYOK + admin, 3 exporters)
        │
        ▼
Phase 5 hardening (load tests, A8 gate in all 3 DB modes, smoke gates, TRUST.md)
        │
        ▼
Phase 6 packaging (abstraction layers → compose/Helm/Terraform → remove deprecated workers)
```

The standing **A8 enforcement gate** (Postgres RLS + ClickHouse row policies + tenant-isolation
CI matrix) carries forward unchanged in intent and must now pass **in all three DB modes**.

### OSS-pivot re-gate — gates that changed

The pivot from a managed multi-vendor SaaS to an open-source, self-hostable product re-grounds
the gates. Per the re-gate:

**Prior gates now VOID (no dependency left to verify):**

- The **Stripe** credit-grants + meter-events dry-run and the billing chaos run are **removed** —
  billing is **removed** entirely (no purchase/grant/meter/refund path).
- The **Supabase Vault** free-tier availability spike is **dropped** — there is no Vault
  dependency; BYOK secrets are env/secret-supplied with an optional operator-managed KEK.
- The Supabase Pro auto-upgrade automation is **dropped** — no managed project to flip.
- The **Cloudflare Workflows** cold-start gate is **replaced** by the Temporal bootstrap-timing
  gate (`M0.14`).
- The billing/refund launch-blockers, reconciliation alarms, the cost-estimate-ratio SLO, and
  all `billing.*` metrics are **removed**; the multi-recipient key-custody ceremony is
  **demoted** to the optional operator-managed KEK (`M0.20`); managed-RPO/restore framings are
  **withdrawn** as ForkReplay obligations (self-hosters own RPO/backup).

**New OSS gates ADDED (smoke-level in Phase 0/5; full live verification deferred to Phase 6):**

1. 3-mode DB matrix bring-up (`M0.21`) — green in `supabase` / `custom` / `compose`.
2. GoTrue cross-mode JWT validation (`M0.3` + `M0.21`).
3. GoTrue against a vanilla custom Postgres (`M0.13`, replacing the Vault spike).
4. Temporal workflow bootstrap timing (`M0.14`, replacing the Cloudflare-Workflows cold-start gate).
5. NATS / Redis ingest throughput (`M0.10`) — the Cloudflare-Queues throughput path is
   **replaced** by the NATS/Redis `QueueConsumer`.
6. S3-abstraction conformance across MinIO / AWS S3 / Azure Blob (`M0.22`).
7. docker-compose end-to-end smoke (`M0.23` + `M5.4`).
8. Helm `lint`/`template` with ClickHouse + Temporal required (`M0.24` + `M5.4`).
9. `terraform validate`/`plan` for AWS + Azure (`M0.25` + `M5.4`).
10. Optional operator-managed KEK round-trip + clean degradation when unset (`M0.20`).

**Standing constraint reaffirmed: ClickHouse is REQUIRED.** "Pluggable Postgres" applies to the
control plane only. ClickHouse ships bundled OSS in compose and is a required dependency in Helm
and Terraform — there is no "disable ClickHouse" option, and any proposal to drop or substitute
it is a re-gate-level change, not a configuration toggle.

**Deferral note.** This re-gate clears the product and the substrate, and clears packaging at
**smoke level** only. End-to-end deployment verification (`docker compose up` on a clean host,
`helm install` against a real cluster, `terraform apply` against scratch AWS/Azure accounts) is
**deferred to Phase 6**, which owns the live-apply exits and the removal of the deprecated
`workers/*` + `workflows/cloudflare` projects.

---

## Filing checklist

When filing these as GitHub issues:

- File each `M*.x` as one issue, copying its **scope / acceptance criteria / dependencies-blocks
  / suggested labels** verbatim.
- Attach the `phase:*` + `type:*` labels listed on the issue.
- Link each issue to its phase milestone (Phase 0 → Phase 6 are milestones #2–#8) and reference
  the parent epic **#1** in the body (`Part of #1`).
- Encode the dependency edges using GitHub issue references (`Depends on #…`, `Blocks #…`) so the
  critical-path ordering above is reproducible in the tracker.
- The Phase 1 schema lock (`M1.2`) must reference its block on epic **#1** and on the
  schema-shaping spikes (`M0.1`, `M0.4`, `M0.21`).

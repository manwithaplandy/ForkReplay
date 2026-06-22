# ForkReplay V1 Concrete Implementation Plan

**Status:** Draft v0.4
**Owner:** Andrew
**Last updated:** 2026-06-21
**Related:** `agent-trace-fork-prd.md` (v0.9), `implementation-readiness-spec.md` (v0.5), `competitive_analysis.md` (v0.4), `READINESS-GATE-REPORT.md`

This plan translates the settled product and architecture decisions into a build sequence. It is intentionally ordered to validate the hardest contracts early, frontload infrastructure/auth/observability/docs, and then prove the full ForkReplay product loop through progressively richer vertical slices.

**v0.4 — OSS self-host pivot.** ForkReplay converts from a managed multi-vendor SaaS to an open-source, self-hostable product under **Apache-2.0** (chosen over MIT for the explicit patent grant). There is no retained managed-SaaS layer. The full architecture delta is in §1; the load-bearing changes are: the control-plane database is pluggable (`DB_MODE=supabase|custom|compose`); auth is **GoTrue** (Supabase Auth OSS) bundled in *all* DB modes with native Postgres **RLS** for tenant isolation; durable orchestration moves from Cloudflare Workflows to self-hosted **Temporal**; the ingest queue moves from Cloudflare Queues to **NATS** (Redis Streams alternative); live streaming moves from Cloudflare Workers SSE + Durable Objects to **FastAPI SSE + Redis pub/sub**; OTLP ingress moves from the Cloudflare Workers gateway to a **FastAPI OTLP endpoint** in ingest/api; object storage moves from Cloudflare R2 to an **S3-compatible abstraction** (MinIO in compose / AWS S3 / Azure Blob); LLM routing, SMTP, and the KEK become **pluggable**; and **billing is removed entirely** (no Stripe, no `billing-batch-worker`, no credit/meter object model — only operational `WorkspaceLimits` remains). **ClickHouse stays REQUIRED** as the columnar span/frame analytics store in every mode — "pluggable Postgres" applies to the control plane only (see §1). The product build sequence (SDK → ingest → trace inspect → fork engine → compare → exporters → mocks) is unchanged; only the infrastructure substrate and billing are swapped. New deployment-packaging work (docker-compose, Helm, Terraform for AWS + Azure) and the abstraction layers are sequenced as **future** Phase 6 deliverables — this plan authors none of that code now.

The pre-pivot history is preserved for context: v0.3 incorporated the May 12 planning round-3 decisions and v0.2 the round-2 decisions; the managed-SaaS specifics of those rounds (Supabase Pro auto-upgrade at $1k MRR, Stripe refund batch cadence, Supabase Vault custody, CF Workflows fork-start budget) are now **void** under the OSS pivot and are called out as such where they appear. See the PRD v0.9 changelog and the `READINESS-GATE-REPORT.md` "OSS Pivot Re-Gate" section for the full delta.

---

## 1. Locked Implementation Direction

The plan assumes these decisions are fixed for V1. The pivot is from a managed multi-vendor SaaS to an **open-source, self-hostable** product: every line item below is the OSS target. Where it replaces a pre-pivot managed dependency, the prior decision is noted in parentheses for the audit trail.

### Distribution and licensing

- **License:** Apache-2.0 (was: closed-source managed SaaS). Permissive, with an explicit patent grant — chosen over MIT for that grant.
- **Distribution:** OSS-only. Self-hostable from a public repository. Multiple deployment options ship as artifacts (docker-compose for single-host / dev; Helm for Kubernetes; Terraform skeletons for AWS + Azure) — authored as Phase 6, not now.
- **Tenancy model:** Multi-tenant core retained (Postgres RLS enforces tenant isolation), with a documented **single-tenant quickstart** that runs everything against a default workspace. Multi-tenant SaaS hosting is not a ForkReplay-operated offering.

### Runtime and hosting

- **Frontend:** Next.js workbench (App Router + RSC) shipped as a **standalone container** (was: Vercel-hosted).
- **Backend services:** Python 3.12 + FastAPI, runnable on **any container host** — docker-compose, Kubernetes, or a single VM (was: Railway-specific).
- **Public API:** REST + OpenAPI, plus native OTLP ingest (HTTP-protobuf + gRPC) served by a **FastAPI OTLP endpoint** in ingest/api (was: Cloudflare Workers OTLP gateway). The gateway worker is deprecated/slated-for-removal.

### Control plane (pluggable)

- **Control-plane database:** Pluggable **`DB_MODE=supabase|custom|compose`** (was: Supabase managed Postgres only).
  - `supabase` — point at an existing Supabase project (managed or self-hosted Supabase).
  - `custom` — operator-supplied Postgres connection string (any conformant Postgres ≥ the documented floor).
  - `compose` — bundled Postgres container for single-host / dev.
- **Auth:** **GoTrue** (Supabase Auth OSS) bundled in **all** DB modes. The app validates GoTrue-issued JWTs everywhere (web, API, ingest, workers). Native Postgres **RLS** is the tenant-isolation primitive (was: Supabase Auth as a managed service). There is no proprietary auth path.
- **Tenant isolation:** Postgres RLS on every tenant-scoped table + ClickHouse row policies on `workspace_id`. Unchanged in intent from the pre-pivot defense-in-depth posture; now enforced identically across all three DB modes.

### Analytics store (standing constraint — NOT pluggable)

- **Trace/query store:** **OSS ClickHouse — REQUIRED in every deployment mode** (was: ClickHouse Cloud). ClickHouse is the columnar span/frame analytics store and has **no Postgres substitute**: the V1 trace-open, DAG/timeline, message/tool search, and compare query latencies depend on columnar storage. "Pluggable Postgres" applies to the **control plane only** — ClickHouse ships bundled OSS in docker-compose and is a required dependency in Helm and Terraform. This is a constraint, not a choice; it is documented prominently in the deploy docs and the Helm/Terraform variable surfaces have no "disable ClickHouse" option.

### Storage, queue, streaming, orchestration

- **Object storage:** **S3-compatible abstraction** behind an `ObjectStore` interface (was: Cloudflare R2). MinIO in compose; AWS S3 or Azure Blob in cloud deploys. Holds frames, exports, audit-cold-archive.
- **Ingest queue:** **NATS** between the FastAPI OTLP endpoint and the stitch/redact/write consumers (was: Cloudflare Queues). **Redis Streams** is the documented alternative behind the same `QueueConsumer` interface. The CF Queues path is removed.
- **Live streaming / SSE:** **FastAPI SSE + Redis pub/sub** for branch progress and system banners, with `Last-Event-ID` resume (was: Cloudflare Workers SSE relay + per-branch Durable Object). The SSE-relay worker and Durable Object are deprecated/slated-for-removal.
- **Durable orchestration:** **Temporal** (self-hosted) orchestrates the branch lifecycle, every step including the first (was: Cloudflare Workflows). The Temporal worker pool runs alongside the Python services. The `workflows/cloudflare` project is deprecated/slated-for-removal.

### Secrets, LLM routing, email

- **Secrets / BYOK:** Operator and workspace keys supplied via **environment variables / mounted secrets**, with an **optional KEK** (operator-managed, age/libsodium) for envelope encryption of workspace BYOK secrets at rest (was: Supabase Vault + `replay_worker_byok` role). **No Vault dependency.** The KEK custody is operator-managed; the prior multi-recipient ceremony is simplified accordingly.
- **LLM routing:** **Pluggable** execution provider — OpenRouter, direct OpenAI/Anthropic, or **Ollama** for fully local inference (was: OpenRouter as the only adapter). The internal provider interface is unchanged; OSS adds the direct-provider and Ollama adapters.
- **Email:** **Pluggable SMTP** — Resend, generic SMTP, or a console/no-op sink (was: Resend only). Required because GoTrue sends signup/confirmation/reset email; the console sink keeps single-host dev zero-config.

### SDK, adapters, exporters, admin

- **SDK:** Explicit-capture core API with decorator ergonomics where safe; `forkreplay-auto` one-line bootstrap is the canonical onboarding path. Python-only in V1; TypeScript SDK is V2+. (Unchanged by the pivot.)
- **Framework adapters:** 3 fork-grade (LangGraph + OpenAI Agents SDK + Claude Agent SDK) + 6 inspect-only (LlamaIndex, Pydantic AI, smolagents, Strands, AutoGen, CrewAI) via OpenInference. (Unchanged.)
- **Exporters:** 3 hard-coded at V1 GA (generic trajectory JSONL, generic JSON test case, Promptfoo). Schema engine + 8 additional exporters are V1.1 (no preview surface in V1). (Unchanged.)
- **Admin panel:** Locked at 5 surfaces (per-workspace limits, auth-policy, member management, BYOK config, retention/redaction). (Unchanged — note that BYOK config now governs the pluggable provider keys + optional KEK, not Vault.)

### Billing — REMOVED

- **Billing:** **Removed from the self-host product.** No Stripe, no `services/billing-batch-worker`, no credit/meter object model (no `usage_event`, `credit_pack_grants`, `byok_usage_event`, `stripe_webhooks_processed`, no rate-card/reasoning-rate metering for charge). Only **operational `WorkspaceLimits`** remains, to bound resource use per workspace. Cost-estimation UX that surfaced *charge* is dropped; any retained estimate is informational only. (Was: Stripe Billing Credits + Meter Events v2 as system of record.)

### Observability and CI/CD

- **Observability sink:** Optional self-hosted **OTel collector + Grafana/Prometheus** (was: Grafana Cloud as a required managed sink). Observability is opt-in for self-hosters; services emit OTLP and run without an external sink configured.
- **CI/CD:** GitHub Actions building and publishing the container images and the deployment artifacts (compose/Helm/Terraform). No cloud-vendor OIDC federation is required to run ForkReplay; the prior Cloudflare/Railway/Supabase token wiring is removed.

### Trust posture and post-V1

- **Trust posture:** No public SLA, no public status page, no third-party pen-test attestation in V1. Internal SLO of 99.0% monthly availability for any reference deployment; self-hosters own their own availability. The `system_banners` mechanism is retained, now backed by Postgres + the FastAPI/Redis SSE channel (was: Workers SSE banner channel).
- **Post-V1:** AG-UI for agent-driven branching/debugging interfaces.

---

## 2. Delivery Strategy

The build sequence is a **core-loop vertical slice with infrastructure and auth frontloaded**:

1. Prove the contracts that would cause the most rework if wrong.
2. Stand up production-shaped infrastructure, auth, monitoring, and tests early.
3. Ship the smallest real user journey end to end.
4. Add the replay engine and compare loop before broadening exports and convenience features.
5. Harden with security, limits, retention, load tests, and operational runbooks before V1 launch.

The target V1 loop remains:

1. Create workspace.
2. Capture a fork-grade trace with the Python SDK.
3. Ingest and inspect it.
4. Fork from a valid step.
5. Resolve downstream tools through `mock`, `ai_mock`, or `block`.
6. Run the branch through durable orchestration.
7. Compare outcomes.
8. Convert the branch into a generic regression test, then export richer formats as the mapping engine lands.

---

## 3. Phase 0: Dependency-First Validation Spikes

These spikes happen before the implementation plan is treated as fully de-risked. Each spike should produce a short written result plus runnable proof code or queries where practical. Spikes 0.8 / 0.9 / 0.12 are the highest-risk; treat them as critical-path.

**OSS-pivot note (v0.4):** This spike list is re-grounded on the self-host stack. Spikes whose risk came from a managed vendor are either re-spiked against the OSS replacement (0.8 → Temporal, 0.10 → NATS/Redis, 0.9 → MinIO/S3) or **dropped** because the dependency is gone (0.13 Supabase Vault, 0.14 CF Workflows cold-start, 0.18/0.19 Stripe + Supabase-Pro). New self-host spikes are appended (0.21–0.25) covering the pluggable-DB matrix, the S3 storage abstraction, and IaC bring-up. The dropped/replaced gates are enumerated in `READINESS-GATE-REPORT.md` "OSS Pivot Re-Gate."

### 0.1 OTel GenAI Import Matrix

Goal:
- Define accepted passive-ingest mappings and fork-grade capture requirements.

Deliverables:
- Versioned mapping table for current `gen_ai.*`, older GenAI conventions, OpenInference-compatible shapes, generic OTLP fallback, and ForkReplay SDK canonical fields.
- Required fields for `inspect-only`, `replay-assisted`, and `fork-grade`.
- Redaction/content-capture implications documented.

Exit:
- Ingest normalization rules are clear enough to freeze the initial internal schema.

### 0.2 OTLP Receiver Spike

Goal:
- Validate OTLP/HTTP protobuf and OTLP/gRPC ingest against the **FastAPI OTLP endpoint** in ingest/api (replaces the CF Workers gateway).

Deliverables:
- FastAPI receiver accepts valid trace batches over HTTP-protobuf and gRPC.
- Workspace ingest-key auth works.
- Invalid payloads and bad keys fail predictably.
- Raw batch metadata and normalized facts are emitted to the next pipeline stage (the NATS/Redis queue, see 0.10).

Exit:
- The ingest lane is viable without architectural changes, with no Cloudflare component on the receive path.

### 0.3 GoTrue Auth and Session Boundary

Goal:
- Prove the user/session model for Next.js, FastAPI, **GoTrue**, and workspace authorization, with GoTrue bundled (not consumed as a managed Supabase service).

Deliverables:
- Login/signup/session refresh path against bundled GoTrue.
- Backend GoTrue-JWT validation path shared by web, API, ingest, and workers.
- Workspace membership and role checks enforced via Postgres RLS.
- API-key ingest auth path.
- Proof that privileged DB/service credentials never reach the browser.
- Confirmation the JWT validation path is identical across all three `DB_MODE` values (the cross-mode JWT check is deepened in 0.21).

Exit:
- The control-plane authorization boundary is settled and vendor-neutral.

### 0.4 ClickHouse Schema and Query Spike

Goal:
- Validate the physical layout for trace and replay query projections on **OSS ClickHouse** (the required, non-pluggable analytics store).

Deliverables:
- Candidate tables for raw spans, normalized steps, messages, tool calls/results, trace summaries, and branch summaries.
- Load test with representative 10k-span trace fixtures, run against a single-node OSS ClickHouse container (the compose-bundled default) to establish the floor a self-hoster sees.
- Query benchmarks for trace open, DAG/timeline load, message/tool search, and original-vs-branch compare.
- Retention/TTL sketch.

Exit:
- The OSS ClickHouse layout can support the V1 UX and latency targets with known tradeoffs, on commodity self-host hardware.

### 0.5 Promptfoo Export Spike

Goal:
- Confirm the first bundled non-generic trace-to-test mapping.

Deliverables:
- One converted trace/branch exported into Promptfoo-compatible JSON or JSONL.
- Provenance preserved.
- Unsupported ForkReplay assertions produce warnings rather than silent loss.

Exit:
- Promptfoo remains the first non-generic mapping target.

### 0.6 Branch Streaming Spike (Redis-backed)

Goal:
- Validate internal branch-event streaming via **FastAPI SSE + Redis pub/sub** (replaces the CF Workers SSE relay + Durable Object).

Deliverables:
- Minimal branch event model.
- FastAPI SSE endpoint that fans out branch events published to a Redis channel, with `Last-Event-ID` resume backed by the Postgres `branch_event` log.
- Browser demo with reconnect/resume behavior across a worker restart.
- Decision on event retention and client catch-up behavior.

Exit:
- UI can show replay progress via FastAPI + Redis without needing Durable Objects, AG-UI, or WebSockets in V1.

### 0.7 Graph Renderer Spike

Goal:
- Validate React Flow + ELK as the default trace DAG / branch-tree renderer.

Deliverables:
- Representative rendering for 100, 500, 1k, 2k, 5k nodes (re-scoped per A10 to the ≤2k step-DAG node target) with collapse/expand, selection, and inspector linking, including progressive-disclosure behavior at the upper end.
- Performance notes and fallback recommendation if React Flow + ELK is not acceptable.

Exit:
- UI graph choice is confirmed or revised before the trace detail implementation deepens.

### 0.8 End-to-End Fork-Start Latency Spike (Temporal)

Goal:
- Validate that the fork-start p95 < 3s launch goal is reachable with **Temporal-orchestrates-every-step** (B4 carried forward onto Temporal) plus a pre-warmed-worker pattern. This replaces the CF Workflows fork-start gate.

Deliverables:
- Throwaway stub on the actual OSS stack (Next.js container + FastAPI services + **Temporal** + OSS ClickHouse + MinIO/S3) covering UI click → API → Temporal workflow start → first model-provider call → first SSE event.
- Variants V0 (cold every time) through V3 (warm Temporal worker pool + object-store prefetch to Redis cache + warm replay-worker replicas).
- p50/p90/p95/p99 measurements; `WorkflowClient.start()`→first activity body, click → provider first byte, S3/MinIO GET TTFB from a co-located worker.

Exit:
- V3 hits p95 < 3s e2e, OR p95 lands at ~4s and we accept the slip, OR p95 > 5s and we escalate before Phase 3.
- Cold-path numbers captured separately to know the degradation floor. Note: with self-hosted Temporal the worker pool is long-lived, so the cold floor reflects worker-restart and task-queue dispatch, not a serverless cold start (see the dedicated Temporal bootstrap timing in 0.14').

Effort: 3 engineer-days.

### 0.9 Object-Store Read Latency Spike (MinIO/S3)

Goal:
- Characterize cold + warm read latency through the **`ObjectStore` S3-compatible abstraction** for frames of 100 KB, 1 MB, 5 MB, across MinIO (compose) and AWS S3 (cloud). Replaces the R2-from-Railway measurement.

Deliverables:
- p50/p95/p99 read times for cold and warm paths against MinIO (single-host) and S3 (cloud), so both the dev floor and the cloud profile are known.
- Validation of B8/B9 storage layout assumptions through the abstraction; redis-cache-hit-rate target with 1 GB per replay-worker replica, LRU.
- Confirmation the abstraction adds no material overhead vs. a direct SDK call (conformance/perf is broadened across MinIO/S3/Azure Blob in 0.22).

Exit:
- Frame read path is viable for the 3s fork-start budget with the planned Redis cache, on both MinIO and S3.

Effort: 2 engineer-days.

### 0.10 OTLP Receiver + NATS/Redis Throughput Spike

Goal:
- Confirm the queue-buffered Phase-1 ingest path can hit the 10k spans/sec/node launch goal on the OSS queue. Replaces the CF Queues throughput gate.

Deliverables:
- Synthetic load through the FastAPI OTLP receiver → **NATS** → stitch/redact/write consumers, behind the `QueueConsumer` interface.
- The same load run against the **Redis Streams** alternative through the identical interface, to confirm the documented alternative also clears the bar.
- Throughput, latency, queue-depth (and consumer-lag) measurements for both backends.

Exit:
- Goal validated on NATS (and on the Redis Streams alternative), or we raise the alarm before Phase 1 implementation locks in.

Effort: 3 engineer-days.

### 0.11 LiteLLM vs Rolled-Translator Spike (E6)

Goal:
- Decide between LiteLLM and a thin in-house translator for cross-provider tool-use / `reasoning_details` round-trips, across the **pluggable** provider set (OpenRouter, direct OpenAI/Anthropic, Ollama). Self-host removes the Vercel AI Gateway option.

Deliverables:
- Comparison run: handling of OpenAI / Anthropic / Gemini `tool_use` and `reasoning_details` round-trips, exercised through the pluggable provider interface (at minimum direct-provider and OpenRouter adapters; Ollama for the local-inference path).
- One-page recommendation memo + maintenance estimate per path (no per-call billing dimension now that billing is removed).

Exit:
- Translator choice locked before Phase 3, and confirmed to sit cleanly behind the pluggable provider interface.

Effort: 1 engineer-week.

### 0.12 Real-World DAG-Size Measurement Spike

Goal:
- Validate the A10 "≤2k interactive" DAG renderer target covers the realistic distribution.

Deliverables:
- Capture 20–30 real production traces from candidate design partners (LangGraph + OpenAI Agents SDK + Claude SDK fixtures).
- Measure step-DAG node counts.

Exit:
- A10 target confirmed, or we revise the renderer's progressive-disclosure thresholds.

Effort: 3 engineer-days.

### 0.13 GoTrue Against Custom Postgres Integration Spike

> **Replaces** the dropped "Supabase Vault Free-Tier Availability" spike. Supabase Vault is gone under the OSS pivot — BYOK secrets are env/secret-supplied with an optional operator-managed KEK (see 0.20), so there is no Vault availability to verify. The new risk is that GoTrue must run cleanly against an operator-supplied Postgres, not only a Supabase-provisioned one.

Goal:
- Verify bundled **GoTrue** runs and migrates cleanly against a plain operator-supplied Postgres (the `custom` `DB_MODE`), and that the app's JWT validation accepts GoTrue-issued tokens from that deployment.

Deliverables:
- GoTrue boots, runs its schema migrations, and issues working JWTs against a vanilla Postgres container (no Supabase extensions assumed beyond the documented floor).
- Signup → confirmation-email → login → refresh round-trip works end to end (email via the console/SMTP sink).
- Documented list of any Postgres roles/extensions/grants GoTrue requires, so the `custom`-mode prerequisites are explicit.

Exit:
- GoTrue is confirmed portable across `supabase` and `custom` Postgres; the auth path is not coupled to managed Supabase. (Full 3-mode matrix is exercised in 0.21.)

Effort: 1 engineer-day.

### 0.14 Temporal Workflow Bootstrap Timing

> **Replaces** the dropped "CF Workflows Cold-Start Measurement." Cloudflare Workflows is gone; the equivalent input to the 0.8 fork-start budget is now Temporal's bootstrap/dispatch timing on a self-hosted cluster.

Goal:
- Measure `WorkflowClient.start()` → first activity body executing on a self-hosted **Temporal** cluster, in isolation from the rest of the stack.

Deliverables:
- p50/p90/p95/p99 start-to-first-activity times against (a) a warm long-lived worker pool and (b) a worker pool just after restart (the worst realistic self-host case).
- Comparison with a speculative-start pattern (workflow started on fork-editor open, gated on a signal for "user-confirmed-run") as the Temporal analogue of the prior pre-warm + wait-for-event approach.

Exit:
- Inform the Phase 0.8 fork-start budget; document the Temporal bootstrap floor and the worker-restart degradation case.

Effort: 2 engineer-days.

### 0.15 redacted_thinking Passthrough Spike

Goal:
- Confirm `redacted_thinking` blocks survive a replay round-trip with the `data` field intact, on both the **direct Anthropic** adapter and the **OpenRouter** adapter (the pluggable routing layer must not strip it on either path).

Deliverables:
- Recorded round-trip with a `redacted_thinking` block via direct Anthropic and via OpenRouter; confirm Anthropic accepts the response and the tool-use loop continues in both.

Exit:
- Same-provider replay of safety-redacted reasoning works through the pluggable provider interface, or we identify the per-adapter workaround.

Effort: 2 engineer-days.

### 0.16 Interleaved-Thinking Beta Header Propagation Spike

Goal:
- Verify `anthropic-beta: interleaved-thinking-2025-05-14` propagates correctly on both the direct-Anthropic adapter and the OpenRouter adapter (header vs `extra_body` mechanism differs by path).

Deliverables:
- Confirmed propagation mechanism per adapter; replay-worker implementation note.

Exit:
- Interleaved-thinking traces can be faithfully replayed through the pluggable provider interface.

Effort: 1 engineer-day.

### 0.17 Claude Agent SDK Fork-Grade Fixture Spike (A3)

Goal:
- Validate Claude Agent SDK as fork-grade through the community OpenInference / OpenTelemetry instrumentor path.

Deliverables:
- 2-tool Claude Agent SDK script with the OpenInference Claude SDK instrumentor.
- Verify spans, hook capture, session_id, and file-checkpointing UUID flow cleanly through OTLP into our normalized schema.

Exit:
- Claude SDK confirmed fork-grade through the instrumentor-only path, OR gaps identified that need explicit ForkReplay capture wrappers.

Effort: 3 engineer-days.

### 0.18 Stripe Credit Grants + Meter Events v2 Dry Run — DROPPED

> **Dropped under the OSS pivot.** Billing is removed from the self-host product — no Stripe, no credit/meter system of record. There is no billing data model to verify, so this spike and its Phase 1 schema-lock dependency no longer exist. The corresponding readiness gate is voided in `READINESS-GATE-REPORT.md`.

### 0.19 Supabase Pro Auto-Upgrade Automation — DROPPED

> **Dropped under the OSS pivot.** There is no managed Supabase project to auto-upgrade and no Stripe MRR to trigger on. Self-hosters provision and scale their own Postgres (the `custom`/`compose` modes) or operate Supabase themselves (the `supabase` mode). The corresponding readiness gate is voided.

### 0.20 Operator-Managed KEK Spike (simplified from age multi-recipient custody)

> **Simplified** from the prior "age multi-recipient key custody ceremony." Self-hosters own their own backup and key custody; ForkReplay no longer runs a managed-data backup with a trusted-advisor recovery ceremony. The retained scope is a clean, optional, operator-managed KEK for envelope-encrypting workspace BYOK secrets at rest.

Goal:
- Stand up the **optional operator-managed KEK** (age/libsodium) used to envelope-encrypt workspace BYOK provider keys at rest, and confirm the app runs with the KEK both enabled and disabled.

Deliverables:
- Operator generates a KEK (single recipient by default; multi-recipient is the operator's choice, not a ForkReplay-run ceremony) and supplies it via env/mounted secret.
- Envelope-encrypt + decrypt of a BYOK secret using the KEK; round-trip verified through the app's secret accessor (no Vault, no `SECURITY DEFINER` accessor).
- Confirmation that `KEK` unset is a supported mode (BYOK secrets stored per the operator's own DB encryption posture), with the security tradeoff documented.
- Rotation procedure documented as operator guidance (not an annual ForkReplay-operated ceremony).

Exit:
- The optional KEK path works and is documented for self-host operators; the app degrades cleanly when no KEK is configured.

Effort: 1 engineer-day.

### 0.21 Pluggable-DB Matrix Bring-Up Spike (NEW)

Goal:
- Bring the control plane up under all three `DB_MODE` values — `supabase`, `custom`, `compose` — and confirm GoTrue, RLS, migrations, and JWT validation behave identically.

Deliverables:
- App + GoTrue boot and migrate green in each mode.
- The same RLS tenant-isolation conformance test (Phase 1 exit gate, see §4.2) passes in all three modes.
- Cross-mode GoTrue JWT validation: a token issued in one mode's auth setup validates through the shared validation path; mode-specific config differences are documented.
- A short matrix table of any per-mode prerequisites (extensions, roles, connection-string shape).

Exit:
- The 3-mode DB matrix is green; "pluggable Postgres" is proven for the control plane (ClickHouse remains separate and required).

Effort: 3 engineer-days.

### 0.22 S3 Storage-Abstraction Conformance Spike (NEW)

Goal:
- Prove the `ObjectStore` S3-compatible abstraction is conformant across **MinIO, AWS S3, and Azure Blob**.

Deliverables:
- A conformance suite (put/get/head/list/delete, multipart for large frames, presign if used, content-hash round-trip) run against MinIO, S3, and Azure Blob.
- Documented behavioral differences (e.g., consistency, error mapping, Azure container vs. S3 bucket semantics) and how the abstraction normalizes them.
- Perf sanity check tying back to 0.9 read-latency numbers.

Exit:
- One storage interface works unmodified across all three backends; per-backend quirks are documented, not load-bearing in app code.

Effort: 2 engineer-days.

### 0.23 docker-compose End-to-End Smoke Spike (NEW)

Goal:
- Stand up the full stack via a candidate `deploy/docker-compose` (web + FastAPI services + Temporal + NATS + Redis + OSS ClickHouse + MinIO + GoTrue + Postgres) and run a minimal product round-trip.

Deliverables:
- `docker compose up` brings the stack to healthy.
- Smoke path: signup → ingest a fixture trace → open it → fork → run branch → compare, all on the single-host stack.
- Documented resource footprint (CPU/RAM/disk) for the single-host quickstart.

Exit:
- The compose quickstart is viable as the default "try it locally" path. (Note: the authored compose artifact itself is Phase 6 — this spike validates feasibility with a throwaway compose file.)

Effort: 3 engineer-days.

### 0.24 Helm Chart Lint/Template Spike (NEW)

Goal:
- Validate a candidate Helm chart skeleton (`helm lint` + `helm template`) for the Kubernetes deployment, with ClickHouse and Temporal as required dependencies.

Deliverables:
- `helm lint` clean and `helm template` renders valid manifests for the full service set, including the required ClickHouse and Temporal components and the `DB_MODE` toggle.
- Confirmation there is no "disable ClickHouse" value (the required-dependency constraint is encoded in the chart surface).

Exit:
- The chart skeleton lints and templates; a full cluster apply is deferred to Phase 6. (Template-only; no live cluster bring-up here.)

Effort: 2 engineer-days.

### 0.25 Terraform validate/plan Spike — AWS + Azure (NEW)

Goal:
- Validate Terraform skeletons for AWS and Azure with `terraform validate` and `terraform plan` (no apply).

Deliverables:
- `terraform validate` clean for `deploy/terraform/aws` and `deploy/terraform/azure` skeletons.
- `terraform plan` produces a coherent plan against each provider (S3/MinIO-or-S3 + managed-or-self ClickHouse + Temporal + the container services), with the required-ClickHouse constraint represented.
- Documented gaps between the two providers' skeletons.

Exit:
- Both skeletons `validate` and `plan` cleanly; `apply`/live verification is explicitly deferred to the Phase 6 IaC authoring work.

Effort: 3 engineer-days.

**Phase 0 timeline:** 3–4 weeks; spikes parallelizable across multiple engineers. Spikes 0.8 / 0.11 / 0.10 are the highest-risk critical-path items. The IaC/packaging spikes (0.23 compose smoke, 0.24 Helm lint/template, 0.25 Terraform validate/plan) are feasibility checks only — they validate that Phase 6 packaging is achievable; the actual artifacts are authored in Phase 6. The 0.20 KEK spike is operational and does not block engineering.

---

## 4. Phase 1: Foundation, Contracts, and Operability

This phase frontloads the platform spine so later work is measurable and does not accumulate avoidable rework.

### 1.1 Repository and Service Layout

Deliverables:
- Monorepo layout for the OSS, self-hostable product:
  - `apps/web` (Next.js workbench, shipped as a standalone container)
  - `services/api` (FastAPI control plane; container)
  - `services/ingest` (FastAPI OTLP endpoint + NATS/Redis queue consumer; container)
  - `services/replay-worker` (container; also runs the Temporal worker pool)
  - `services/mock-gen-worker` (container)
  - `services/export-worker` (container)
  - `services/scheduler` (optional slim scheduler for partition/retention cron — replaces the cron co-tenancy that previously lived in `billing-batch-worker`; runs only low-frequency platform crons such as audit-partition creation and retention sweeps)
  - `sdk/python` (`forkreplay-sdk` + `forkreplay-sdk[auto]` + per-framework extras)
  - `packages/contracts` or equivalent shared schema surface
  - **Deprecated / slated-for-removal (documented, not deleted this pass):**
    - `workers/otlp-gateway` (Cloudflare Workers OTLP gateway — superseded by the FastAPI OTLP endpoint in `services/ingest`)
    - `workers/sse-relay` (Cloudflare Workers SSE relay + Durable Object — superseded by FastAPI SSE + Redis pub/sub)
    - `workflows/cloudflare` (Cloudflare Workflows — superseded by Temporal)
  - **Removed:** `services/billing-batch-worker` (billing removed entirely).
- **Infra components** the stack depends on (bundled in compose; provisioned in Helm/Terraform):
  - **GoTrue** (auth, all DB modes)
  - **Temporal** (durable orchestration; server + worker pool)
  - **NATS** (ingest queue; Redis Streams as the documented alternative)
  - **Redis** (SSE pub/sub + frame cache)
  - **MinIO** (S3-compatible object store in compose; AWS S3 / Azure Blob in cloud)
  - **OSS ClickHouse** (required analytics store — bundled in compose, required dependency in Helm/Terraform; no disable option)
  - **Postgres** (control-plane DB in `compose` mode; external in `custom`/`supabase` modes)
- **`deploy/` path tree (FUTURE — authored in Phase 6, not now):**
  - `deploy/docker-compose/` — single-host / dev stack (bundles all infra components, including OSS ClickHouse and MinIO)
  - `deploy/helm/` — Kubernetes chart (ClickHouse + Temporal required dependencies; `DB_MODE` toggle)
  - `deploy/terraform/aws/` — AWS skeleton
  - `deploy/terraform/azure/` — Azure skeleton
- Environment strategy for local, dev, and production self-host deployments via the `deploy/` artifacts; no per-PR preview-deploy dependency on a managed frontend host.
- Container build + image-publish definitions per service (replaces Vercel/Railway/Cloudflare project definitions).

### 1.2 Control Plane

Deliverables:
- **GoTrue** integration (email/password + federated OAuth/OIDC), bundled in all DB modes; app-wide GoTrue-JWT validation.
- Control-plane Postgres schema (identical across `DB_MODE=supabase|custom|compose`) for:
  - workspaces (with `workspace_limits` row)
  - members/invites
  - API key metadata with verb-on-resource scope taxonomy
  - traces registry
  - sessions (per C8 — `gen_ai.conversation.id` grouping)
  - step_buildability (per data-plane round-2 state machine)
  - branches (including `failure_attribution`, `model_substitution`, `provider_envelope`, `trial_set_id`, `retry_count_override`) — **drop `rate_card_version`** (no billing rate cards)
  - intervention manifests
  - mock definitions
  - tool definitions
  - capability contracts
  - frames (pointer rows with `content_hash`, `object_key`, `fidelity_badge`, `rebuild_count`, `last_rebuilt_at`) — `object_key` is the `ObjectStore` key (was `r2_key`)
  - frame_references (reference-counted GC table)
  - branch_event (partitioned by hash of branch_id)
  - trial sets
  - export snapshots
  - test cases
  - workspace_limits (operational limits only)
  - admin_review_item (auth-policy domain mismatches)
  - audit events (monthly partitions, write-once GRANTs)
  - `system_banners` (status-page replacement — fields: `banner_id`, `severity`, `title`, `body_md`, `active_from`, `active_until`, `audience` (`all`/`workspace_id`), `created_by`, `created_at`) — now Postgres-backed and surfaced over the FastAPI/Redis SSE channel
  - **Removed (billing): `rate_cards`, `model_rates`, `usage_event`, `byok_usage_event`, `credit_pack_grants`, `stripe_webhooks_processed`.**
- Postgres RLS policies on every tenant-scoped table.
- ClickHouse row policies on the `workspace_id` column for every queryable table.
- Tenant-isolation conformance test in CI (Phase 1 exit gate per A8) — must pass identically in all three DB modes (see Phase 0.21).
- Audit-table monthly partition automation via pg_cron-style job, run by the optional `services/scheduler` (creates partitions 1 month ahead; per D-S8).
- **Optional KEK-based BYOK envelope encryption** (operator-managed age/libsodium key via env/secret) for workspace provider keys at rest — **no Supabase Vault, no `replay_worker_byok` role, no `SECURITY DEFINER` accessor.** The app degrades cleanly when no KEK is configured (see Phase 0.20).
- Logged-secret canary CI test (BYOK plaintext + GoTrue service/admin JWT + provider API keys for OpenRouter/OpenAI/Anthropic).
- `system_banners` table + `/v1/internal/banners` admin endpoint + **FastAPI SSE + Redis** push of banner rows to active workbench sessions (status-page replacement; the prior Postgres LISTEN/NOTIFY → Workers SSE wiring is replaced by Redis pub/sub fan-out).
- **Removed (billing): Stripe webhook receiver, the sub-24h refund batch, Stripe Meter Event Adjustments, reconciliation mismatch alarms.** None of these exist in the self-host product.
- **No managed sub-processor list.** Self-host has no ForkReplay-operated data processors; the operator's own infra choices are theirs. Pluggable external dependencies the operator may opt into (OpenRouter / OpenAI / Anthropic for execution + AI-mock; an SMTP provider such as Resend for GoTrue email) are documented as *optional, operator-configured* integrations in the deploy docs, not as ForkReplay sub-processors.

### 1.3 API and Contract Baseline

Deliverables:
- REST/OpenAPI skeleton.
- Canonical ID/versioning rules.
- Problem-details error format.
- Pagination/filter conventions.
- Idempotency rules for mutating endpoints.
- Initial contract tests.

### 1.4 Observability and Operations Baseline

Deliverables:
- **Optional self-hosted OTel collector + Grafana/Prometheus** as the sink. Every service emits OTLP/HTTP-protobuf with gzip; the stack runs with **no external sink configured** (observability is opt-in for self-hosters). A reference Grafana/Prometheus deployment is documented (and bundled as an optional profile in the Phase 6 compose artifact).
- Structured application logs.
- Metrics for:
  - auth failures
  - ingest acceptance/rejection
  - trace normalization failures
  - Temporal workflow starts/pauses/resumes/failures (was CF Workflows)
  - workflow dead-letter / non-retryable failures
  - replay model-call attempts
  - branch completion/failure
  - mock.matched (counter, **not** an audit row — per F-S5)
  - export success/failure
  - queue depth / consumer lag (NATS or Redis Streams)
  - SSE connected-client gauge and reconnect rate (FastAPI/Redis)
  - **Removed (billing): all `billing.*` metrics and `cost_estimate.actual_vs_estimate_ratio`.**
- Distributed tracing across API, ingest, replay worker, and Temporal-activity execution paths.
- Dashboards and first-pass alerts (shipped as optional reference dashboards, not a managed service).
- Operational runbook skeleton.
- **No public status page in V1**; internal SLO dashboard with a 99.0% target for any reference deployment (self-hosters own their own availability).

### 1.5 Test Foundation

Deliverables:
- Unit test harnesses per service.
- Integration test harness against the bundled-compose stack: Postgres + GoTrue, OSS ClickHouse, MinIO (S3-compatible) via the `ObjectStore` abstraction, NATS/Redis via the `QueueConsumer` abstraction, and Temporal (test server) where possible.
- Tenant-isolation test matrix (Postgres RLS conformance + ClickHouse row-policy conformance).
- Seed fixtures for:
  - small trace
  - 5-step trace with two tools
  - multi-step replay fixture
  - restricted-trace scenario

### 1.6 Agent-Instruction Scaffolding & Docs Harness

Even though the dedicated docs *content* owner starts in Phase 2 (per A11), the agent-instruction scaffolding lands in Phase 1 so doc drift is structurally hard from the start.

Deliverables:
- `AGENTS.md` (root + per-service) — open standard, tool-agnostic; canonical project instructions.
- `CLAUDE.md` (root + per-service) — imports `AGENTS.md` via `@./AGENTS.md`; Claude-specific operational notes.
- Both files include the "V1 deliberately-constrained scope" section (no SLA, no public status page, no pen-test, operator-owned infra + backups/RPO, self-host privacy defaults, Python-only SDK, 5-item admin panel, **billing removed**, Apache-2.0). The pre-pivot SaaS framings (free-tier infra, ~24h managed RPO, paid-tier-only privacy) are replaced by their self-host equivalents.
- `docs-update` agent skill at `.claude/skills/docs-update.md` (and a near-equivalent at `.codex/skills/docs-update.md`).
- `docs-drift-check` GitHub Actions check that fails any PR touching specified path-globs (`services/api/openapi/**`, `packages/contracts/**`, `sdk/python/**`, etc.) without a matching `docs/**` edit.
- Scope-creep guard in the `docs-update` skill: if a PR adds "SLA", "status page", "pen test", or "TypeScript SDK" in a customer-facing doc context, the skill prompts against the V1 scope constraints.

Exit for Phase 1:
- A deployable, observable skeleton exists with GoTrue auth, control-plane persistence (RLS + ClickHouse row-policy conformance test green, identically across all three DB modes), contracts, optional KEK-based BYOK envelope encryption landed, audit-partition automation in the slim scheduler, system_banners over FastAPI/Redis SSE, agent-instruction scaffolding live, and CI confidence before the product loop expands. No Stripe/refund-batch/Vault deliverables — billing is removed.

---

## 5. Phase 2: Capture and Inspect Vertical Slice

This phase proves that a developer can produce a useful ForkReplay trace and inspect it in the product.

### 2.1 Python SDK Core

Deliverables:
- **Explicit-capture core API** landed first: `checkpoint()`, `start_conversation()`, `register_tool()`, `capture_tool_call()`, `capture_stream()`, `mark_step_complete()`, redaction-hints API.
- Decorator layer (`@capture`, `@step`, `@tool`, `@model_call`) — sugar over the core.
- Framework-neutral adapter as the reference fork-grade fixture.
- **LangGraph adapter** (default mode: explicit `checkpoint()` after each node; opt-in mode: consume LangGraph's checkpointer directly).
- **OpenAI Agents SDK adapter** over the official `opentelemetry-instrumentation-openai-agents-v2` contrib package.
- **Claude Agent SDK adapter** (A3; ~2 engineer-weeks): thin wrapper module that calls the OpenInference Claude SDK instrumentor + our own PreToolUse / PostToolUse hooks for fork-grade additions. Mid-session fork semantics documented (replay via `get_session_messages()` + edited prompt sequence; not Anthropic's native `fork_session` for mid-session). `pip install forkreplay-sdk[claude]` pulls in `claude-agent-sdk` and the OpenInference instrumentor as transitive deps.
- **`forkreplay-auto`** (G-R2.5 override, V1 not V1.1; ~1 engineer-week core + 12 engineer-days for 6 inspect-only integration tests, parallelizable): one-line `import forkreplay.auto` walks `sys.modules` + `importlib.metadata.distributions()`, dispatches to OpenInference / community OTel instrumentors for detected frameworks. Idempotent. Quietable. Skip silently if `OTEL_SDK_DISABLED=true`. **`[auto]` extra is detection logic only (round-3 §0.1 override)** — pulls in `forkreplay-auto` core + the `importlib.metadata` walker, NOT the per-framework instrumentor packages. Users install per-framework extras (`[langgraph]`, `[openai-agents]`, `[claude]`) explicitly for each framework they want auto-instrumented; `[all]` extra remains as a convenience meta-package with compatibility-range pins (`~=` or `>=X.Y,<X.(Y+1)` per G-R3.4) but ships with a production warning. Detection budget: 50ms total / 5ms per-adapter (per C-R3.2). Explicit `forkreplay.init(...)` wins over auto-attach (per C-R3.8).
- **`.pth` env-var bootstrap** (round-3 G-R3.1): a `forkreplay_auto.pth` file ships in the `[auto]` extra and is a no-op unless `FORKREPLAY_AUTO_INSTRUMENT=1` is set. When set, the `.pth` file imports `forkreplay.auto` at Python startup before user code runs — no application-code edit required. Companion env vars wired in this phase: `FORKREPLAY_AUTO_SAMPLE=0.1` (probabilistic drop at SDK), `FORKREPLAY_AUTO_DISABLE=1` (hard kill-switch per D-R3.Q7), `FORKREPLAY_VERBOSE=1` (INFO-level logs from auto-instrument; silent default per G-R3.7).
- `atexit` flush hook in `forkreplay-auto` with opt-out kwarg (per G-R3.3).
- OTel `TracerProvider` interaction: attach as `SpanProcessor` (last-wins safe), don't replace the user's provider (per G-R3.6).
- **Claude SDK passive opt-out helper** `disable_implicit_markers()` (per G-R3.2): kills the trust-span-close behavior for customers who want strict explicit marking.
- **`jsonschema-rs` strict-validation wrapper** (round-3 F-R3.6): thin Python wrapper around the Rust `jsonschema-rs` crate plus OpenAI strict-subset additional checks layered on top. Used by mock-gen schema enforcement.
- **Nightly OpenRouter ZDR conformance probe** (round-3 F-R3.1; now optional + relocated): when an operator configures OpenRouter as the provider and opts into strict-ZDR routing, a cron in the optional `services/scheduler` calls each strict-ZDR model with a known ZDR-required header and validates the routing honors it. On failure, the model is auto-narrowed out of the strict dropdown; alert on-call if >1 simultaneous failure. Skipped entirely when OpenRouter is not the configured provider (e.g., direct-provider or Ollama deployments).
- Six inspect-only adapters (OpenInference deps): LlamaIndex, Pydantic AI, smolagents, Strands Agents, AutoGen, CrewAI.
- OTLP-compatible export (HTTP-protobuf with gzip) to the ForkReplay ingest endpoint; no managed-sink preference (the SDK targets whatever OTLP endpoint the operator points it at).
- Production redaction-before-egress.
- Fork-readiness classification inputs.
- CI-safe sample agent using fake model/tool behavior.
- SDK version starts at **0.1.0** (per G-R2.4 override, leaves room for breaking changes during V1.1/V1.2).
- 30-min first-fork-grade-trace acceptance test wired into CI (Phase-2 exit gate per A11).
- Tiered mock scratchpad (256 KB default, up to 1 MB on paid tiers, per F-R2.4).
- Postgres trigger to enforce `mock_version` bump on every mock content change (per C-R2.5).

### 2.2 Ingest and Projection

Deliverables:
- FastAPI OTLP receiver integrated with the ingest pipeline via NATS/Redis.
- Canonical normalization into ForkReplay trace objects.
- ClickHouse projection writes for span/step/message/tool views.
- `ObjectStore` (S3/MinIO) storage for frame/checkpoint payloads.
- Postgres trace registry and readiness summary.

### 2.3 Trace Detail UI

Deliverables:
- Trace list.
- Trace detail summary.
- Step timeline.
- Raw span fallback.
- Fork-readiness panel.
- Per-step fidelity badging (`exact` / `schema_equivalent` / `approximate`).
- Sessions view (chronological list of traces sharing `gen_ai.conversation.id`).
- Initial DAG/tree view if graph spike validates the approach (≤2k step-DAG nodes interactive per A10; progressive disclosure above).

### 2.4 Docs Workstream

Deliverables (dedicated docs owner starts in Phase 2):
- `docs/quickstart/python.md` — 30-minute first-fork-grade-trace path (Phase-2 exit gate per A11, validated weekly by a non-engineer or designated tester).
- `docs/sdk/python/`, `docs/integrations/langgraph`, `docs/integrations/openai-agents-sdk`, `docs/integrations/claude-agent-sdk`, `docs/integrations/auto`.
- `docs/integrations/claude-agent-sdk/migration.md` — proactive migration path for when Anthropic ships native OTel.
- Enforce the `CLAUDE.md` / `AGENTS.md` discipline alongside engineering PRs.

Acceptance:
- A user can instrument the sample agent, ingest a fork-grade trace, open it, inspect its steps, and understand why it is or is not forkable.
- **Phase-2 exit gate (A11):** a clean signup → fork-grade trace in ≤30 minutes following only public docs.

---

## 6. Phase 3: Fork MVP and Generic Regression Output

This phase proves the central value loop.

### 3.1 Branch Domain

Deliverables:
- Branch records and intervention manifest persistence.
- Initial fork-point validation.
- One or two intervention types implemented first:
  - system/message edit
  - forced tool result
- Preflight for missing mocks and blocked execution.

### 3.2 Durable Replay Execution

Deliverables:
- **Temporal workflow** for branch lifecycle. **Workflow orchestrates every step including the first** (B4 carried forward). Phase 0.8 spike validates the fork-start budget; if Temporal bootstrap/dispatch (Phase 0.14) violates the budget, escalate before locking the wiring.
- Speculative-start pattern: the Temporal workflow is started on fork-editor open and gated on a `user-confirmed-run` signal (the Temporal analogue of the prior pre-warmed wait-for-event pattern).
- Replay-worker activities invoked from Temporal workflow steps (worker pool co-located with `services/replay-worker`).
- **Pluggable** execution path with the default provider envelope where the provider supports it (`allow_fallbacks: false`, `order: [<captured>]`, `require_parameters: true` for OpenRouter; equivalent pinning for direct-provider; deterministic local model for Ollama).
- Provider-pinning envelope implementation with `validateModelSwap` API and substitution-dialog support, across the pluggable provider set.
- Deterministic state transitions:
  - `draft`
  - `estimating`
  - `blocked`
  - `queued`
  - `running`
  - `paused`
  - terminal states
- Idempotency ledger for model/tool attempts.
- Cancellation cascade: `branch.cancel_requested_at` polling at 1s; AbortSignal propagation; 3s p95 cancel-to-abort budget.
- Temporal activity retry policy: a `workflow_step_retries` operational limit on `WorkspaceLimits` (default 5; initial delay 5s, exponential backoff via the Temporal `RetryPolicy`). User-configurable override in the fork editor (per B-R2.8), bounded by the workspace limit. CHECK constraint at the `WorkspaceLimits` level enforces the max. (The prior Free/Pro/Enterprise tier ladder is removed with billing — this is now a flat operational limit the operator can set per workspace via the admin panel.)

### 3.3 Tool Resolution

Deliverables:
- `mock`, `ai_mock` draft placeholder behavior, and `block` states wired into the execution engine.
- Matcher engine integration (`jsonata-python` + conformance suite, pinned version per F-R2.3).
- Output-template renderer (JSON interpolation + tiny expression sublanguage).
- Scratchpad lifecycle implementation (per-branch, seeded from observed values).
- Static mocks treated as a specialization of `input_matcher` kind with a single `true` rule.
- Runtime enforcement that live tools are never executed in V1.

### 3.4 Branch Progress and Compare

Deliverables:
- **FastAPI SSE endpoint backed by Redis pub/sub**, reads from the Postgres `branch_event` log with `Last-Event-ID` resume (replaces the CF Workers SSE relay + per-branch Durable Object).
- Branch run UI with pause/failure/completion state.
- Original-vs-branch step comparison.
- First-divergence display.

### 3.5 Generic Test Conversion

Deliverables:
- Convert a successful branch into generic JSON test output.
- Basic assertion proposal/review.
- Test-case persistence.

Acceptance:
- A user can fork a real captured trace, run the branch through durable orchestration, compare the result, and save it as a generic regression test.

---

## 7. Phase 4: Beta-Complete Product Loop

This phase adds the V1 breadth needed for a serious beta. **Schema configuration engine is V1.1, out of Phase 4.** **V1.1 exporter preview infra is out** (per §0.8 override; the 8 V1.1 exporters do not appear behind a feature-flag preview surface).

Deliverables:
- Full guided intervention surface from the PRD.
- AI-generated mock workflow with review/approve/disable.
- Workspace-admin-configurable default AI-mock model (curated list highlighting cheap-but-good structured-output models; default Gemini 3.x Flash if available, Claude Haiku fallback per F-R2.6).
- Capability contract auto-inference (cache key `(workspace_id, agent_name, tool_catalog_hash, system_prompt_hash)`; shares the AI-mock generation counter per F-R2.1, now an operational metric not a billing meter).
- Repeated trials and trial-set aggregation.
- Branch effect summary.
- **BYOK integration via the pluggable provider interface + optional KEK** (operator-managed age/libsodium key for envelope encryption at rest; no Supabase Vault, no `replay_worker_byok` role).
- Optional **informational** replay estimation as a ±20% range (token/latency, not charge) + operational hard caps from `WorkspaceLimits`. `retry_amplification_factor` initial value 0.20; calibrate against observed Phase-3 dogfood retry rates and dial in by end of Phase 4. (No credit line item, no reasoning-rate charge — billing is removed.)
- **Removed (billing): reconciliation alarms.** There is no charge ledger to reconcile.
- Cross-provider model-swap UX (drop `reasoning_details` with warning), across the pluggable provider set.
- BYOK usage tracking (rolling 30 days) as an **operational** signal with admin-configurable alert and cutoff thresholds against `WorkspaceLimits` (no hard cap by default) — caps spend at the operator's own provider, not a ForkReplay charge.
- Audit coverage for critical actions.
- Retention/deletion mechanics.
- Branch tree navigation and recursive forks.
- Three hard-coded exporters: generic trajectory JSONL, generic JSON test case, Promptfoo (on top of a thin internal mapping interface that V1.1 will replace with the schema configuration engine).
- **V1 admin panel (locked at 5 surfaces per §0.3):** per-workspace limit overrides, auth-policy edits, member management, BYOK/provider config (pluggable provider selection + keys + optional KEK), retention/redaction policy. All operational limits, monthly usage caps, retention windows, and AI-mock caps are admin-editable from this panel without a code deploy. No rate-card or billing surfaces (billing removed). No other admin features in V1 GA — anything else is V1.1+.
- Reasoning-token transparency in the fork editor (informational token counts) + prompt-cache-bust side-by-side comparison.

Acceptance:
- The primary debugging workflow works end to end with realistic failure cases, repeated-trial confidence, approved mocks, operational usage caps, and the three V1 exporters.

---

## 8. Phase 5: V1 Self-Host Bring-Up Hardening

This phase replaces the prior "SaaS launch hardening" with **OSS self-host bring-up hardening**. **Pen-test work removed. Public status page work removed. Billing/refund work removed (billing is gone).** The deployment-packaging artifacts themselves (compose/Helm/Terraform) are authored in Phase 6; this phase hardens the product so that those artifacts have something stable to package, and adds the smoke-level verification gates that do not require the full IaC.

Deliverables:
- Export previews, validation reports, and delivery destinations for the 3 V1 GA exporters.
- Onboarding flow and setup docs. `forkreplay-auto` is the canonical onboarding path in docs/examples; the **single-tenant (default-workspace) quickstart** is the canonical self-host onboarding path.
- Runbooks for ingest, replay, BYOK/provider config, exports, deletion, backup/restore, and KEK rotation operations.
- Load tests (run against the bundled-compose stack to set the self-host floor):
  - ingest throughput (validate the 10k spans/sec/node launch goal per A9, through NATS/Redis)
  - trace-open latency (OSS ClickHouse)
  - branch-start latency (validate fork-start p95 < 3s launch goal on Temporal; accept 4s slip)
  - compare query latency
- Security verification:
  - **Postgres RLS policy tests + ClickHouse row-policy tests + tenant-isolation CI matrix, run in all three DB modes** (A8 enforcement gate; must be green before launch).
  - GoTrue JWT-validation negative tests (expired/forged/cross-mode tokens rejected).
  - authz negative tests
  - API key misuse tests
  - KEK access boundary tests (BYOK secrets unreadable without the KEK; clean degradation when KEK unset)
  - Logged-secret canary regression test
- Self-host bring-up smoke gates (smoke-level; full live verification deferred to Phase 6):
  - **`docker compose up` end-to-end smoke** green (signup → ingest → fork → run → compare on one host).
  - **`helm lint` + `helm template`** clean for the chart skeleton.
  - **`terraform validate` + `terraform plan`** clean for the AWS and Azure skeletons.
- Monitoring refinement and alert thresholds (against the optional self-hosted OTel/Grafana/Prometheus reference).
- **Removed (billing): refund-latency exit gate, billing/replay-credit reconciliation checks.**
- Quarterly **backup/restore drill** for Postgres + OSS ClickHouse + object store — documented as operator guidance (self-hosters own RPO/backup; ForkReplay ships the drill runbook, not a managed backup).
- KEK rotation drill; object-store retrieval drill.
- **Trust-posture page / `TRUST.md`** — launch-blocker. Authored with engineering review. Ships as a doc in the repo (and as a deal-team one-pager for anyone offering hosted ForkReplay). Covers the internal 99.0% SLO for reference deployments, incident communication discipline, the security baseline, **operator-controlled** data handling, honest constraints (no SLA, no public status page, no pen-test, self-host privacy defaults, **billing removed**, Apache-2.0), and the V1.1/V2 upgrade path. (No EU-residency / HIPAA claims to make — self-hosters choose their own region and compliance posture.)
- Documentation drift audit: validate that every V1 GA feature has docs, examples, and a `docs-update`-skill-tested round-trip, including the deploy docs.
- Launch comms boilerplate updated for self-host: data residency, region, and compliance posture (EU residency, HIPAA/BAA, etc.) are the **operator's** choice in a self-hosted deployment; ForkReplay makes no managed-residency claim. Lands in the README/deploy docs and in-product onboarding.

Acceptance:
- V1 scope is feature-complete, observable, test-backed, and operationally supportable.
- A8 enforcement gate green (RLS + row policies + tenant-isolation CI matrix, all three DB modes).
- Trust-posture page / `TRUST.md` live.
- The three self-host smoke gates are green: `docker compose up` end-to-end smoke, `helm lint`/`helm template`, and `terraform validate`/`terraform plan` (AWS + Azure).

---

## 9. Phase 6: Deployment Packaging and Abstraction Layers (FUTURE)

This phase **produces the deployment artifacts and the abstraction layers** that make ForkReplay genuinely self-hostable. It is sequenced as **future work** — this plan authors none of it now; Phase 5 only validated feasibility at smoke level (Phase 0.21–0.25 spikes + the Phase 5 smoke gates). The artifacts here are what a self-hoster actually runs.

### 9.1 Abstraction layers (productionized)

- **`AuthProvider` / GoTrue client** — the shared GoTrue-JWT validation + session client used by web, API, ingest, and workers, hardened across all three `DB_MODE` values.
- **`ObjectStore` (S3 interface)** — production implementation over MinIO / AWS S3 / Azure Blob, passing the 0.22 conformance suite.
- **`QueueConsumer`** — production NATS implementation + the Redis Streams alternative behind one interface.
- **Temporal workers** — the productionized worker pool, retry/timeout policies, and task-queue topology for the branch lifecycle.
- **Redis SSE relay** — the production FastAPI SSE + Redis pub/sub fan-out with `Last-Event-ID` resume and connection lifecycle management.
- **FastAPI OTLP endpoint** — the production OTLP/HTTP-protobuf + gRPC receiver in ingest/api, replacing the deprecated `workers/otlp-gateway`.

### 9.2 docker-compose (single-host / dev)

- `deploy/docker-compose/` bundling web + FastAPI services + the optional scheduler + GoTrue + Temporal + NATS + Redis + **OSS ClickHouse** + MinIO + Postgres, plus an optional observability profile (OTel collector + Grafana + Prometheus).
- `DB_MODE=compose` default; `.env`-driven config; single-tenant default-workspace quickstart.
- End-to-end `docker compose up` smoke must pass (productionizes the 0.23 spike).

### 9.3 Helm (Kubernetes)

- `deploy/helm/` chart for the full service set with **ClickHouse and Temporal as required dependencies** (no disable toggle) and the `DB_MODE` value (`supabase`/`custom`/`compose-in-cluster`).
- `helm lint` + `helm template` clean in CI; a full cluster apply + smoke is the Phase 6 exit (productionizes the 0.24 spike).

### 9.4 Terraform (AWS + Azure)

- `deploy/terraform/aws/` and `deploy/terraform/azure/` skeletons: object store (S3 / MinIO-or-S3 on Azure), managed-or-self ClickHouse, Temporal, the container services, and the `DB_MODE` wiring, with the required-ClickHouse constraint represented.
- `terraform validate` + `terraform plan` clean in CI; a guarded `apply` against a scratch account is the Phase 6 live-verification exit (productionizes the 0.25 spike).

### 9.5 Packaging exit criteria

- A new operator can stand up ForkReplay from a public repo via **any one** of: docker-compose (single host), Helm (Kubernetes), or Terraform (AWS or Azure).
- ClickHouse is present and required in every path; the control plane runs under the operator's chosen `DB_MODE`.
- GoTrue, Temporal, NATS/Redis, Redis-SSE, and the S3 object store are all driven by the productionized abstraction layers.
- The deprecated `workers/otlp-gateway`, `workers/sse-relay`, and `workflows/cloudflare` projects are removed once their FastAPI/Temporal replacements are proven in this phase.

---

## 10. Cross-Cutting Quality Bar

These are not cleanup tasks. They ship continuously with the work.

### Testing

- Unit tests for domain logic and serialization.
- Integration tests for storage boundaries and orchestration handoffs.
- Contract tests for REST/OpenAPI and workflow inputs.
- SDK unit tests (≥90% line / ≥85% branch on `forkreplay/_core/`).
- SDK integration tests (LangGraph default + checkpointer-consume, OpenAI Agents SDK, Claude SDK, six inspect-only smoke tests, `forkreplay-auto` import-order tests).
- Contract tests against ingest with golden OTLP fixtures.
- End-to-end tests for:
  - signup to first trace
  - trace to branch
  - branch to compare
  - branch to generic test export
  - BYOK branch execution across the pluggable provider set (OpenRouter / direct-provider / Ollama)
- Tenant-isolation and authorization negative-path tests.
- 30-minute first-fork-grade-trace acceptance test in CI.
- **Documentation drift CI check** (`docs-drift-check`): blocks merge when public-API-touching, schema-touching, or scope-touching PRs lack matching doc edits. Override via `docs:no-change-needed` label (docs owner only).

### Monitoring and Observability

- Every service emits structured logs with request IDs, workspace IDs where appropriate, object IDs, and error classes.
- Critical cross-service operations carry trace IDs.
- Dashboards track product and system signals, including:
  - trace ingest success rate
  - fork-readiness rate
  - branch completion/failure rate
  - workflow pause/resume reasons
  - cost-cap blocks
  - AI-mock approval funnel
  - export success rate
- Alerts cover auth regressions, ingest error spikes, Temporal workflow backlog/failures, queue depth/consumer lag (NATS/Redis), ClickHouse write/query issues, and object-store (S3/MinIO) access failures.

### Security

- Redaction-before-egress in SDK.
- Server-side redaction validation on ingest.
- No plaintext BYOK provider keys in application tables or logs.
- Optional operator-managed KEK for BYOK envelope encryption at rest; clean degradation when no KEK is configured (no Vault, no `replay_worker_byok` role).
- Explicit workspace scoping at every storage boundary plus Postgres RLS + ClickHouse row policies.
- GoTrue-JWT validation enforced uniformly across web, API, ingest, and workers, in all three DB modes.
- Logged-secret canary CI test on every PR.

### Documentation as a First-Class Workstream

- `AGENTS.md` + `CLAUDE.md` are maintained alongside engineering PRs; both include the "V1 deliberately-constrained scope" section so new contributors don't write code that contradicts settled scope.
- `docs-update` skill is the reproducible workflow for doc updates; the `docs-drift-check` CI job is the deterministic backstop.
- Trust-posture page / `TRUST.md` is the procurement-facing artifact; reviewers auto-CC'd on changes (security + product owners).
- Deploy docs (compose/Helm/Terraform quickstarts, the required-ClickHouse note, and `DB_MODE` guidance) are first-class and drift-checked alongside the code.

---

## 11. Immediate Next Artifact After This Plan

Once this plan is accepted, the next implementation artifact should be a **technical architecture and milestone breakdown** that converts the phases above into:

- service-level responsibilities
- initial database/schema sketches (control plane + ClickHouse) with the `DB_MODE` matrix
- first OpenAPI endpoint inventory (including the FastAPI OTLP endpoint)
- Temporal workflow lifecycle sketches for the branch loop
- SDK package outline
- the `deploy/` artifact outline (compose/Helm/Terraform) and abstraction-layer interfaces (`AuthProvider`, `ObjectStore`, `QueueConsumer`, Temporal workers, Redis SSE relay)
- milestone issue list suitable for execution


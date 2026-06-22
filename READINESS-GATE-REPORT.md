> **OSS PIVOT RE-GATE (2026-06-21):** ForkReplay has pivoted from a managed multi-vendor SaaS to an open-source, self-hostable product (Apache-2.0). A re-gate section — **"OSS Pivot Re-Gate (post-pivot)"** — has been added immediately below this header. It supersedes the managed-SaaS gates wherever the two conflict. The original report body (and the 2026-05-12 post-consolidation update below) is preserved unchanged as a **frozen audit trail** of the pre-pivot readiness review. Current canonical state after the pivot: **PRD v0.9 / Spec v0.5 / Plan v0.4 / competitive_analysis v0.4.**
>
> **POST-CONSOLIDATION UPDATE (2026-05-12):** The "Outstanding Gaps" listed in §4 below have been resolved.
> Current canonical state: **PRD v0.8 / Spec v0.4 / Plan v0.3.** Phase 0 spikes **0.19 (Stripe Sandbox chaos)** and **0.20 (age multi-recipient key custody ceremony)** are now in the Plan. `system_banners` table is in Spec §2. `WorkspaceLimits.workflow_step_retries` (Free=1/Pro=5/Enterprise=10) and `CreditPackGrant` custom-amount flow are in Spec §2.
>
> The report body below is preserved as a frozen audit trail of the readiness review; references to `questions-round-*.md`, `round-1-responses/`, `round-2-responses/`, and `round-3-tactical-decisions.md` point to files removed during the post-consolidation cleanup. Their content is in the canonical docs (PRD §11 risk table, Spec §11 decision audit, Plan v0.3 changelog block).

---

## OSS Pivot Re-Gate (post-pivot)

**Re-gate date:** 2026-06-21
**Trigger:** Pivot from managed multi-vendor SaaS → open-source, self-hostable product (Apache-2.0).
**Canonical versions after pivot:** PRD **v0.9** / implementation-readiness-spec **v0.5** / implementation-plan **v0.4** / competitive_analysis **v0.4**.
**Verdict:** **READY (re-gated).** The product contract (canonical object model, framework adapters, fork execution semantics, defense-in-depth tenant isolation) is unchanged by the pivot and remains settled. The infrastructure substrate is swapped to best-of-breed OSS and billing is removed; the gates below replace the managed-vendor gates accordingly. End-to-end deployment verification (live compose up / helm apply / terraform apply) is **DEFERRED** to the implementation phase that authors the IaC (Plan §9, Phase 6) — see the deferral note at the end of this section.

### Architecture delta this re-gate is grounded on

| Dimension | Pre-pivot (frozen body below) | Post-pivot (this re-gate) |
|---|---|---|
| Control-plane DB | Supabase managed Postgres | Pluggable `DB_MODE=supabase\|custom\|compose` |
| Auth | Supabase Auth (managed) | **GoTrue** bundled in all DB modes; Postgres RLS |
| Analytics store | ClickHouse Cloud | **OSS ClickHouse — REQUIRED in every mode** (bundled in compose; required in Helm/Terraform; not pluggable) |
| Object storage | Cloudflare R2 | S3-compatible `ObjectStore` (MinIO / AWS S3 / Azure Blob) |
| OTLP ingress | CF Workers `otlp-gateway` | FastAPI OTLP endpoint in ingest/api |
| Ingest queue | CF Queues | **NATS** (Redis Streams alternative) |
| Live streaming / SSE | CF Workers SSE relay + Durable Objects | FastAPI SSE + Redis pub/sub |
| Durable orchestration | Cloudflare Workflows | **Temporal** (self-hosted) |
| Secrets / BYOK | Supabase Vault + `replay_worker_byok` role | env/secret + optional operator-managed KEK (age/libsodium); **no Vault** |
| LLM routing | OpenRouter only | Pluggable (OpenRouter / direct OpenAI/Anthropic / Ollama) |
| Email | Resend only | Pluggable SMTP (Resend / SMTP / console) for GoTrue mail |
| Billing | Stripe Credits + Meters (system of record) | **Removed.** Operational `WorkspaceLimits` only |
| Web hosting | Vercel | Next.js standalone container |
| Python services | api, ingest, replay, mock-gen, export, **billing-batch** | same five **minus billing-batch**; + optional slim `scheduler` for partition/retention cron |
| Observability | Grafana Cloud (required) | Optional self-hosted OTel collector + Grafana/Prometheus |
| Tenancy | Multi-tenant SaaS | Multi-tenant core (RLS) + documented single-tenant default-workspace quickstart |

Deprecated/slated-for-removal (documented, not deleted this pass): `workers/otlp-gateway`, `workers/sse-relay`, `workflows/cloudflare`, `services/billing-batch-worker`.

### Prior gates now VOID

These pre-pivot gates no longer have a dependency to verify and are withdrawn:

- **Stripe Credit Grants dry-run (Plan 0.18) and Stripe Sandbox chaos test (0.19-as-chaos / H-R3.6).** Billing is removed; there is no purchase → grant → meter → refund path, no credit/meter system of record, and no refund-batch liability to chaos-test.
- **Supabase Vault free-tier availability spike (Plan 0.13).** No Vault dependency — BYOK secrets are env/secret-supplied with an optional operator-managed KEK.
- **Supabase Pro auto-upgrade automation ($1k MRR trigger; Plan 0.19).** No managed Supabase project to flip and no Stripe MRR to trigger on; self-hosters scale their own Postgres.
- **CF Workflows cold-start gate (Plan 0.14).** Cloudflare Workflows is gone; replaced by the Temporal bootstrap-timing gate below.
- **Billing/refund-cadence gates:** the Phase-5 "sub-24h refund batch ≥7 days clean" launch-blocker, reconciliation-mismatch alarms ($5/$50), the `cost_estimate.actual_vs_estimate_ratio` ±20% SLO, all `billing.*` metrics, and the nightly **ZDR probe as a billing-batch cron** (the ZDR probe survives only as an optional scheduler cron when OpenRouter is the configured provider).
- **age multi-recipient key-custody ceremony (Plan 0.20):** demoted from a ForkReplay-operated, advisor-recipient recovery ceremony to a simplified **optional operator-managed KEK** spike. The bus-factor-of-1 risk is now the operator's to manage, not ForkReplay's.
- **Managed-availability framings:** the ~24h managed RPO, the quarterly managed restore drill, and the "paid-tier-only privacy" posture are withdrawn as ForkReplay obligations — self-hosters own RPO, backups, and privacy defaults (ForkReplay ships the drill runbooks, not a managed backup).

### New gates ADDED

These are the post-pivot readiness gates. Smoke-level validation lands in Phase 0 (spikes) and Phase 5 (smoke gates); full live deployment verification is deferred to Phase 6.

1. **3-mode DB matrix bring-up (Plan 0.21):** control plane + GoTrue boot, migrate, and pass the RLS tenant-isolation conformance test **green in all three `DB_MODE` values** (`supabase` / `custom` / `compose`).
2. **GoTrue cross-mode JWT validation (Plan 0.3 + 0.21):** GoTrue-issued JWTs validate through one shared validation path across web/API/ingest/workers, identically in every DB mode; expired/forged/cross-mode tokens are rejected (Phase-5 negative tests).
3. **GoTrue against custom Postgres (Plan 0.13, replacing the Vault spike):** GoTrue runs and migrates cleanly against a vanilla operator-supplied Postgres; required roles/extensions/grants documented.
4. **Temporal workflow bootstrap timing (Plan 0.14, replacing the CF Workflows cold-start gate):** `WorkflowClient.start()` → first activity measured on a self-hosted cluster (warm pool + worker-restart cases); feeds the 0.8 fork-start p95 < 3s budget.
5. **NATS/Redis ingest throughput (Plan 0.10):** the 10k spans/sec/node goal validated on **NATS** and on the **Redis Streams** alternative behind the `QueueConsumer` interface.
6. **S3-abstraction conformance across MinIO / AWS S3 / Azure Blob (Plan 0.22):** one `ObjectStore` interface passes a put/get/head/list/delete + multipart + content-hash conformance suite on all three backends; behavioral differences documented, not load-bearing in app code.
7. **docker-compose end-to-end smoke (Plan 0.23 + Phase-5 smoke gate):** `docker compose up` brings the full stack (incl. required OSS ClickHouse + MinIO) to healthy and a signup → ingest → fork → run → compare round-trip passes on one host.
8. **Helm chart lint/template (Plan 0.24 + Phase-5 smoke gate):** `helm lint` clean and `helm template` renders valid manifests, with ClickHouse and Temporal encoded as **required** dependencies (no disable toggle).
9. **`terraform validate` / `terraform plan` for AWS + Azure skeletons (Plan 0.25 + Phase-5 smoke gate):** both skeletons `validate` clean and produce a coherent `plan`, with the required-ClickHouse constraint represented.
10. **Optional operator-managed KEK (Plan 0.20):** BYOK envelope encrypt/decrypt round-trips with the KEK enabled, and the app degrades cleanly with the KEK unset.

The standing **A8 enforcement gate** (Postgres RLS + ClickHouse row policies + tenant-isolation CI matrix) carries forward unchanged in intent and is now required to pass **in all three DB modes**.

### Standing constraint reaffirmed: ClickHouse is REQUIRED

"Pluggable Postgres" applies to the **control plane only**. ClickHouse is the columnar span/frame analytics store with no Postgres substitute (the trace-open / DAG / search / compare latencies depend on it). It ships bundled OSS in docker-compose and is a required dependency in Helm and Terraform — the chart/Terraform variable surfaces have no "disable ClickHouse" option. Any future proposal to drop or substitute ClickHouse is a re-gate-level change, not a configuration toggle.

### Deferral note (end-to-end deployment verification)

This re-gate clears the product and the architecture substrate, and clears the packaging at **smoke level** (3-mode matrix, S3 conformance, compose smoke, `helm lint`/`template`, `terraform validate`/`plan`). It does **not** assert a verified live deployment. End-to-end deployment verification — `docker compose up` on a clean host as the published quickstart, `helm install` against a real cluster, and `terraform apply` against scratch AWS/Azure accounts — is **DEFERRED to Plan §9 (Phase 6)**, the implementation phase that authors the docker-compose/Helm/Terraform artifacts and productionizes the abstraction layers (`AuthProvider`/GoTrue client, `ObjectStore`, `QueueConsumer`, Temporal workers, Redis SSE relay, FastAPI OTLP endpoint). Phase 6 owns the live-apply exits and the removal of the deprecated `workers/*` + `workflows/cloudflare` projects once their replacements are proven.

# ForkReplay V1 Readiness Gate Report

**Reviewer:** Readiness Gate (final independent review)
**Date:** 2026-05-12
**Docs reviewed:**
- `agent-trace-fork-prd.md` (Status: v0.8, headered v0.7 — version label inconsistency, see Gap #1)
- `implementation-readiness-spec.md` (v0.3)
- `implementation-plan.md` (v0.2)
- `questions-round-1.md` (372 lines, all answered)
- `questions-round-2.md` (139 lines, all answered)
- `questions-round-3.md` (130 lines, all answered)
- `round-2-responses/Z-doc-edits-summary.md` (round-1+round-2 changelog)
- `round-3-tactical-decisions.md` (round-3 §A–§H tactical rationale)

---

## 1. TL;DR Verdict

**READY WITH MINOR GAPS.**

The PRD, Spec, and Plan are coherent, mutually consistent on the load-bearing decisions (architecture, billing system of record, canonical objects, framework adapters, fork execution semantics, tenant isolation), and Phase 0 spike work can start tomorrow with no blockers. Three rounds of subagent → user → subagent iteration have produced a planning surface that is unusually well-developed for a V1 — the canonical object model alone is more rigorous than most production systems achieve at launch.

The gaps are real but bounded:

- **The doc consolidation pass is half-finished.** Round-3 decisions are absorbed in the PRD (header shows v0.8 in changelog block but the literal `**Status:**` line still says v0.7), but the Spec is still v0.3 and the Plan is still v0.2 — neither has been refreshed to incorporate the Round-3 deltas. This creates known but specific spec-plan-PRD drift that an engineer would hit on first read.
- **Two readiness-gate spikes are missing or under-scoped.** The Phase 0 spike list does not call out a Stripe Credit Grants chaos test or the age multi-recipient key custody ceremony as discrete spikes, even though both surfaced from Round-3 and are referenced as expectations in this gate's checklist.
- **Several Round-3 tactical decisions (system_banners table, age multi-recipient backup-key custody, billing-batch-worker co-tenancy, Resend as a stack member, 4h refund cadence vs the Plan's "sub-24h") have not been written into the Plan's Phase 1.2 / Phase 5 deliverables.**

None of these are blocking. Each can be remediated by a half-day doc-edit pass that pushes the Round-3 deltas into the Spec and Plan, plus appending 2 short spikes to Phase 0. The product contract is settled; only the consolidation is incomplete.

Recommend: do the doc-consolidation pass now (estimated 4–6 hours of focused edits), then start Phase 0.

---

## 2. Phase 0 Readiness — What Can Start Tomorrow

The Plan's Phase 0 has 18 spikes (0.1–0.18). Effort for each is 1 engineer-day to 1 engineer-week. The Plan calls out **0.8 / 0.11 / 0.10** as the highest-risk critical-path items, and **0.8 / 0.9 / 0.12** as the latency/UI-scale items that determine whether the public PRD targets are honest.

Concrete first-week kickoff (parallelizable across 3–4 engineers if available, or staged solo):

| Spike | Effort | Owner (Plan-suggested) | Critical Path? | Why first |
|---|---|---|---|---|
| 0.1 OTel GenAI Import Matrix | ~2 days | SDK lead | Yes (gates §2 Canonical schema lock) | Locks the normalization rules before Phase 1 schemas freeze. |
| 0.13 Supabase Vault Free-Tier Availability | 1 day | Security/Infra | Yes (gates BYOK encryption path; cheap to verify) | If Vault is unavailable on Free, the BYOK envelope-encryption design changes vendor. Cheap and short. Run first. |
| 0.14 CF Workflows Cold-Start | 2 days | Infra | Yes (input to 0.8) | Cold-start floor is needed before the 0.8 end-to-end measurement is meaningful. |
| 0.8 End-to-End Fork-Start Latency | 3 days | Infra + Replay-worker lead | **Highest-risk** (validates fork-start p95 ≤ 3s launch goal) | This is the entire B4-override gamble. If it fails, we revisit either the orchestrator or the 3s SLO. |
| 0.9 R2 Read Latency from Railway | 2 days | Infra | Yes (input to 0.8) | Frame-fetch is on the fork-start critical path; redis-cache sizing depends on numbers. |
| 0.10 OTLP Receiver + CF Queues Throughput | 3 days | Ingest lead | High-risk (validates 10k spans/sec/node) | Confirms the queue-buffered Phase-1 ingest path scales. |
| 0.11 LiteLLM vs Rolled-Translator | 1 week | OpenRouter lead | **Highest-risk** (E6; gates Phase 3 dispatch) | Cross-provider tool-use / reasoning_details round-trip is where most products fail silently. |
| 0.17 Claude Agent SDK Fork-Grade Fixture | 3 days | SDK lead | Yes (Claude SDK was a round-2 add; needs validation) | The OpenInference path is unproven for fork-grade. If it doesn't reach fork-grade, Claude SDK gets demoted to inspect-only. |
| 0.18 Stripe Credit Grants + Meter Events v2 Dry Run | 3 days | Billing lead | Yes (gates Phase 1 schema lock for `usage_event` + `credit_pack_grant`) | The entire billing system-of-record contract collapses if Adjustment-within-24h doesn't behave as Stripe docs claim. |

Spikes 0.2 / 0.3 / 0.4 / 0.5 / 0.6 / 0.7 / 0.12 / 0.15 / 0.16 can run in parallel with the critical-path work.

**Missing from the Plan but called out by this gate:** Stripe Credit Grants **chaos test** (Round-3 §H decision was Stripe Sandbox for chaos) and **age multi-recipient + key-custody ceremony**. Recommend adding these as Phase 0.19 and 0.20 (see remediation below).

---

## 3. Gate-by-Gate Findings

### Gate 1: Scope coherence (PRD ↔ Plan ↔ Spec) — **PASS-WITH-NOTE**

The three documents agree on V1 scope at the load-bearing level (V1 ships 3 fork-grade adapters, 6 inspect-only, 3 hard-coded exporters, mock/ai_mock/block only, defense-in-depth tenant isolation, Stripe Billing Credits + Meters as system of record, etc.). The Phase 0 → Phase 5 sequence in the Plan maps cleanly onto the PRD's deliverables.

**Note:** The PRD's header literally says `**Status:** Draft v0.8` (line 3 of `agent-trace-fork-prd.md`), but the round-2 doc-edits summary refers to the document as v0.7 and the changelog block at line 8 says "Changes from v0.7 (May 12 planning round-3 pass)". The doc-edits summary file (`Z-doc-edits-summary.md`) is a Round-1+Round-2 changelog and does not describe Round-3 propagation; the Spec is still v0.3 and the Plan is still v0.2 — neither has had a Round-3 pass. This is the largest single integration gap.

### Gate 2: Critical-path clarity — **PASS**

The critical path is clear: Phase 0 spikes 0.8 / 0.11 / 0.10 / 0.17 / 0.18 → Phase 1 control plane + RLS gates + sub-24h refund batch → Phase 2 SDK + ingest + trace inspect → Phase 3 fork engine + Workflow orchestration → Phase 4 admin panel + mocks + BYOK + 3 exporters → Phase 5 trust-posture page + tenant-isolation green + sub-24h refund batch ≥7 days + load tests + restore drill. Each phase has a clean exit criterion. No unresolved blockers between phases.

The Plan explicitly calls out which spikes are critical-path and gives effort estimates per spike. Phase 1.6 (agent-instruction scaffolding + docs harness) lands before Phase 2 so docs don't drift from day one. Phase-2 exit gate (30-min first-fork-grade trace) is concrete and CI-enforced.

### Gate 3: Phase 0 spike completeness — **PASS-WITH-NOTE (2 spikes missing/under-scoped)**

Checklist mapping:

| Expected spike | Present in Plan? |
|---|---|
| End-to-end fork-start latency including CF Workflow bootstrap | Yes (0.8) |
| R2 read-latency from Railway | Yes (0.9) |
| LiteLLM-vs-rolled-translator (E6) | Yes (0.11) |
| Real-world DAG-size measurement | Yes (0.12) |
| Railway OTLP receiver throughput | Yes (0.10) |
| Supabase Vault free-tier verification | Yes (0.13) |
| CF Workflows cold-start | Yes (0.14) |
| `redacted_thinking` passthrough through OpenRouter | Yes (0.15) |
| Interleaved-thinking beta header propagation | Yes (0.16) |
| Claude SDK fork-grade fixture | Yes (0.17) |
| **Stripe Credit Grants chaos test** | **Partial — 0.18 is "dry run," not "chaos test." Round-3 §H decision (H-R3.6) was Stripe Sandbox specifically for chaos. Not written into the Plan.** |
| **age-encryption + key custody ceremony** | **Missing — Round-3 §0.4 decision was age multi-recipient (you + 1 advisor). The Plan mentions weekly manual `pg_dump → R2` but does not describe the key-custody ceremony or the cryptographic-recipient mechanism.** |

Recommend appending two Phase 0 spikes (0.19 Stripe Sandbox chaos run, 0.20 age multi-recipient backup-key ceremony) and one Phase 1 deliverable (weekly `pg_dump → age-encrypt → R2` cron in `billing-batch-worker` per Round-3 §B-R3.3).

### Gate 4: Architecture diagram alignment — **PASS**

PRD §9 has a clear ASCII diagram showing Vercel (frontend) + Railway (4 services) + Cloudflare (Workers OTLP gateway, Queues, Workflows, SSE relay + Durable Object, R2) + Supabase (Auth + Postgres + Vault) + ClickHouse Cloud + Grafana Cloud + Stripe + OpenRouter. Component responsibilities and protocols (OTLP/HTTP+gRPC for ingest, REST/JWT for product API, EventSource/SSE through CF Workers, pull consumer over HTTP for the queue) are labeled on the edges. Sub-processors list (now including Resend per Round-3) lives at the marketing-site `/legal/sub-processors`.

**Minor note:** The PRD diagram doesn't show Resend as a labeled component (Resend was a Round-3 addition; the diagram was redrawn during the Round-2 pass). Not a blocking gap — Resend is an out-of-band transactional-email vendor, not an inline data-path component, so its omission from the data-flow diagram is reasonable.

### Gate 5: Canonical object coverage — **PASS**

Spec §2 defines all the objects Phase 1 / 2 / 3 needs:

Core: `Workspace`, `Member`, `ApiKey`, `Trace`, `Step`, `Frame`, `Message`, `ToolDefinition`, `ToolCall`, `ToolResult`, `MockDefinition`, `InterventionManifest`, `Branch`, `TrialSet`, `ExportSnapshot`, `TestCase`, `AuditEvent`, `CapabilityContract`.

Round-2 additions (all present): `RateCard`, `ModelRates`, `UsageEvent`, `BYOKUsageEvent`, `CreditPackGrant`, `Session`, `StepBuildability`, `FrameReferences`, `WorkspaceLimits`.

Phase-1 deliverables also reference: `admin_review_item`, `stripe_webhooks_processed`, `branch_event` (partitioned), `system_banners` (Round-3 addition; in PRD changelog but **not yet in Spec §2** — see Outstanding Gaps).

Every Phase 1 / 2 / 3 user-visible workflow has a canonical-object backing. Tenant scoping (`workspace_id`) is universal. Provenance fields are present on derived objects.

### Gate 6: Event taxonomy completeness — **PASS**

Spec §10 lists ~70 events across lifecycle, ingest/buildability, fork/branch, mocks, provider/reasoning, and billing/BYOK. Round-2 additions are all present: `mock.*` (matcher_no_match, template_render_failed, schema_mismatch, scratchpad_overflow, approval_*, branch_override_granted, capability_contract_*), `workflow.dead_letter`, `frame.*` (hash_changed, size_warning, size_exceeded), `step.*` (buildable, built, unbuildable), `marker.malformed`, `reasoning.*`, `provider.*`, `model.substitution_*`, `byok.*`, `billing.*`, `credit_pack.*`, `overage.*`, `rate_card.changed`, `workspace_limits.changed`.

Explicit note that `mock.matched` is a Grafana counter (not an audit row) per F-S5 / F-R3.7. Good — that's the kind of distinction that prevents an audit-table volume blow-up at launch.

### Gate 7: Decisions trail (binding decisions reflected in PRD/Spec/Plan) — **PASS-WITH-NOTE**

Sampled 5 decisions per round:

**Round 1:**
- A1 (3 GA exporters) — reflected in PRD §6 Q10, Spec §1, Plan Phase 4. ✓
- A3 (3 fork-grade + 6 inspect-only) — reflected in PRD §10, Spec §3 framework table, Plan §1 + Phase 2.1. ✓
- A8 (defense-in-depth + RLS required) — reflected in PRD §7.2 + §7.6 + §8, Spec §8, Plan §1.2 + Phase 5 A8 gate. ✓
- B4 (Workflow orchestrates every step including first) — reflected in PRD §13 #13, Spec §4 Durable Orchestration, Plan §1 + Phase 3.2. ✓
- H14 (verb-on-resource API scopes) — reflected in PRD §7.6, Spec §2 ApiKey, Plan §1.2. ✓

**Round 2:**
- §0.4 (1 credit = $0.001) — reflected in PRD §13 #6, Spec §11 row 4. ✓
- §0.5 (per-model reasoning rate from day one) — reflected in PRD §7.7, Spec §2 ModelRates, Spec §11 row 5. ✓
- §0.3 (5-item admin panel) — reflected in PRD §13.A + §10, Spec §11 row 32 + §9 WorkspaceLimits. ✓
- G-R2.5 (`forkreplay-auto` is V1 not V1.1) — reflected in PRD §7.1 + §13 #10, Spec §3, Plan Phase 2.1. ✓
- H-R2.5 (Adjustment-only, sub-24h batch cadence) — reflected in PRD §9, Spec §11 #6, Plan §1.2 (cron every 4h). ✓

**Round 3:**
- §0.1 (`[auto]` is detection logic only) — **reflected in PRD changelog only.** Not yet in Spec §1 ("First Launch Acceptance Criteria" still says `pip install forkreplay-sdk[claude]`) or Plan §2.1 (`[auto]` extra description in Plan still implies it pulls all 9). ✗ — needs update.
- §0.2 ($1k MRR Supabase Pro trigger) — **PRD changelog only.** Spec §8 still says "first paid commercial milestone"; Plan §1 same. ✗ — needs update.
- §0.5 (credit packs $10 min + 3 presets) — **PRD §6 Q5 / §7.7 only.** Spec §2 `CreditPackGrant` does not mention $10 minimum or preset amounts; Plan does not reference Stripe Checkout custom-amount flow. ✗ — needs update.
- §0.7 (workflow_step_retries Free=1 / Pro=5 / Enterprise=10) — **PRD only.** Spec §2 / §9 `WorkspaceLimits` does NOT list `workflow_step_retries` at all (only `retry_count_override` on Branch). ✗ — needs update.
- A-Q4 (4h refund cadence) — **Spec/Plan say "sub-24h batch" or "every 4h is default."** Plan §1.2 has "cron every 4h is the default" which matches; Spec §11 #6 says "sub-24h batch cadence (cron every 4h is the default, hourly/sub-hourly permitted)" — matches. ✓ (this one is consistent.)

**Verdict on Round 3:** The Round-3 decisions live in the PRD changelog and PRD body, but they have NOT been propagated into the Spec §2 canonical objects, the Spec §8 security/RPO language, or the Plan's Phase-1/Phase-4 deliverables. This is mechanical follow-up work, not a planning gap.

### Gate 8: Open items / known constraints — **PASS**

PRD §13.A "V1 deliberately-constrained scope" lists exactly the constraints the gate asks about:

- No public availability SLA (internal 99.0% SLO only) ✓
- No public status page in V1 (V2+) ✓
- No third-party penetration-test attestation in V1 ✓
- Free-tier infra is intentional (Supabase Free, Cloudflare paid Workers, ClickHouse Cloud Scale, Railway Hobby+) ✓
- ~24h best-effort RPO (Supabase Free has no PITR) ✓
- Privacy posture is paid-tier-only (Free permissive; Paid can opt INTO strict) ✓
- Python-only SDK (TS is V2+, not V1.1) ✓
- Admin panel scope locked at 5 surfaces ✓

PRD §2 Non-Goals adds: no live tool execution, no schema engine in V1 GA, no EU residency (V2), no HIPAA (off-roadmap), no SSO/SCIM (V1.1+), no browser-session replay, no mid-stream forks. Both lists are honest and customer-facing-ready.

### Gate 9: Risk register sanity check — **PASS**

PRD §11 risk table covers the highest-impact risks from Round-3 surprises:

- Cloudflare Workflows hits unanticipated limit — captured with `step.do` aggregation + R2 frame pointer + Inngest/DBOS noted as Plan-B.
- Workflow-orchestrates-every-step cold-start adds latency — captured with pre-warmed Workflow + Phase-0.8 spike validation.
- Cross-provider model swap loses reasoning_details — captured with V1 drop-with-warning + V1.1 re-translation.
- Claude Agent SDK hook API churn — captured with pinned minor version + weekly CI + abstract instrumentor + Anthropic native OTel cutover.
- No public SLA + no status page = procurement friction — captured with trust-posture page + postmortem-under-NDA discipline.
- Single-vendor outage = product outage — captured as accepted (D6).
- Supabase Free has no PITR; V1 RPO is ~24h — captured with weekly `pg_dump → R2` safety net + commercial-milestone upgrade.

Two Round-3 risks could be more explicit:

1. **age key custody / bus factor.** Round-3 §0.4 picked age multi-recipient (you + 1 advisor) to eliminate bus-factor-of-1, but the PRD risk table does not call out "primary backup-key holder unavailable" as a discrete risk. Mitigation is now in place (advisor recipient), but the risk and mitigation aren't documented as a pair.
2. **Stripe Adjustment 24h window.** PRD touches this in §13.A and the changelog, but the explicit risk "refund batch falls behind → adjustments expire → refunds lost" is not in the §11 risk table. It's implied by the Plan's Phase-5 launch-blocker exit gate (sub-24h batch ≥7 days clean), but a customer reading only the PRD would not see the operational fragility.

### Gate 10: First-week implementation kickoff — **PASS-WITH-NOTE (AGENTS.md/CLAUDE.md missing)**

A new engineer reading the PRD + Spec + Plan today can:

- Understand the product, the V1 scope, and the constrained-by-design gaps.
- See the architecture diagram, identify the 8 cloud services, and provision them.
- Read the 18 Phase-0 spike list and pick up any spike with effort estimate and exit criteria.
- Reference the Spec §2 canonical objects to start schema design.

What they **cannot** do today:

- Find `AGENTS.md` or `CLAUDE.md` in the repo. The Plan calls these out as Phase-1.6 deliverables (with the "V1 deliberately-constrained scope" embedded), but they do not yet exist. The `.claude/skills/docs-update.md` skill and the `docs-drift-check` GitHub Actions check don't exist either — these are also Phase-1.6 items.
- See a milestone issue list. The Plan §10 says the "Immediate Next Artifact After This Plan" is a technical architecture and milestone breakdown — but that artifact has not been written yet.

This is consistent with where the planning sits ("ready to implement, not yet implementing"), but worth flagging: the agent-instruction scaffolding the Plan promises is itself a Phase-1.6 deliverable, so a brand-new engineer in week 1 doesn't have it as a guardrail.

---

## 4. Outstanding Gaps / Risks (ordered by severity)

### Severity: High — Spec and Plan not refreshed for Round 3

**Gap:** The Round-3 doc-edits pass touched only the PRD. The Spec (still v0.3, dated 2026-05-12) and the Plan (still v0.2, dated 2026-05-12) do not reflect §0.1 ([auto] install posture), §0.2 ($1k MRR Supabase Pro trigger), §0.5 (credit pack $10 min + 3 presets), §0.7 (workflow_step_retries Free=1/Pro=5/Enterprise=10), system_banners table, Resend in stack, age multi-recipient key custody, 4h refund-batch cadence (Plan says "sub-24h" which is technically compatible, but A-Q4 locked the cadence to 4h aggregated), billing-batch-worker co-tenancy (B-R3.3), restore-drill cadence change (D-R3.Q1 quarterly), SSE-DO self-terminate 60s, backup key rotation annual.

**Remediation:** A focused 4–6 hour doc-edits pass before Phase 0 starts. Spec bump v0.3 → v0.4; Plan bump v0.2 → v0.3. Land in **Phase 0 prep**, not as part of Phase 1 — this is consolidation, not new work.

### Severity: High — PRD version header inconsistency

**Gap:** The PRD `**Status:**` line says "Draft v0.8" but no v0.8 changelog block exists; the changelog at line 8 still reads "Changes from v0.7." This is cosmetic but creates confusion about which round of changes is incorporated.

**Remediation:** Edit the PRD `**Status:**` to read `v0.8` consistently, add a new "Changes from v0.7" header to the changelog block at line 8, and note that the v0.8 pass is the Round-3 absorption. **Land in the same Phase 0 prep doc-edits pass.**

### Severity: Medium — Phase 0 missing Stripe chaos test and age key-custody ceremony

**Gap:** This gate's checklist called out "Stripe Credit Grants chaos test" and "age-encryption + key custody ceremony" as expected Phase 0 spikes. The current Plan has 0.18 as a "dry run" (basic happy-path), not a chaos test, and has no separate ceremony.

**Remediation:** Add two spikes to Phase 0:
- **0.19 Stripe Sandbox Credit Grants chaos run (2 engineer-days).** Per H-R3.6, exercise the refund-batch path with simulated 24h-window-breach failures (cron not running, Stripe API rate limit, partial-success Adjustment batches). Validate that refund liability is bounded and that the 5%/7d on-call-page threshold (H-R2.4) fires reliably.
- **0.20 age multi-recipient backup-key custody ceremony (1 engineer-day).** Per §0.4, generate the multi-recipient age key, distribute the advisor recipient, document the recovery runbook, and verify a test-encrypted blob can be decrypted with each recipient independently. Land the recovery runbook in `docs/runbooks/backup-key-recovery.md` as a Phase 0 deliverable.

Both can be in parallel with the existing critical-path spikes.

### Severity: Medium — `system_banners` table not in Spec §2

**Gap:** Round-3 §H-R3.12 introduces `system_banners` as the V1 status-page replacement. It's mentioned in the PRD changelog but is not a defined canonical object in Spec §2, and Plan §1.2 doesn't list it as a Phase-1 schema deliverable.

**Remediation:** Add `SystemBanner` to Spec §2 (workspace_id-scoped, content + severity + start_at + end_at + visibility_scope + active flag), and add it to Plan §1.2's Postgres schema list. Land it in the Round-3 doc-edits pass.

### Severity: Low — risk register missing two Round-3 risks

**Gap:** "Primary backup-key holder unavailable" and "refund batch falls behind → Adjustment window expired → refunds lost" are not in PRD §11.

**Remediation:** Append two rows to the risks table during the Round-3 doc-edits pass. Mitigations already exist (advisor recipient; H-R2.4 5%/7d page); the risks just need to be documented as a pair with their mitigations.

### Severity: Low — Phase-1.6 agent scaffolding hasn't shipped

**Gap:** The Plan promises `AGENTS.md`, `CLAUDE.md`, `.claude/skills/docs-update.md`, and `docs-drift-check` CI as Phase 1.6 deliverables. None exist yet. A first-week engineer working on Phase 0 spikes will not have the scope-creep guardrails the Plan describes.

**Remediation:** Land Phase 1.6 as the **first** Phase 1 task, parallel with Phase 0 spike execution rather than after Phase 0 completes. The scaffolding itself is ~1 day of writing. Doing this in week 1 means the scope-creep guard is active during Phase 0 already.

### Severity: Low — milestone issue list / technical architecture artifact not yet produced

**Gap:** Plan §10 says the next artifact after the Plan is a milestone issue list + technical architecture + initial OpenAPI inventory + CF Workflow lifecycle sketches + SDK package outline. This work has not started.

**Remediation:** This is exactly the right scope for the immediate-next-step. Produce it after the Round-3 doc-edits pass and as parallel work to Phase 0. Not a launch blocker; a tooling artifact.

---

## 5. Recommended First-Week Kickoff Actions

In priority order. Most can run in parallel; the dependencies are noted.

### Day 1 (consolidation; sequential before anything else)

1. **Round-3 doc-edits pass** on Spec and Plan (4–6 hours, single owner). Bumps Spec v0.3 → v0.4, Plan v0.2 → v0.3. Apply the gaps listed in §4 above. Output: clean spec/plan that match PRD v0.8 / Round-3 decisions.
2. **PRD version-header fix** (15 minutes). Make `**Status:**` and changelog block agree on v0.8.

### Day 1–3 (Phase 1.6 scaffolding, parallel with Phase 0 start)

3. **Create `AGENTS.md` and `CLAUDE.md`** at the repo root with: V1 product summary + V1 deliberately-constrained scope section (§13.A verbatim) + reference to PRD/Spec/Plan + scope-creep guard language. (~1 day.)
4. **Create `.claude/skills/docs-update.md`** and `.codex/skills/docs-update.md` with the docs-edit workflow. (~3 hours.)
5. **Create `.github/workflows/docs-drift-check.yml`** path-glob CI. (~3 hours.)

### Day 1–5 (Phase 0 spike kickoff, parallelize aggressively)

6. **Provision infra accounts:** Supabase (Free), ClickHouse Cloud (Scale), Cloudflare (Workers + Queues + R2 + Durable Objects + Workflows v2 beta), Railway (Hobby+), Vercel (Hobby + Pro upgrade ready), Grafana Cloud (free tier), Stripe (test mode + Sandbox), OpenRouter (platform key + workspace test key), Resend. Document IDs and access in a shared password manager.
7. **Run Spike 0.13** (Supabase Vault Free-tier check; 1 day). Lowest effort, highest decision value. If Vault fails, the BYOK story changes.
8. **Run Spike 0.1** (OTel GenAI Import Matrix; 2 days). Locks the normalization rules so canonical-object schema can freeze.
9. **Run Spike 0.14** (CF Workflows cold-start; 2 days) → **feeds into Spike 0.8** (fork-start latency, 3 days). Sequential.
10. **Run Spike 0.18** (Stripe Credit Grants dry run; 3 days) → **plus newly-added Spike 0.19** (Sandbox chaos run; 2 days). Sequential.
11. **Run Spike 0.20** (age multi-recipient key ceremony; 1 day). Independent.
12. **Run Spike 0.11** (LiteLLM vs rolled translator; 1 week). Highest implementation risk; start as early as possible since it has the longest tail.

### Week 2 (Phase 0 completion + Phase 1 schema lock prep)

13. Finish remaining Phase 0 spikes (0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.9, 0.10, 0.12, 0.15, 0.16, 0.17). Most are 1–3 engineer-days. Run in parallel.
14. **Begin Phase 1.1 / 1.2** repo layout + control-plane schema in parallel with the slower spikes. The Spec §2 canonical-object model is concrete enough to start schema work without waiting for every spike to finish.

### Week 3–4 (Phase 0 exit)

15. **Phase 0 exit review.** All 20 spikes have written results + proof code. Specifically validate the **fork-start 3s p95** (or accept 4s slip), **10k spans/sec/node** (or escalate), **Vault Free-tier viability**, **OpenRouter cross-provider tool-use round-trip**, and **Stripe Adjustment within 24h reliable**. Document any decisions to walk back.

### Files to create in week 1

- `/Users/andrew/Scripts/ForkReplay/AGENTS.md`
- `/Users/andrew/Scripts/ForkReplay/CLAUDE.md`
- `/Users/andrew/Scripts/ForkReplay/.claude/skills/docs-update.md`
- `/Users/andrew/Scripts/ForkReplay/.codex/skills/docs-update.md`
- `/Users/andrew/Scripts/ForkReplay/.github/workflows/docs-drift-check.yml`
- `/Users/andrew/Scripts/ForkReplay/docs/runbooks/backup-key-recovery.md` (output of Spike 0.20)
- `/Users/andrew/Scripts/ForkReplay/docs/spikes/0.{1..20}-results.md` (one per spike)
- Updated `/Users/andrew/Scripts/ForkReplay/implementation-readiness-spec.md` (v0.4)
- Updated `/Users/andrew/Scripts/ForkReplay/implementation-plan.md` (v0.3)
- Repo layout: `apps/web`, `services/{api,ingest,replay-worker,mock-gen-worker,export-worker,billing-batch-worker}`, `workers/{otlp-gateway,sse-relay}`, `workflows/cloudflare`, `sdk/python`, `packages/contracts` (per Plan §1.1).

### Infrastructure to stand up first

1. Supabase project (Free tier) — verifies Vault, gives schema-deployment target for Phase 1.
2. Cloudflare Workers + R2 + Queues + Workflows v2 beta — gates 0.8 / 0.9 / 0.10 / 0.14.
3. ClickHouse Cloud (Scale) — gates 0.4.
4. Railway test project — gates 0.2 / 0.10.
5. Grafana Cloud (Tempo + Loki + Mimir) — observability sink from day one.
6. Stripe (test mode + Sandbox) — gates 0.18 / 0.19.
7. OpenRouter (platform key + test workspace key) — gates 0.11 / 0.15 / 0.16.
8. GitHub repo with OIDC federation to Cloudflare + Railway Project Tokens in GHA secrets.

---

## 6. Open Questions Still Requiring User Input

**None that are blocking.** Three minor items the user may want to confirm explicitly, but each has a defensible default:

1. **Doc-edits pass owner.** Round-3 changes landed in PRD but not Spec/Plan. Is this a subagent run, or does the user want to do it directly? Default recommendation: a single subagent pass with explicit "incorporate Round-3 decisions into Spec and Plan; bump Spec to v0.4 and Plan to v0.3" instructions. ~4–6 hours subagent effort.
2. **Phase-1.6 timing.** Plan §1.6 places AGENTS.md/CLAUDE.md in Phase 1, after Phase 0 completes. Recommend pulling forward to week 1 (parallel with Phase 0) so the scope-creep guard is active during spike work. Trivial scope question; default is "pull forward."
3. **Spike 0.19 / 0.20 addition.** Two new Phase 0 spikes (Stripe Sandbox chaos run; age key custody ceremony) are recommended by this gate but not currently in the Plan. The user can either accept these additions or push them to Phase 1. Recommend acceptance — both are cheap, both eliminate real risk.

Everything else is mechanical follow-up.

---

## Closing Note

This is an unusually well-developed V1 planning surface. The canonical-object model in Spec §2 is rigorous; the Phase 0 spike list is honest about what needs validating before commitment; the V1 deliberately-constrained scope section is the most useful artifact in the PRD because it makes the V1 trade-offs auditable in advance.

The gaps are concentrated in one place: the Round-3 doc-edits pass touched only the PRD, leaving the Spec and Plan one round behind. Fix that gap, append two cheap Phase 0 spikes, land Phase 1.6 in week 1, and the team is ready to build.

**Verdict: READY WITH MINOR GAPS.** Recommend a one-day consolidation pass, then start.

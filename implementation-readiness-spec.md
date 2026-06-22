# ForkReplay V1 Implementation-Readiness Spec

**Status:** Draft v0.5
**Owner:** Andrew
**Last updated:** 2026-06-21
**Related:** `agent-trace-fork-prd.md` (v0.9), `competitive_analysis.md` (v0.4)

v0.5 (OSS pivot) turns the contracts from a managed multi-vendor SaaS into an **open-source, self-hostable** product. Major changes:
- **License:** Apache-2.0. Single self-hostable codebase; no managed-SaaS layer.
- **Auth (§8):** **GoTrue** (Supabase Auth OSS) in all DB modes; deployment-mode-agnostic GoTrue JWT validation. Native Postgres RLS for tenant isolation. Removes Supabase-Auth-specific assumptions.
- **Data layer:** pluggable control-plane Postgres via `DB_MODE=supabase | custom | compose`. **ClickHouse remains required** in every mode (bundled OSS in compose; required in Helm/Terraform). The analytics plane is not pluggable.
- **Orchestration (§4):** **Temporal** (workflow/activity model) replaces Cloudflare Workflows `step.do`/`waitForEvent`. Branch state machine retained.
- **Streaming:** **Redis-backed FastAPI SSE** replaces the CF Workers SSE relay + Durable Object.
- **Storage:** **S3-compatible abstraction** (MinIO / AWS S3 / Azure Blob) replaces R2-specific keys; content-addressing + workspace-scoped prefixes retained.
- **Queue:** **NATS** (Redis Streams alternative) replaces Cloudflare Queues; OTLP ingress is a **FastAPI endpoint** (replaces the CF Workers otlp-gateway).
- **Secrets/BYOK (§8):** operator/workspace keys via env/secret + an **optional KEK** (age/libsodium). **No Vault.** Removes the `replay_worker_byok` Supabase-Vault accessor framing; least-privilege intent kept generically.
- **LLM routing:** pluggable — OpenRouter / direct OpenAI/Anthropic / Ollama via config. **Email:** pluggable SMTP (Resend / SMTP / console) for GoTrue confirmations.
- **Billing REMOVED:** all Stripe contracts (webhook receiver, meter events, reconciliation, refund batch, credit packs) deleted. Object model drops `CreditPackGrant`, `UsageEvent`, `BYOKUsageEvent`, and RateCard-as-billing; `RateCard`/`ModelRates` survive **only as an informational cost estimate**. `WorkspaceLimits` keeps operational fields and drops billing-only fields. `Branch` drops `credit_*`/`refund_*` fields (credit_estimate reframed as an informational cost estimate). The §10 billing/credit/overage/rate_card/reconciliation event taxonomy is removed; product/ingest/fork/mock events kept.
- **`system_banners`** stays as the operational banner mechanism, now FastAPI/Redis-backed (not CF-SSE).
- **Deprecated/slated-for-removal** (documented, not deleted this pass): `workers/otlp-gateway`, `workers/sse-relay`, `workflows/cloudflare`, `services/billing-batch-worker`.

v0.4 (May 12 planning round-3 pass) incorporates: `workflow_step_retries` tier maxes (Free ≤ 1, Pro ≤ 5, Enterprise ≤ 10) baked into the `WorkspaceLimits` CHECK constraint; `CreditPackGrant` reworked for Stripe Checkout custom-amount flow with a $10 minimum and three one-click presets (not three static SKUs); `frame_mock_bindings.mock_version_hashed` field added per C-R3.4; `AuthPolicy` / `WorkspacePrivacyPosture` gains a 24h-revert banner state field; new events added (`railway_audit.ingested`, `rate_card.reasoning_inferred`, `mock.gen_contract_truncated`); confirmation that `mock.matched` and `frame.rebuilt_idempotent` are Grafana counters/UI-collapsed events; §11 planning decisions extended with Supabase Pro at $1k MRR, retry caps tier maxes, pack custom-amount flow, system_banners CMS for incident comms; `forkreplay-sdk[auto]` install posture clarified to detection-only.

This document turns the PRD into product contracts that are concrete enough to plan implementation. v0.3 incorporates the May 12 planning round-2 decisions: Vercel + Railway split for hosting; Cloudflare Workers SSE relay; Cloudflare Queues between OTLP receive and stitch; Grafana Cloud as the OTel sink; LangGraph + OpenAI Agents SDK + Claude Agent SDK as the three fork-grade fixtures; six inspect-only frameworks via OpenInference; explicit-capture core API with decorator ergonomics; `forkreplay-auto` one-line bootstrap; Stripe Billing Credits + Meters as system of record with 1 credit = $0.001 denomination; per-model reasoning-token rate from day one; ±20% cost-estimate accuracy SLO; tenant isolation as defense-in-depth with required RLS + ClickHouse row policies; verb-on-resource API key scope taxonomy; `forkreplay.*` step-boundary marker namespace; new canonical objects (MockDefinition, ToolDefinition, CapabilityContract, RateCard/ModelRates, UsageEvent, BYOKUsageEvent, CreditPackGrant, Session, StepBuildability, FrameReferences); and a V1 admin panel locked at 5 surfaces.

---

## 1. V1 Thin Slice

The first shippable slice should prove the core product loop:

1. An operator deploys ForkReplay (docker-compose quickstart) and a user creates a workspace (or uses the pre-created default workspace in single-tenant mode).
2. The user signs in through GoTrue and creates a workspace ingest key.
3. The user instruments a Python agent with the ForkReplay Python SDK (explicit-capture core; decorators are sugar where boundaries map to a function call). For inspect-only frameworks, the user adds `import forkreplay.auto` as the one-line bootstrap.
4. ForkReplay ingests one fork-grade trace.
5. The user opens the trace, inspects the step DAG/timeline, and selects a fork point.
6. The user edits one intervention: message edit, system prompt edit, tool result correction, or model/sampling override.
7. ForkReplay resolves all downstream tools with `mock`, `ai_mock`, or `block`.
8. The user runs one branch.
9. ForkReplay shows branch progress and a comparison against the original.
10. The user converts the successful branch into a generic test case.

### V1 Launch Tiers

**V1 launch-critical**
- GoTrue auth baseline (all DB modes): email/password plus federated OAuth/OIDC providers; deployment-mode-agnostic JWT validation.
- Pluggable control-plane Postgres (`DB_MODE=supabase | custom | compose`); required ClickHouse analytics store in every mode.
- Workspace, roles, API keys (verb-on-resource scope taxonomy), audit log. Multi-tenant core retained; single-tenant (default-workspace) quickstart documented.
- Fork-grade framework-neutral Python adapter plus three fork-grade framework integrations: **LangGraph, OpenAI Agents SDK, Claude Agent SDK**.
- Inspect-only OpenInference passive OTel mappings for six frameworks: LlamaIndex, Pydantic AI, smolagents, Strands Agents, AutoGen, CrewAI.
- `forkreplay-auto` one-line bootstrap module.
- OTLP ingest for passive traces (FastAPI OTLP endpoint + NATS + ingest-worker stitch/redact/write).
- Active-track ingest for adapter traces (with `forkreplay.*` step-boundary markers).
- Trace list/detail, step inspector, message timeline, DAG view (≤2k step-DAG nodes interactive; progressive disclosure above).
- Per-step fidelity badging (`exact` / `schema_equivalent` / `approximate`).
- Fork editor with guided intervention templates and substitution dialog.
- Mock, ai_mock, and block tool policies; AI-mock review/approve/disable flow.
- Branch execution through Temporal (orchestrates every step including the first), FastAPI SSE backed by Redis pub/sub (Last-Event-ID resume), comparison, effect summary.
- Repeated trials.
- **Three hard-coded exporters: generic trajectory JSONL + generic JSON test case + Promptfoo.**
- Operator quotas (`WorkspaceLimits`); LLM token tracking (rolling 30-day, admin-configurable alert/cutoff, no hard cap by default); informational cost estimates as ±20% range; hard token/step caps.
- Reasoning-token cost as a separate line item in the informational estimate, using a per-model `reasoning_rate` from day one.
- Pluggable LLM routing (OpenRouter / direct OpenAI/Anthropic / Ollama) and pluggable SMTP email (Resend / SMTP / console).
- V1 admin panel locked at 5 surfaces: per-workspace limits, auth-policy, member management, LLM-routing/key config, retention/redaction.
- **No billing/metering** — no Stripe, no credits, no meters, no reconciliation, no refund batch.

**V1 can be beta behind flags**
- Vector similarity search.
- Per-trace ACLs beyond workspace role checks.
- Advanced branch-tree visualization for very large trees.

**V1.1 (behind `exporters.v1_1` feature flag; no preview surface in V1)**
- Schema configuration engine.
- HuggingFace package export, TRL SFT, TRL DPO, OpenAI SFT, OpenAI/Together preference JSONL, Inspect, Braintrust, LangSmith mappings.
- ClickHouse message search projection.
- `llm_synthesize` runtime mock execution mode.
- Cross-provider lossy re-translation of `reasoning_details`.
- Anomaly detection on LLM token consumption.

**V1 non-goals**
- Live tool execution.
- TypeScript adapter SDK (V2+, not V1.1).
- Browser screen/action replay.
- Enterprise SSO/provisioning with SAML/SCIM.
- Built-in judges/scorers/assertion DSL.
- A hosted/managed SaaS run by the ForkReplay team (self-host is the product).
- Built-in billing, metering, payments, or a credit/usage ledger (removed; operators bring their own).
- A Postgres-only mode that drops ClickHouse (ClickHouse is required).

### First Launch Acceptance Criteria

- A new workspace can ingest a fork-grade trace within 30 minutes of signup using documented Python adapter steps.
- A new workspace can produce a fork-grade trace using the Claude Agent SDK with one OpenTelemetry instrumentor install and no application-code edits (via `pip install forkreplay-sdk[claude]` + the OpenInference Claude SDK instrumentor).
- A trace with at least five agent steps and two tool calls can be forked from a middle step.
- If downstream tool mocks are missing, the branch is blocked before execution with a precise remediation list.
- A user can (a) generate an AI-mock draft, (b) review the matcher rules and output template, (c) edit either, (d) approve workspace-scoped or branch-scoped, (e) execute a branch that resolves a tool call through that mock with deterministic output.
- Branch comparison identifies the first divergent model decision or tool call.
- A completed branch can be converted into a generic JSON test case.
- Every fork, export, auth change, API key action, and LLM-routing/key change writes an audit event.
- Postgres RLS and ClickHouse row-policy conformance tests pass in CI; tenant-isolation conformance test green and merged.

---

## 2. Canonical Object Model

All canonical objects must include:
- `schema_version`
- `workspace_id`
- stable object ID
- `created_at`
- `updated_at` where mutable
- `created_by` where user-initiated
- provenance links to source objects where derived

All IDs are opaque strings. Timestamps are ISO-8601 UTC. User-facing names are mutable; IDs are not.

### Workspace

Purpose: tenant boundary.

Required fields:
- `workspace_id`
- `name`
- `slug`
- `retention_policy_id`
- `redaction_policy_id`
- `limits_id`: FK to `WorkspaceLimits` (operational quotas; no billing).
- `llm_routing_status`: `default`, `configured`, `error`, `disabled` — whether the workspace overrides the operator-default LLM routing/key.
- `auth_policy`: enabled login methods, allowed domains if configured

Invariants:
- Every trace, branch, export, test, API key, and audit event belongs to exactly one workspace.
- No cross-workspace derived object is allowed in V1.

### Member

Purpose: user membership in a workspace.

Required fields:
- `member_id`
- `workspace_id`
- `auth_user_id`
- `email`
- `role`: `admin`, `editor`, `viewer`
- `status`: `invited`, `active`, `disabled`, `removed`

Role rules:
- Admin: workspace settings, quotas, LLM routing/key config, API keys, redaction, exports, member management.
- Editor: ingest, inspect, fork, run branches, create tests/datasets, export if allowed by workspace policy.
- Viewer: inspect traces, branches, tests, and exports; no fork execution or export creation.

### ApiKey

Purpose: SDK ingest and programmatic access.

Required fields:
- `api_key_id`
- `workspace_id`
- `name`
- `scopes`: `TEXT[]` — verb-on-resource taxonomy (H14). Allowed values:
  - `traces:write`, `traces:read`
  - `branches:write`, `branches:read`
  - `exports:write`, `exports:read`
  - `mocks:write`, `mocks:approve`
  - `workspace:admin`
- `status`: `active`, `revoked`, `expired`
- `created_by`
- `last_used_at`
- `expires_at`

Invariants:
- API key secret is shown once.
- Revoked keys cannot ingest new spans.
- Every API key use is workspace-scoped and audit logged at least by key ID, action, and timestamp.
- `mocks:approve` is sensitive (an attacker with this scope could approve adversarial mocks that influence branch execution). The UI shows a warning when granting it; by default no API key includes it.

### Trace

Purpose: immutable captured execution. Traces are open-ended at the trace level; buildability is a per-step property (see `StepBuildability`).

Required fields:
- `trace_id`
- `workspace_id`
- `source_trace_id`
- `source`: `otlp_http`, `otlp_grpc`, `adapter`, `file_import`
- `capture_mode`: `passive`, `active`
- `service_name`
- `environment`
- `session_id` — references `sessions.conversation_id`. Extracted from `gen_ai.conversation.id` first; falls back to LangSmith `thread_id`, OpenAI Agents `group_id`/`session_id`, Claude SDK session id, OpenInference `session.id`, or a synthetic `synthetic:<trace_id>` if none found.
- `root_span_id`
- `status`: `ingesting`, `ready`, `failed`, `expired`, `deleted`
- `content_capture`: `none`, `metadata_only`, `messages`, `messages_and_tools`
- `semconv_source`: `otel_genai`, `openinference`, `framework`, `custom`
- `semconv_version`
- `started_at`
- `ended_at`
- `expires_at`
- `summary`: counts, latency, token usage, model/provider list, error count

Optional fields:
- `external_user_id_hash`
- `tags`
- `privacy_classification`: `normal`, `sensitive`, `restricted`

Invariants:
- Original trace spans are immutable after capture.
- Late spans extend a trace at any time; they may trigger frame rebuilds for affected steps (see the `StepBuildability` table below).
- Redaction is applied before trace content becomes visible in the product.
- Passive traces may be viewable but not fork-grade.
- `ready` means "at least one step is buildable;" no separate "finalized" or "partial" status — buildability is per-step.

### Step

Purpose: logical unit of agent work reconstructed from spans or emitted by adapter.

Required fields:
- `step_id`
- `trace_id` or `branch_id`
- `step_type`: `llm_call`, `tool_execution`, `agent_invocation`, `workflow_invocation`, `human_input`, `system`
- `ordinal`
- `parent_step_ids`
- `span_ids`
- `status`: `pending`, `running`, `completed`, `failed`, `blocked`, `fixed_from_parent`
- `started_at`
- `ended_at`
- `input_refs`
- `output_refs`
- `error`

Conditional fields:
- LLM step: model/provider/config, message IDs, token usage, cost estimate.
- Tool step: tool name, tool call ID, tool result ID, execution policy.
- Agent/workflow step: agent ID/name/version, child step IDs.

Invariants:
- A step belongs either to an original trace or to a branch, not both.
- Branch steps before the fork point may be referenced from parent as fixed history.
- Branch steps after the fork point are branch-owned.

### Frame

Purpose: forkable state at a step boundary. Stored as a content-addressed blob in the S3-compatible object store; the control-plane Postgres holds the pointer row.

Required fields:
- `frame_id`
- `workspace_id`
- `trace_id` or `branch_id`
- `step_id`
- `step_ordinal`
- `boundary`: `before_step`, `after_step`
- `messages` (embedded inside the frame blob, not first-class storage)
- `tool_catalog_hash`
- `model_config`
- `sampling_config`
- `external_context_refs`
- `capability_contract_ref`
- `checkpoint_fidelity`: `exact`, `schema_equivalent`, `approximate`, `unrestorable` — adapter-declared.
- `fidelity_badge`: `exact`, `schema_equivalent`, `approximate` — derived by the ingest pipeline.
- `content_hash`: `sha256-<hex>`, computed over JCS-canonicalized payload. 64-char lowercase hex, no truncation.
- `object_key`: `frames/<workspace_id>/<hash[0:2]>/<hash[2:4]>/<full_hash>` — key in the S3-compatible object store (MinIO / AWS S3 / Azure Blob); workspace-scoped key prefix; no cross-tenant blob sharing.
- `size_bytes`
- `rebuild_count`: integer, default 0 (incremented when a late span retroactively belongs to this step).
- `last_rebuilt_at`: nullable timestamp.
- `superseded_at`: nullable; non-null means this is an older version replaced by a later content hash for the same step.
- `valid_for_fork`: boolean (conjunction of seven concrete checks: workspace_id present, schema_version supported, messages captured, tool_catalog captured, sampling_config captured, system_prompt captured, redaction policy applied).
- `invalid_reason`: nullable string.

Size limits:
- **Soft warning at 1 MB.** Frame persisted normally; UI surfaces a non-blocking notice.
- **Hard reject at 5 MB.** Frame builder fails; step marked `unbuildable` with `invalid_reason='frame_size_exceeded'`.
- Per-item content above **256 KB** is externalized: stored as a separate object `frames/<workspace_id>/blobs/<hash>.bin` in the S3-compatible store and referenced by hash from inside the frame.

Invariants:
- Fork execution requires `valid_for_fork=true`.
- UI must show fidelity caveats before branch execution.
- Frames are immutable per content hash; older versions are retained as long as any branch / intervention / test_case / export_snapshot references them (see `FrameReferences`).
- A frame that has been rebuilt at least once (`rebuild_count > 0`) cannot have a `fidelity_badge` of `exact`; the badge caps at `schema_equivalent`.

### Message

Purpose: normalized conversational unit used by the UI and exporters.

Required fields:
- `message_id`
- `role`: `system`, `developer`, `user`, `assistant`, `tool`
- `content_blocks` — provider-original blocks preserved inside a `provider_format`-tagged envelope.
- `provider_format`: `openai`, `anthropic`, `gemini`, `generic`
- `source_step_id`
- `created_by`: `original`, `adapter`, `user_intervention`, `branch_execution`

Optional fields:
- `tool_calls`
- `tool_call_id`
- `attachments`
- `hidden_reasoning_policy`: `not_captured`, `captured_not_exportable`, `captured_not_exportable_signed` (V1.1+ extensibility seam), `exportable_summary_only`
- `redaction_status`

Invariants:
- Hidden chain-of-thought or provider-private reasoning must not be exported unless the provider explicitly returns exportable content and policy allows it.
- V1 **hard filter**: every `redacted_thinking` block and every `thinking` block with a non-empty `signature` is filtered from export, regardless of admin opt-in. The schema engine runs `signed_reasoning_filter` as a non-skippable validator.
- Provider-specific structure should be preserved alongside normalized content when available.
- Same-provider, same-model replay passes `thinking` / `redacted_thinking` blocks through verbatim (required to keep Anthropic's tool-use loop valid). Cross-provider model swap drops `reasoning_details` with a warning (V1; lossy re-translation is V1.1+).

### ToolDefinition

Purpose: tool catalog item available to an agent step.

Required fields:
- `tool_id`
- `workspace_id`
- `name`
- `description`
- `input_schema`
- `provider_format`
- `version`
- `source`: `captured`, `adapter_declared`, `user_modified`
- `execution_policy`: `mock`, `ai_mock`, `block`
- `side_effect_class`: `unknown`, `read_only`, `idempotent_write`, `compensatable_write`, `irreversible_write`
- `schema_strictness`: `strict` | `loose` — derived from the source tool's declared strict flag (e.g., OpenAI `strict: true` ⇒ `strict`).

Optional fields:
- `output_schema`
- `examples`
- `mock_definition_id`
- `capability_notes`

Invariants:
- V1 never executes live tools.
- Unknown side effects default to `block` unless a mock or forced result exists.

### ToolCall

Purpose: requested invocation of a tool.

Required fields:
- `tool_call_id`
- `step_id`
- `tool_name`
- `arguments`
- `argument_validation_status`: `valid`, `invalid`, `unknown`
- `decision_source`: `llm`, `forced_by_user`, `fixed_from_parent`
- `status`: `requested`, `resolved`, `blocked`, `failed`

Optional fields:
- `tool_result_id`
- `validation_errors`

### ToolResult

Purpose: output returned to the model for a tool call.

Required fields:
- `tool_result_id`
- `tool_call_id`
- `result_content`
- `result_source`: `original`, `static_mock`, `ai_mock`, `forced_by_user`, `fixed_from_parent`
- `schema_fidelity`: `exact`, `schema_equivalent`, `approximate`, `invalid`
- `redaction_status`

Optional fields:
- `error`
- `mock_definition_id`
- `edited_by`

### MockDefinition

Purpose: reusable mocked behavior for a tool.

Required fields:
- `mock_definition_id`
- `workspace_id`
- `tool_id`
- `tool_name`
- `name` (slug; uniqueness-checked per `(workspace_id, tool_name)` — collisions get numeric suffix)
- `kind`: `input_matcher`, `output_template`, `ai_generated`
- `approval_state`: `draft`, `approved`, `rejected`, `disabled`
- `approved_by`: nullable
- `approved_at`: nullable
- `approved_for_branch_id`: nullable — populated when the mock was approved as a per-branch override (F7)
- `matcher_rules`: ordered list of JSONata rules with priorities, evaluated highest-priority first
- `output_template`
- `ai_generation_config`: nullable JSONB — model used, retry index, source-example refs, seed
- `schema_strictness`: `strict`, `loose` — derived from the source `ToolDefinition.schema_strictness`; on strict-mode validation failure after N retries, mock is saved as `draft` requiring manual approval (per F-R2.8).
- `mock_version`: integer; enforced to bump on every content change via Postgres trigger (per C-R2.5).
- `parent_version_id`: nullable
- `validation_report`
- `source_example_refs`: object-store keys (not inline) of original tool I/O captured from the workspace's own traces (per F5 strict isolation).

Invariants:
- AI-generated mocks start as `approval_state='draft'`.
- Workspace may allow auto-approval later, but first launch requires explicit user approval before first use.
- The AI-mock generator never sees examples from other workspaces (F5 strict isolation, enforced via RLS + runtime assertion).
- Any mock content change MUST bump `mock_version` (Postgres trigger enforces).

### InterventionManifest

Purpose: versioned record of what changed at a fork point.

Required fields:
- `intervention_manifest_id`
- `schema_version`
- `parent_trace_id`
- `parent_branch_id`
- `fork_point_step_id`
- `base_frame_id`
- `changes`
- `created_by`
- `created_at`

Supported change types:
- `edit_message`
- `insert_message`
- `delete_message`
- `edit_system_prompt`
- `edit_tool_definition`
- `add_tool_definition`
- `remove_tool_definition`
- `force_tool_call`
- `force_tool_result`
- `swap_model`
- `swap_model_cross_provider` (extends `swap_model`; carries `dropped_fields` enumeration)
- `system_drop_reasoning_details` (system-generated; not user-authored)
- `override_sampling`
- `fix_subagent_from_parent`

Invariants:
- Manifest is append-only once branch execution starts.
- Later edits create a new branch or a new manifest revision before execution.

### Branch

Purpose: forked trajectory.

Required fields:
- `branch_id`
- `workspace_id`
- `root_trace_id`
- `parent_trace_id`
- `parent_branch_id`
- `fork_point_step_id`
- `base_frame_id`: FK to `frames.frame_id` — the frame the branch was forked from.
- `base_frame_content_hash`: denormalized for diagnostic queries and surfacing the fork-raced-a-late-span case.
- `intervention_manifest_id`
- `status`: `draft`, `estimating`, `blocked`, `queued`, `running`, `paused`, `completed`, `failed`, `cancelled`
- `depth`: integer; number of ancestors in the fork chain (source trace = 0; direct fork = 1; fork of fork = 2).
- `fidelity_at_fork`: `exact` | `schema_equivalent` | `approximate` — base frame's badge at fork time, possibly downgraded one level if the fork raced a hash change.
- `fidelity_min_ancestor`: minimum fidelity across all ancestor branches in the chain.
- `failure_attribution`: `platform` | `provider` | `user_config` | `unknown` — set on terminal failure for diagnostics/alerting (no billing implication; there are no refunds). On-call/operator alerting if `unknown` exceeds 5% in a 7d window.
- `model_substitution`: JSONB, nullable — `{original, resolved, dropped_fields, trigger, chose_rolling_alias}` (see PRD §6 Q11 trigger list).
- `provider_envelope`: JSONB, nullable — the actual `provider` envelope sent to the routing backend (for reproducibility; multi-endpoint backends like OpenRouter only).
- `rate_card_version`: FK to `rate_cards.version` — the informational rate card used for the cost *estimate*, locked at branch **queue time** (so the displayed estimate is reproducible).
- `trial_set_id`: FK, nullable.
- `retry_count_override`: integer, nullable — per-branch override of the Temporal activity retry limit. Bounded by `WorkspaceLimits.workflow_step_retries`. Null falls back to the workspace default. **Per-branch override captured on the branch row only — no audit event** (per H-R3.9).
- `owner_id`
- `name`
- `tags`
- `execution_limits`
- `cost_estimate`: range (low, high) — **informational only**, in the rate card's display units. Not metered, not charged.
- `tokens_actual`: JSONB — observed input/cached/output/reasoning token counts (for quota accounting and the informational actual-vs-estimate ratio).
- `auto_cancel_tokens`: nullable; when set, branch auto-cancels at this token consumption (operational guardrail).
- `effect_summary`

Invariants:
- Branches can be forked recursively.
- Branch execution must stop before exceeding hard limits at deterministic boundaries.
- Descendant branches inherit the minimum fidelity across all ancestors.
- Silent provider/model substitutions are not allowed; the substitution dialog records the resolution in the intervention manifest.

### TrialSet

Purpose: repeated executions of the same intervention.

Required fields:
- `trial_set_id`
- `intervention_manifest_hash`
- `root_trace_id`
- `fork_point_step_id`
- `requested_k`
- `completed_k`
- `branch_ids`
- `aggregate_summary`
- `status`: `queued`, `running`, `completed`, `partial`, `failed`, `cancelled`

Aggregate summary fields:
- success count
- failure count
- blocked count
- most common first divergence
- final outcome distribution
- token/cost/latency distribution
- representative branch IDs

### ExportSnapshot

Purpose: immutable exported dataset/test artifact.

Required fields:
- `export_snapshot_id`
- `workspace_id`
- `source_query`
- `source_object_ids`
- `mapping_id`
- `target_dialect`
- `schema_version`
- `redaction_policy_id`
- `row_count`
- `accepted_row_count`
- `rejected_row_count`
- `validation_report`
- `delivery_target`
- `status`: `queued`, `running`, `completed`, `failed`, `expired`

Invariants:
- Export snapshots are immutable.
- Re-running the same saved query creates a new snapshot version.

### TestCase

Purpose: evaluation/regression-test artifact derived from a trace or branch.

Required fields:
- `test_case_id`
- `workspace_id`
- `source_trace_id`
- `source_branch_id`
- `scope`: `final_output`, `selected_steps`, `full_trajectory`
- `input`
- `expected`
- `assertions`
- `target_format`: `generic_json`, `promptfoo`, `inspect`, `braintrust`, `langsmith`
- `metadata`
- `status`: `draft`, `approved`, `exported`, `archived`

### AuditEvent

Purpose: immutable record of security/product-critical actions.

Required fields:
- `audit_event_id`
- `workspace_id`
- `actor_type`: `user`, `api_key`, `system`
- `actor_id`
- `action`
- `object_type`
- `object_id`
- `occurred_at`
- `request_context`
- `result`: `success`, `failure`

Must audit:
- auth changes
- member invite/role changes
- API key create/revoke/use for privileged scopes
- LLM-routing/key config create/update/delete
- trace access for restricted traces
- fork execution
- export creation/download/delivery
- redaction policy changes
- retention/deletion changes

Operational characteristics:
- Audit table partitioned monthly; partitions created 1 month ahead via the optional slim scheduler / cron (Phase-1 deliverable; missing the next month's partition would cause every user action to lose its audit trail).
- Write-once GRANTs at the Postgres role level prevent retroactive edits.
- Retention: **13 months hot** in Postgres, **7 years cold** in immutable object storage (Parquet + JSONL), using the object store's object-lock/retention on the `committed=true/` prefix (operator-configured; e.g., S3 Object Lock / Azure Blob immutability).

### CapabilityContract

Purpose: agent capability declaration used by the fork editor to guide interventions and warn on out-of-capability edits.

Required fields:
- `capability_contract_id`
- `workspace_id`
- `agent_name`
- `agent_role`
- `agent_version`
- `accepted_input_shapes`
- `tool_affordances`
- `max_recommended_task_granularity`
- `known_constraints`
- `valid_instruction_examples`
- `invalid_instruction_examples`
- `source`: `adapter_declared` | `auto_inferred` | `user_overridden`
- `cache_key`: `(workspace_id, agent_name, tool_catalog_hash, system_prompt_hash)` — for auto-inferred contracts.

Invariants:
- Optional with inference (F9). The fork editor proceeds without a declared contract; the UI auto-populates an inferred one from observed tool catalog + system prompt + agent name.
- Auto-inference counts against the `monthly_ai_mock_generations` quota (per F-R2.1).

### RateCard (informational only)

Purpose: an **operator-maintainable model price reference used solely to compute the informational pre-fork cost estimate.** It is **not** a billing ledger, not a meter, and nothing is charged against it. ForkReplay never settles spend; the operator's own LLM-provider invoice is authoritative.

Required fields:
- `rate_card_id`
- `version`: semantic version (e.g., `2026-06-21.1`).
- `effective_from`
- `effective_until`: nullable
- `status`: `draft`, `active`, `retired`
- `model_rates`: list of `ModelRates`.
- `created_at`

Invariants:
- The active rate-card version used for a branch's displayed estimate is recorded on the branch (`rate_card_version`) so the estimate is reproducible. This is provenance for an estimate, not a billing lock.
- The operator edits the rate card to keep estimates roughly accurate; there is no customer-facing pricing-change notice obligation, because there is no billing.

### ModelRates

Purpose: per-model price line in the informational rate card. All rates are denominated in the operator's chosen display currency (e.g., USD per 1k tokens) and feed the cost *estimate* only.

Required fields:
- `model_id` — e.g., `anthropic/claude-opus-4-8-20260301`.
- `provider_slug`
- `prompt_rate` (per 1k tokens)
- `cached_input_rate`
- `cache_write_rate`
- `completion_rate`
- `reasoning_rate` — explicit per-model reasoning rate. When a model has no separate provider-published reasoning rate, this is set equal to `completion_rate` and the UI labels the line "Reasoning (estimated at output rate)."
- `reasoning_estimate_kind`: `per_token` | `flat_per_call` | `bundled_in_output`
- `request_rate`
- `image_rate`
- `surcharges`: JSONB for provider-specific extras.

> **Removed in OSS pivot:** `UsageEvent`, `BYOKUsageEvent`, and `CreditPackGrant` are deleted. They existed only to feed Stripe billing (meter events, credit packs, refunds), which no longer exists. Token observations needed for operational quota accounting and the informational cost estimate are captured in `LimitUsage` below; there is no billing ledger.

### LimitUsage

Purpose: operational token/usage projection for quota accounting and the informational actual-vs-estimate ratio. **Not a billing record.** Token usage is *tracked* for resource visibility and soft-throttle decisioning; nothing is metered or charged.

Required fields:
- `limit_usage_id`
- `workspace_id`
- `branch_id` (nullable for non-branch events, e.g. ai-mock generation)
- `step_ordinal` (nullable)
- `attempt` (nullable)
- `kind`: `fork_execution`, `ai_mock_generation`
- `model_id` (nullable)
- `provider_slug` (nullable)
- `input_tokens` / `cached_input_tokens` / `output_tokens` / `reasoning_tokens` (nullable)
- `estimated_cost`: nullable — informational, computed from the recorded `rate_card_version` for display only.
- `rate_card_version` (nullable)
- `occurred_at`

Invariants:
- LLM token usage is **tracked, not capped by default.** Workspace admins can configure rolling 30-day alert and cutoff thresholds (operational quota, per H6).
- Threshold evaluation window: rolling 30 days.
- Soft-throttle behavior: when the cutoff threshold is hit, branches refuse to start until an admin acks or raises the threshold. The cutoff banner may lag actual usage by one batch of concurrent branches (acceptable).
- This is a projection for operator visibility, not a ledger of record. There is no external reconciliation (no Stripe, no billing).

### TrialSet (extended)

Add fields:
- `estimated_cost_total`: informational only.
- `tokens_actual_total`: JSONB — observed token counts across the trial set.
- `rate_card_version`

Trial-set cancel semantics (per H4): stops not-yet-started branches and aborts in-flight branches at deterministic boundaries. (No refund concept — there is no billing.)

### Session

Purpose: cross-trace grouping by `gen_ai.conversation.id` (or framework-equivalent attribute).

Required fields:
- `(workspace_id, conversation_id)` — composite primary key.
- `is_synthetic`: boolean — true if the trace had no detectable conversation id and we generated `synthetic:<trace_id>` (per C-R2.6).
- `first_seen_at`
- `last_seen_at`
- `trace_count`
- `source_hint`: which attribute the id was extracted from (for debugging).

Invariants:
- Synthetic sessions are size 1 and surfaced as "Single-trace session" in the UI.
- We do NOT infer cross-trace grouping from `service.name`, user-id hashes, or temporal proximity.
- Each trace in a session is independently forkable. Cross-trace step continuation is V1.1+.

### StepBuildability

Purpose: per-step state machine tracking whether a step's frame is buildable. Traces are open-ended at the trace level; buildability is a per-step property.

Required fields:
- `(workspace_id, trace_id, step_ordinal)` — composite primary key.
- `step_id`: adapter-supplied stable ID (`step_<nanoid>`) or null.
- `state`: `awaiting_spans` | `markable_complete` | `idle_timeout_pending` | `buildable` | `built` | `superseded_by_late_span` | `unbuildable`
- `first_span_at`
- `last_span_at`
- `marker_received_at`: nullable.
- `built_at`: nullable.
- `current_frame_id`: FK to `frames.frame_id`.
- `rebuild_count`: integer.
- `invalid_reason`: nullable.

Inactivity-window default: **30s** for passive OTLP without an adapter marker (C1); workspace-admin configurable from 10s to 5min (per C-R2.7). Adapter step-boundary markers (`forkreplay.step.boundary` span name or span-event form) are the fast path and bypass the inactivity window entirely (C2 — required for fork-grade).

### FrameReferences

Purpose: reference-counted GC for content-addressed frames.

Required fields:
- `frame_content_hash`
- `ref_type`: `branch`, `intervention`, `test_case`, `export_snapshot`, `step_current`
- `ref_object_id`
- `workspace_id`
- `created_at`

Invariants:
- Old frames are never garbage-collected while any branch / intervention / test_case / export_snapshot references their content hash.
- When `step.current_frame_id` flips, the `step_current` reference for the old hash is removed.
- GC daily sweep: hashes with zero references AND older than the workspace's retention window are deleted from the object store.
- Workspace deletion deletes all frames in that workspace regardless of references.

### WorkspaceLimits

Purpose: per-workspace configurable limits surfaced via the V1 admin panel. All values admin-overridable; the spec captures starting defaults.

Configurable fields (starting defaults per H7):
- `concurrent_branches`: 5
- `branch_wall_clock_minutes`: 10
- `max_steps_per_branch`: 200
- `max_tool_invocations_per_branch`: 100
- `max_input_tokens_per_branch`: 2,000,000
- `max_output_reasoning_tokens_per_branch`: 500,000
- `branches_per_source_trace`: 50
- `max_branch_depth`: 25 default; operator-configurable per workspace. Hard ceiling 100 to prevent accidental infinite recursion.
- `max_repeated_trial_k`: 10
- `monthly_ai_mock_generations`: 200 default; operator-raisable per workspace (unlimited permitted).
- `ai_mock_scratchpad_size_kb`: 256 default; operator-raisable up to 1024 (per F-R2.4).
- `token_alert_threshold`: nullable — rolling-30-day token-volume alert threshold (operator-configured visibility, not billing).
- `token_cutoff_threshold`: nullable — rolling-30-day token-volume soft-throttle cutoff (branches refuse to start above it).
- `workflow_step_retries`: integer — per-activity Temporal retry max. Operator default; admin-configurable per workspace. Branch-level override via `Branch.retry_count_override` cannot exceed the workspace's `workflow_step_retries`.
- `retention_days`: 90 default.
- `inactivity_window_seconds`: 30 default (10–300 range; C1 + C-R2.7).
- `seats_per_workspace`: operator-defined.
- `auth_policy_enabled_methods`: list of allowed login methods.
- `auth_policy_allowed_domains`: list of allowed email domains (D5 flagged-for-review semantics).
- `auth_policy_require_verified_email`: boolean, default true.
- `controlled_fallback_allowed_providers`: list of provider slugs for multi-endpoint backends (e.g., OpenRouter); empty list ⇒ no fallback even if `allow_fallbacks_toggle = true`. Ignored by single-endpoint backends (direct provider, Ollama).

---

## 3. Framework-Neutral Python Adapter SDK Contract

The adapter SDK is the V1 active-track contract. Passive OTLP traces can be viewed; active adapter traces can be forked.

The first fork-grade target is the **framework-neutral Python adapter contract**, not any specific agent framework. Framework integrations are compatibility layers over this contract. They should prove that ForkReplay can adapt to existing runtimes without becoming opinionated about LangGraph, LangChain, OpenAI Agents SDK, Pydantic AI, AutoGen, CrewAI, or any other framework.

Design rules:
- No ForkReplay concept may require a LangGraph-specific state model, node model, reducer model, or checkpoint API.
- Framework adapters must emit the same canonical trace/frame/message/tool/intervention objects as the generic adapter.
- Framework-specific metadata can be preserved as optional provenance, but product workflows must work without it.
- Product positioning remains framework-agnostic production trace fork/replay.

### SDK Ergonomics

V1 adoption is **explicit-capture core with decorator ergonomics where safe**. The explicit API (`checkpoint()`, `start_conversation()`, `register_tool()`, `capture_tool_call()`, `capture_stream()`, `mark_step_complete()`, etc.) is the load-bearing surface. Decorators (`@capture`, `@step`, `@tool`, `@model_call`) are sugar over the same core, used where the boundary maps cleanly to a Python function call. Documentation must teach the core first and decorators second.

- Explicit APIs remain available for checkpoints, external context, tool catalogs, message snapshots, redaction hints, and other state decorators cannot infer safely.
- Decoration alone does not imply fork readiness.
- The ingest/replay pipeline classifies traces as `fork-grade`, `replay-assisted`, `inspect-only`, or `import-only` based on captured evidence.
- `forkreplay-auto` (one-line `import forkreplay.auto`) is the canonical onboarding path: walks `sys.modules` + `importlib.metadata.distributions()` to detect installed frameworks and calls each adapter's `.instrument()` idempotently.

The product goal is low-friction adoption without creating false confidence about replay fidelity.

### Fork-Grade Capture Requirements

A trace is fork-grade only if the adapter captures:
- full normalized message history at each forkable boundary
- tool catalog at time of call
- tool call IDs, arguments, results, and errors
- model/provider identifier
- sampling config
- system/developer prompts
- external context references such as RAG hits, memory entries, retrieved files, and user/session metadata
- checkpoint fidelity metadata
- agent capability contract
- semantic convention/source version
- redaction policy version applied at capture or ingest

### Adapter API Surface, Product-Level

The SDK must support these concepts, regardless of final function names:
- decorators or equivalent ergonomics for common agent/step/tool/model-call boundaries
- start/end trace
- mark step boundary
- capture LLM request/response
- capture stream finalization
- register tool catalog
- capture tool call/result
- capture external context
- capture checkpoint
- declare capability contract
- declare redaction hints
- flush/export OTLP-compatible telemetry

### Agent Capability Contract

Captured per agent/workflow where available:
- `agent_name`
- `agent_role`
- `agent_version`
- accepted input/message shapes
- available tool affordances
- max recommended task granularity
- known constraints
- examples of valid instructions
- examples of invalid or risky instructions

The UI uses this contract to guide interventions and warn when an edit asks the agent to do something outside its capability.

### User Responsibilities

V1 docs must be explicit that users are responsible for:
- enabling content capture for prompts/tool data they want to replay
- avoiding capture of secrets through redaction policy configuration
- registering tools or wrapping tool calls if the framework does not expose them
- marking state checkpoints or using explicit capture APIs when decorators/framework hooks cannot recover durable replay state
- verifying AI-generated mocks before use

### Framework Support Levels

Every advertised integration must be labeled:
- **Fork-grade:** adapter captures all required state and supports fork execution.
- **Replay-assisted:** enough state to fork many traces, but missing some framework-specific guarantees.
- **Inspect-only:** trace viewing and span/message inspection only.
- **Import-only:** batch import without live SDK support.

V1 ships three fork-grade framework integrations plus the framework-neutral adapter, and six inspect-only integrations.

| Framework | V1 support level | Notes |
|---|---|---|
| Framework-neutral Python adapter | Fork-grade | Reference fork-grade fixture. |
| LangGraph | Fork-grade | Default mode: explicit `checkpoint()` after each node (framework-agnostic, cleaner positioning vs. LangGraph Studio). Opt-in mode: consume LangGraph's checkpointer directly (configuration option, lower implementation friction). |
| OpenAI Agents SDK | Fork-grade | Uses the official `opentelemetry-instrumentation-openai-agents-v2` contrib package. Closer to upstream OTel direction; less attribute-namespace drift risk. |
| Claude Agent SDK | Fork-grade | Uses native `fork_session=True` + session-resume + file-checkpointing + PreToolUse/PostToolUse hooks. Our adapter wraps the official `claude-agent-sdk` Python package with the OpenInference Claude SDK instrumentor + our explicit-capture markers; no fork of Anthropic's SDK. Cut over to Anthropic native OTel within 1 minor release after it hits non-experimental. **Mid-session fork caveat:** Anthropic's `fork_session` only forks from where the original session ended; mid-session fork at step N replays via `get_session_messages()` + edited prompt sequence — document this divergence. |
| LlamaIndex | Inspect-only | OpenInference instrumentation. |
| Pydantic AI | Inspect-only | OpenInference / community OTel. |
| smolagents | Inspect-only | OpenInference / community OTel. |
| Strands Agents | Inspect-only | OpenInference / community OTel. |
| AutoGen | Inspect-only | OpenInference instrumentation. |
| CrewAI | Inspect-only | OpenInference instrumentation. |

### Adapter Acceptance Criteria

- A simple Python agent with two tool calls can produce a fork-grade trace without custom exporter code.
- A trace captured with content disabled is clearly marked inspect-only.
- A missing tool result, missing tool schema, or unrestorable checkpoint produces a specific fork-readiness warning.
- The SDK can run with production redaction enabled before content leaves the application process.
- A Claude Agent SDK trace from a 2-tool script produces a fork-grade trace via `pip install forkreplay-sdk[claude]` and one `instrument()` call, with no other code changes.

### Adapter step-boundary marker schema

Adapters emit step boundaries as a **zero-duration internal-kind OTel span** with name `forkreplay.step.boundary` (or equivalent span-event form). All attributes live in the `forkreplay.*` namespace (per C-R2.1; insulates us from OTel GenAI semconv churn). Required attributes: `forkreplay.marker.type`, `forkreplay.step.ordinal`, `forkreplay.step.id`, `forkreplay.step.kind`, `forkreplay.frame.boundary`, `forkreplay.adapter.name`, `forkreplay.adapter.version`, `forkreplay.capture.mode`, `forkreplay.schema.version`.

---

## 4. Fork Execution Semantics

### Branch State Machine

Allowed states:
- `draft`: intervention is being edited.
- `estimating`: cost/limit estimate in progress.
- `blocked`: required mock/result/config is missing.
- `queued`: ready to execute.
- `running`: executor is producing branch steps.
- `paused`: stopped at deterministic boundary due to missing input, limit, or resumable error.
- `completed`: terminal success.
- `failed`: terminal failure.
- `cancelled`: user/system cancelled before terminal result.

State transitions:
- Draft -> Estimating -> Blocked
- Draft -> Estimating -> Queued -> Running -> Completed
- Running -> Paused -> Queued -> Running
- Running -> Failed
- Draft/Queued/Running/Paused -> Cancelled

### Durable Orchestration

V1 uses **Temporal** (self-hosted) as the durable branch-orchestration layer. The branch lifecycle is a Temporal **workflow**; model dispatch, mock resolution, step persistence, quota checks, and effect-summary generation are Temporal **activities**.
- The workflow orchestrates **every** branch step including the first model call (no first-call bypass). The fork-start latency budget assumes worker/workflow bootstrap is in the critical path. A pre-warmed worker pool (and optionally a workflow started speculatively on fork-editor open, awaiting a "user-confirmed-run" signal) is the latency mitigation.
- The workflow owns branch lifecycle progression, long waits (Temporal timers), pause/resume behavior (signals), cancellation, and repeated-trial fan-out (child workflows).
- The replay-worker activities own replay/business logic: model dispatch, mock resolution, step persistence, quota checks, and effect-summary generation.
- Workflow history must stay compact; frame data is referenced by hash, not embedded. Activities return only `{frame_hash, pointer_id}`, never frame payloads, to keep Temporal history small.
- Activity retry policy: a small bounded retry max (default within `WorkspaceLimits.workflow_step_retries`), initial delay 5s, exponential backoff. User-configurable per branch via `Branch.retry_count_override`.
- Single model call hard cap: 25 minutes (B3); replay-worker enforces a 24-minute HTTP timeout for a safety margin.
- The control-plane Postgres remains the mutable source of truth for branch/product records; ClickHouse and the object store hold replay facts and large artifacts.

### Tool Resolution Order

When a branch reaches a tool call in V1:

1. If the intervention forced a tool result for this call, use that result.
2. Else if an approved mock matches the call, use the mock.
3. Else if an approved ai_mock matches the call, use the ai_mock.
4. Else if the workspace setting allows generating an ai_mock draft at this point, pause and ask user to review/approve it.
5. Else block before the tool result is needed.

The executor must never call the live tool in V1.

### Force Tool Call

Force tool call means:
- Skip the LLM decision for the selected step.
- Insert a synthetic assistant tool-call message.
- Resolve the tool result using forced result, mock, ai_mock, or block.
- Continue downstream model execution from the resulting frame.

### Force Tool Result

Force tool result means:
- Keep the preceding tool call decision, whether original or branch-generated.
- Replace the tool output with user-provided content.
- Mark result source as `forced_by_user`.
- Continue downstream model execution.

### Missing Mock Behavior

Branch execution must preflight downstream tool requirements where possible. If required mocks are missing:
- show tool name, first missing step, expected schema, and original example result if available
- offer generate ai_mock
- offer static mock editor
- offer block branch intentionally

### AI Mock Review

AI-generated mocks are draft artifacts until approved. The review UI must show:
- original tool inputs/outputs used as examples
- generated matching logic
- generated output template
- schema validation result
- preview for the current branch call
- edit/approve/disable controls

### Repeated Trials

V1 supports repeated trials for the same intervention.

Defaults:
- default K: 3
- user-selectable K: 1-10, subject to workspace limits
- each trial creates a branch with the same intervention manifest hash
- trial set aggregates branch outcomes

Repeated trials count against workspace quotas (concurrency, token volume, AI-mock generations) like normal branches.

### Model Dispatch

V1 uses an internal model-provider abstraction with a **pluggable, config-selected execution backend** — **OpenRouter / direct OpenAI/Anthropic / Ollama**:
- The backend and key are an operator default, overridable per workspace. Keys are operator/workspace env/secret values (optionally KEK-wrapped); no Vault.
- **Multi-endpoint backends (OpenRouter):** default provider envelope `provider.allow_fallbacks: false`, `provider.order: [<captured_provider_slug>]`, `provider.require_parameters: true`. Privacy posture (`data_collection`, `zdr`) is workspace-configurable. Controlled fallback opt-in: admins can flip `allow_fallbacks: true` and supply `controlled_fallback_allowed_providers`; fallbacks across the full catalog are forbidden.
- **Single-endpoint backends (direct provider, Ollama):** the provider-envelope knobs are ignored; the call goes straight to the configured endpoint. Ollama keeps all inference on the operator's own infrastructure (air-gap-friendly).
- Validation at fork-init: model available on the configured backend, captured parameters supportable, (for multi-endpoint backends) data-collection/ZDR compatibility, informational rate-card version recorded at queue time. Failure surfaces the substitution dialog with a per-parameter diff.
- Substitution dialog triggers (per PRD §6 Q11): full unavailability, dated-version supersession, provider mismatch, capability gap, workspace policy elimination. Rolling aliases are allowed by default (per E-R2.3); the user must explicitly accept the substitution.
- Cross-provider model swap drops `reasoning_details` with a warning (V1; option B). Silent re-translation deferred to V1.1+ (option A). Same-provider, same-model fork: pass `thinking` / `redacted_thinking` blocks through verbatim; interleaved-thinking beta header propagated via `extra_body.anthropic_beta` when used.
- Adding a new direct-provider adapter does not change the branch execution contract.
- Branch metadata must record requested model, resolved model, routing/fallback policy, execution backend, usage, and the informational cost estimate where available.
- Silent provider/model substitutions are not allowed.

### Cancellation Contract

When a user clicks "cancel" on a running branch:
- The in-flight model call is aborted within **3s p95** of the click via `AbortSignal` propagation (Temporal activity cancellation).
- Replay-worker polls `branch.cancel_requested_at` every 1s during long calls; on observed cancel, calls `abortController.abort()`.
- Tokens emitted before abort are still counted in `LimitUsage` for quota accounting (`partial_tokens_consumed = min(observed_chunks, final_usage_from_provider)`). There is no billing implication.
- No meter event exists; the cancel state is persisted durably to the control-plane Postgres for accurate quota accounting.

### Effect Summary

Every completed branch gets an effect summary:
- first divergent step
- first divergent LLM decision
- first divergent tool call/result
- final outcome changed: `yes`, `no`, `unknown`
- structural similarity to original continuation
- token delta
- informational cost-estimate delta
- latency delta
- "no material divergence detected" warning where applicable

Effect summary is not a judge or quality scorer. It describes behavioral difference, not correctness.

---

## 5. Trace-To-Test Spec

Trace-to-test is the primary V1 downstream workflow.

### Test Creation Flow

1. User selects trace or branch.
2. User chooses test scope:
   - final output only
   - selected steps
   - full trajectory
3. ForkReplay proposes assertions.
4. User reviews/edits assertions.
5. User chooses output target.
6. Test case is saved as draft or approved.
7. Test case is exported or sent via webhook/SDK.

### Default Assertion Suggestions

ForkReplay may suggest:
- final status is success
- final output equals/contains/regex matches selected text
- tool call sequence includes selected tools
- tool call arguments match exact/partial schema
- tool result conforms to schema
- no disallowed tool called
- max steps
- max latency
- max token usage
- max estimated cost (informational)
- no branch step errors

Assertions must be user-reviewable before export.

### Generic JSON Test Format

Required fields:
- `schema_version`
- `test_case_id`
- `name`
- `source`: trace/branch/step provenance
- `input`: normalized messages and/or initial task variables
- `expected`: final output and/or expected tool sequence
- `assertions`
- `metadata`

Assertion fields:
- `assertion_id`
- `type`
- `scope`: `final_output`, `step`, `tool_call`, `tool_result`, `trajectory`, `cost_latency`
- `target_path`
- `operator`: `equals`, `contains`, `regex`, `json_schema`, `less_than`, `greater_than`, `sequence_contains`, `not_called`
- `expected_value`
- `severity`: `error`, `warning`

### Target Mappings

V1 GA ships **two bundled target mappings** (hard-coded; the schema engine is V1.1):
- Generic JSON test case
- Promptfoo test case

V1.1 (behind `exporters.v1_1` flag, no preview surface): Inspect `Sample`, Braintrust dataset row, LangSmith example.

If a target cannot represent a ForkReplay assertion exactly, export should include a warning in the validation report and preserve the original assertion in metadata.

### Trace-To-Test Acceptance Criteria

- A successful branch can become a generic JSON test without custom mapping.
- A user can remove brittle exact-match assertions before approving.
- Promptfoo/Inspect/Braintrust/LangSmith exports include provenance metadata.
- Unsupported assertions are reported, not silently dropped.

---

## 6. Schema Configuration Engine

The schema engine is the shared mechanism behind dataset exports and test-case exports.

### Mapping Object

Required fields:
- `mapping_id`
- `name`
- `source_type`: `trajectory`, `preference_pair`, `test_case`
- `target_dialect`
- `target_schema_version`
- `row_selector`
- `field_mappings`
- `validators`
- `redaction_policy_id`
- `version`
- `status`: `draft`, `active`, `archived`

### Mapping Primitives

V1 should support:
- path selection from canonical objects
- constants
- renames
- list projection
- conditional inclusion
- join/concat for text fields
- role filtering
- message window selection
- branch/original pairing
- provenance injection
- metadata injection
- split assignment

V1 should not require arbitrary user code in mappings.

### Validation

Every export job runs:
- canonical source validation
- target schema validation
- row-level redaction validation
- provider/dialect compatibility validation
- accepted/rejected row report

Rejected rows must include:
- source object ID
- reason code
- human-readable reason
- suggested remediation where available

### Built-In Mappings

**V1 GA (hard-coded; the schema configuration engine ships in V1.1):**
- Generic trajectory JSONL
- Generic JSON test case
- Promptfoo

**V1.1 (behind `exporters.v1_1` feature flag; no preview surface in V1):**
- OpenAI-compatible SFT JSONL
- TRL/HuggingFace SFT
- OpenAI/Together preference JSONL
- TRL DPO
- HuggingFace dataset package
- Inspect
- Braintrust
- LangSmith

At V1.1, the three V1 exporters become editable copies on top of the engine.

### Schema Engine Acceptance Criteria

- Built-in mappings are editable copies, not hard-coded special paths.
- A user can preview the first N rows before export.
- Export snapshots record mapping version.
- Validation report is downloadable with the export.

---

## 7. Product UX Flows

### Workspace Onboarding

Required steps:
- create workspace
- choose login method
- create ingest API key
- install Python adapter
- run a sample agent
- verify first trace appears

Acceptance:
- empty state explains active vs passive capture
- onboarding shows whether first trace is fork-grade

### Trace Detail

Required views:
- trace summary
- step DAG
- message timeline
- span tree fallback
- step inspector
- fork readiness panel

Acceptance:
- user can tell why a trace is not fork-grade
- user can open raw span details for debugging instrumentation

### Fork Editor

Required controls:
- fork point summary
- checkpoint fidelity warning
- guided intervention templates
- raw message editor
- tool catalog editor
- force tool call/result editor
- model/sampling override
- preflight panel for missing mocks/limits/cost

Acceptance:
- user cannot accidentally run a branch with unresolved blocked tools
- intervention manifest preview is visible before run

### Branch Run

Required states:
- queued
- running
- waiting/paused
- completed
- failed
- cancelled

Acceptance:
- progress shows current step and next expected tool/model call
- failures indicate whether branch can resume

### Compare Branch

Required views:
- original vs branch timeline
- first divergence marker
- step diff
- tool call/result diff
- final outcome summary
- token/cost/latency delta

Acceptance:
- user can answer whether their edit materially changed the trajectory

### Repeated Trials

Required views:
- trial setup with K and cost estimate
- aggregate outcomes
- representative branches
- variance summary

Acceptance:
- user can compare intervention stability without opening every branch

### Convert To Test

Required views:
- source scope picker
- assertion proposal/review
- target format picker
- export preview

Acceptance:
- test can remain draft until reviewed
- brittle assertions are obvious and removable

### Dataset Export

Required views:
- saved query builder or label filter
- mapping picker/editor
- preview rows
- validation report
- delivery target

Acceptance:
- export never silently drops invalid rows
- every row has provenance

---

## 8. Security, Auth, and Data Governance

### Auth Baseline

V1 bundles **GoTrue** (Supabase Auth OSS) as the auth provider in **all** DB modes:
- email/password registration (confirmations sent via the pluggable SMTP transport — Resend / SMTP / console)
- federated login using GoTrue-supported OAuth/OIDC providers
- workspace membership and the full mutable product/control plane stored in the control-plane Postgres selected by `DB_MODE`

**Deployment-mode-agnostic JWT validation:** the app validates GoTrue-issued JWTs the same way in every `DB_MODE`. GoTrue's JWT signing config (secret or JWKS) is supplied to all services; there is no Supabase-Auth-hosted-specific code path. In `DB_MODE=supabase` GoTrue is the Supabase-managed Auth service; in `custom`/`compose` GoTrue runs as a bundled container against the operator's Postgres.

V1.1+:
- enterprise SSO/provisioning with SAML/SCIM

Auth notes:
- GoTrue supports password auth, social/OAuth/OIDC providers, and magic links/OTP.
- Social provider tokens are sensitive and are not stored by default; ForkReplay does not rely on provider tokens for product access.
- Authorization is ForkReplay workspace/role based; do not use user-editable metadata for authorization decisions.

### Workspace Authorization

Every product API must enforce:
- authenticated user or valid API key
- workspace membership or API key workspace scope
- role permission for action
- per-trace ACL if trace is restricted

Tenant isolation is **defense-in-depth, automated test-enforced** (per A8). Required layers:
- Workspace scoping on every query.
- Native Postgres RLS policies on every tenant-scoped table.
- ClickHouse row policies via the `workspace_id` column on every queryable table.
- Object-store key-prefix isolation (`<workspace_id>/...`) on the S3-compatible bucket.
- A tenant-isolation conformance test in CI that fails the build if any policy is missing or misconfigured.

Native Postgres RLS and ClickHouse row policies are **required for V1 launch**, not optional. Cross-workspace data leak is a P0 incident.

### Redaction

V1 redaction rules:
- applied at ingest before user-visible storage
- irreversible for V1
- versioned
- auditable
- visible in export provenance

Rule types:
- regex
- structured key/path match
- built-in secret patterns
- allow/drop fields for messages, tool args, tool results, metadata

### Retention and Deletion

Defaults:
- trace retention: 90 days (workspace-configurable).
- export signed URLs expire after 30 days.
- audit events retained **13 months hot** in Postgres (monthly partitions, write-once GRANTs), then **7 years cold** in the S3-compatible object store (Parquet + JSONL) with object-lock / WORM retention on the `committed=true/` prefix (AWS S3 Object Lock, MinIO retention, or the provider equivalent).

Deletion behavior:
- deleting a trace deletes branches, frames (subject to `FrameReferences` GC), messages, mocks scoped only to that trace, exports if configured, and test drafts if configured.
- audit events remain with object IDs and tombstone status.

RPO / RTO (operator-determined by your backup configuration; the targets below are recommended defaults):
- Control plane (Postgres): RPO ~24h with daily backups. Lower it with more frequent backups or PITR where the chosen `DB_MODE` backend supports it (managed RDS / Azure Database for PostgreSQL / Supabase Pro all offer PITR). Recommended RTO 4h.
- Trace plane (ClickHouse): RPO 24h / RTO 8h via daily ClickHouse backups.
- Cross-region replication is the operator's responsibility and out of scope for the bundled quickstart.

### Export Governance

Every export requires:
- permission check
- redaction policy version
- destination validation
- validation report
- audit event

Restricted traces require explicit confirmation before export.

### BYOK Secrets

BYOK provider credentials:
- workspace-admin only.
- V1 scope is a single workspace-scoped API key for the configured `LLM_PROVIDER` (OpenRouter by default; direct OpenAI / Anthropic / Ollama are the other supported providers). One key per workspace.
- **Envelope-encrypted at rest with an optional Key-Encryption-Key (`KEK_PROVIDER`: `none` | `age` | `libsodium`).** When a KEK is configured, ordinary product tables store only the wrapped ciphertext, references, and status metadata — never plaintext. When `KEK_PROVIDER=none`, the key is protected by whatever at-rest encryption the operator's database/secret store provides (acceptable for a single-operator self-host).
- The KEK identity (e.g. the age identity file, `KEK_AGE_IDENTITY_FILE`) is operator-held and supplied to the replay-worker out of band; it is never committed and never stored in the product tables it protects.
- The decrypted key lives in process memory only for the duration of one branch step's outbound HTTP call to the provider, then is overwritten before the variable goes out of scope.
- Never logged. A `Bearer **redacted**` log filter is mandatory; a CI logged-secret canary test enforces it (covering BYOK plaintext, GoTrue/service JWTs, and the operator's default LLM key).
- Can be disabled without deleting saved config.
- Changes are audit logged.
- **No Vault dependency.** Earlier drafts used Supabase Vault plus a dedicated `replay_worker_byok` Postgres role + `SECURITY DEFINER` accessor; the OSS build replaces both with the pluggable KEK above so BYOK behaves identically across all `DB_MODE` backends. Least-privilege intent is preserved — only the replay-worker process holds the KEK identity needed to unwrap keys.

---

## 9. Operational Limits

All operational limits live in the `WorkspaceLimits` canonical object (§2 above). Every value is operator-configurable per workspace via the V1 admin panel; the numbers below are starting defaults. These are **resource guardrails** (concurrency, depth, wall-clock, token volume, retention) — **not billing or metering.** There are no commercial tiers; an operator who wants to bill their users brings their own billing layer (see root `AGENTS.md`).

Starting defaults (per H7):
- `concurrent_branches`: 5
- `branch_wall_clock_minutes`: 10
- `max_steps_per_branch`: 200
- `max_tool_invocations_per_branch`: 100
- `max_input_tokens_per_branch`: 2,000,000
- `max_output_reasoning_tokens_per_branch`: 500,000
- `branches_per_source_trace`: 50
- `max_branch_depth`: 25 default; operator-configurable per workspace. Hard ceiling 100 to prevent accidental infinite recursion.
- `max_repeated_trial_k`: 10
- `monthly_ai_mock_generations`: 200 default; operator-raisable per workspace (unlimited permitted).
- `ai_mock_scratchpad_size_kb`: 256 default; operator-raisable up to 1024 (per F-R2.4).
- `token_alert_threshold`: nullable — rolling-30-day token-volume alert threshold (operational visibility).
- `token_cutoff_threshold`: nullable — rolling-30-day token-volume soft-throttle cutoff (branches refuse to start above it).
- `workflow_step_retries`: per-activity Temporal retry max; operator default, admin-configurable per workspace.
- `retention_days`: 90.
- `inactivity_window_seconds`: 30 default, 10–300 admin-configurable (C1 + C-R2.7).
- `seats_per_workspace`: operator-defined.

### Cost-Estimate Accuracy (informational)

The pre-fork cost figure is an **informational estimate**, not a charge (see `RateCard` / `LimitUsage` in §2). Nothing is metered or billed.
- Target accuracy: **±20%** (H12). Tracked via `cost_estimate.actual_vs_estimate_ratio` histogram.
- Editor display: cost shown as a **low–high range in the rate card's display currency** (e.g. "$0.10–$0.15"), alongside the operational hard token cap (`Branch.auto_cancel_tokens`) — not a single number.
- Reasoning cost shown as a separate line item; sub-totals (reasoning + output) and grand total (input + output + reasoning).

### BYOK Fair Use

Per H6: **BYOK token usage is tracked but not hard-capped by default.** Admins configure rolling-30-day alert and cutoff thresholds (`token_alert_threshold` / `token_cutoff_threshold`). The operational product limits still apply:
- concurrency
- wall-clock time
- branch depth
- token volume
- tool invocations
- stored artifacts
- AI-mock generation
- export jobs

---

## 10. Product Event Metrics

Every success metric should map to product events.

### Core Events

Lifecycle:
- `workspace.created`
- `member.invited`
- `auth.signup_completed`
- `api_key.created`
- `api_key.scope_denied`
- `sdk.installed_sample_completed`

Ingest / step-buildability:
- `trace.ingested`
- `trace.ready`
- `trace.opened`
- `trace.fork_readiness_viewed`
- `step.buildable`
- `step.built`
- `step.unbuildable`
- `frame.rebuilt_idempotent` (low priority)
- `frame.hash_changed`
- `frame.size_warning`
- `frame.size_exceeded`
- `marker.malformed`
- `session.created`
- `stitch.ambiguous_late_span`

Fork / branch lifecycle:
- `fork_editor.opened`
- `intervention_manifest.created`
- `branch.estimated`
- `branch.blocked`
- `branch.queued`
- `branch.started`
- `branch.completed`
- `branch.failed`
- `branch.cancelled`
- `branch.compared`
- `branch.auto_cancelled_at_hard_cap`
- `effect_summary.viewed`
- `workflow.dead_letter`

Trial sets / tests / exports:
- `trial_set.created`
- `trial_set.completed`
- `test_case.created`
- `test_case.exported`
- `dataset_export.created`
- `dataset_export.completed`

Mocks (audit-row events; **note: `mock.matched` is a Grafana metric counter, not an audit row**, per F-S5):
- `mock.matcher_no_match` (warn; triggers branch pause)
- `mock.template_render_failed` (error)
- `mock.schema_mismatch` (error)
- `mock.scratchpad_overflow` (error)
- `mock.ai_generation_started`
- `mock.ai_generation_completed`
- `mock.ai_generation_failed`
- `mock.gen_contract_truncated` (warn; capability-contract tool-list truncated to source + 5 related per F-R3.5)
- `mock.approval_required`
- `mock.approval_granted`
- `mock.approval_denied`
- `mock.disabled`
- `mock.branch_override_granted`
- `mock.capability_contract_inferred`
- `mock.capability_contract_overridden`

Provider / reasoning:
- `reasoning.redacted_passthrough` (info)
- `reasoning.redacted_blocked_in_export` (warn)
- `provider.fallback_triggered`
- `provider.response_schema_drift`
- `model.substitution_required`
- `model.substitution_chosen`
- `byok.provider_type_rejected`
- `prompt_cache.first_turn_busted`
- `rate_card.reasoning_inferred` (warn; unknown-model reasoning rate inferred from output-rate parity per E-R3.3)

Platform / ops:
- `scheduler.maintenance_completed` (info; heartbeat emitted once per optional `services/scheduler` partition/retention run)

Quota / BYOK (operational — no billing):
- `byok.configured`
- `byok.alert_threshold_hit`
- `byok.cutoff_activated`
- `byok.cutoff_reset`
- `workspace_limits.changed`

### Metric Definitions

Active workspace:
- workspace with at least one `trace.opened` or `branch.started` in the last 7 days.

Fork executed:
- `branch.started`, excluding branches that never leave queued/blocked.

Fork compared:
- `branch.compared` or `effect_summary.viewed` within 24 hours of branch completion.

Repeated trial used:
- `trial_set.created` with requested K greater than 1.

Trace-to-test workflow in CI:
- test case exported via webhook/SDK target at least twice in a 30-day period, or external status callback received.

Dataset export feeding training:
- export target/dialect marked SFT/preference/DPO and customer marks destination as training/fine-tuning.

---

## 11. Resolved Planning Decisions

These decisions are settled for implementation planning. They reflect the **OSS self-hostable** architecture (v0.5 pivot). Numbering is preserved from earlier drafts for traceability; where a decision supersedes a managed-SaaS choice, the prior choice is noted, and billing-era items now read **Removed in OSS pivot** (superseded by decision 4).

1. **Framework adapter scope:** V1 ships **three fork-grade framework adapters** — LangGraph, OpenAI Agents SDK, Claude Agent SDK — plus the framework-neutral Python adapter. Six inspect-only frameworks via OpenInference passive OTel mapping: LlamaIndex, Pydantic AI, smolagents, Strands Agents, AutoGen, CrewAI.
2. **SDK ergonomics:** V1 is **explicit-capture core with decorator ergonomics where safe**. `forkreplay-auto` (one-line `import forkreplay.auto`) is the canonical onboarding path; ships in V1. **Python-only SDK in V1** (no TypeScript SDK).
3. **Exporters:** V1 GA ships **3 hard-coded exporters** (generic trajectory JSONL, generic JSON test case, Promptfoo) on a thin internal mapping interface. The schema configuration engine and the additional 8 dialects ship in V1.1 (behind `exporters.v1_1`, no preview surface in V1).
4. **Billing — Removed in OSS pivot.** No Stripe, no replay credits, no meter events, no reconciliation, no refund batch, no credit packs. The pre-fork cost figure is an **informational estimate only** (`RateCard` / `LimitUsage`, §2); nothing is metered or charged. An operator who wants to bill their own users brings their own billing layer.
5. **Reasoning-token rate (informational):** Explicit **per-model `reasoning_rate`** in the informational rate card. When a model has no separate provider-published reasoning rate, the line is estimated at the output rate and labeled "Reasoning (estimated at output rate)." Feeds the cost *estimate* only.
6. **Failure attribution (no refunds):** `Branch.failure_attribution` (`platform` | `provider` | `user_config` | `unknown`) is set on terminal failure for diagnostics/alerting only — there are no refunds (no billing). Operator alerting fires if `unknown` exceeds 5% in a 7-day window.
7. **Redaction posture:** V1 stores only redacted content. Raw unredacted content is not retained by ForkReplay in V1.
8. **Web app + streaming:** the Next.js workbench ships as a **standalone container** deployable on any host; **streaming is Redis-backed FastAPI SSE** (Last-Event-ID resume via Redis pub/sub). Supersedes the earlier Vercel-hosted frontend + Cloudflare Workers SSE relay + per-branch Durable Object.
9. **Services:** the FastAPI `api`, `ingest`, `replay-worker`, `mock-gen-worker`, and `export-worker` run as containers on the operator's platform (compose / Kubernetes / cloud). Supersedes the earlier Railway-hosted split.
10. **Durable replay orchestration:** **Temporal** (workflow/activity model) orchestrates every branch step including the first. Supersedes the earlier Cloudflare Workflows decision.
11. **Ingest queue:** **NATS** (primary; Redis Streams alternative via `QUEUE_BACKEND`) between OTLP receive and stitch/redact/write. OTLP ingress is a **FastAPI endpoint**. Supersedes the earlier Cloudflare Queues + Workers gateway.
12. **Control plane:** **pluggable Postgres via `DB_MODE` (`compose` | `custom` | `supabase`)**, with **GoTrue** (Supabase Auth OSS) as the auth provider in all modes. Supersedes the earlier "Supabase Free tier" managed assumption; backup/RPO is now operator-determined by the chosen backend.
13. **Trace/data plane:** **ClickHouse is required in every deployment mode** (bundled OSS container in compose; required component in Helm/Terraform) for trace/replay query projections. Frames, artifacts, audit cold archive, and export bundles live in an **S3-compatible object store** (MinIO / AWS S3 / Azure Blob). Supersedes ClickHouse Cloud + Cloudflare R2.
14. **Frame storage:** S3-compatible, content-addressed, workspace-scoped key prefix (per C6), embedded messages, 5 MB hard cap with 1 MB soft warning, per-item externalization above 256 KB.
15. **Step storage:** Promote-on-demand step rows in Postgres; ClickHouse is the authoritative span/step projection.
16. **Branch event store:** Postgres append-only `branch_event` table partitioned by hash of `branch_id`. Sequence allocation via `SELECT MAX(seq) + 1 ... FOR UPDATE` inside `append_branch_event` (B-R2.5).
17. **Secret storage:** operator/workspace secrets via env/secret manager, with an **optional KEK** (`KEK_PROVIDER`: `none` | `age` | `libsodium`) for envelope-encrypting workspace BYOK keys. **No Vault.** Supersedes the Supabase Vault + `replay_worker_byok` role design.
18. **Model-provider strategy:** internal provider abstraction with **pluggable execution adapters** (`LLM_PROVIDER`: OpenRouter / direct OpenAI / direct Anthropic / Ollama). V1 BYOK means a customer-supplied key for the configured provider. Supersedes the OpenRouter-only design.
19. **Provider envelope defaults:** `provider.allow_fallbacks: false`, `provider.order: [<captured>]`, `provider.require_parameters: true` for multi-endpoint backends (e.g. OpenRouter). Privacy posture is operator/workspace-configurable (e.g. opt into `data_collection: deny` + `zdr: true`). Single-endpoint backends (direct provider, Ollama) ignore the envelope.
20. **Rolling aliases:** Allowed by default per workspace; user must explicitly accept substitution.
21. **Sessions:** Grouped by `gen_ai.conversation.id` (or framework-equivalent attribute); each trace independently forkable. Synthetic sessions named `synthetic:<trace_id>` with `is_synthetic=true`. Cross-trace step continuation is V1.1+.
22. **Adapter step-boundary markers:** `forkreplay.*` attribute namespace (not `gen_ai.*`); insulates us from OTel GenAI semconv churn.
23. **Inactivity window default:** 30s passive-OTLP, workspace-admin configurable 10s–5min. Claude SDK passive ingest **trusts Claude SDK span close as an implicit marker** (per C-R2.2).
24. **Messages search projection:** V1.1 (V1 ships object-store-frame-only reads).
25. **Public API style:** REST + OpenAPI for product APIs; native OTLP ingest (HTTP-protobuf + gRPC) for telemetry lanes.
26. **Observability sink:** **any OTLP-compatible sink** the operator runs (self-hosted OTel Collector + Prometheus/Grafana, or an external endpoint via `OTEL_EXPORTER_OTLP_*`). Optional; leave unset to disable. Supersedes the Grafana Cloud requirement.
27. **CI/CD:** GitHub Actions for the OSS repo (build, test, secret-scan via gitleaks, docs-drift). Deploying a self-hosted instance is the operator's pipeline; the repo ships IaC skeletons (compose / Helm / Terraform) in a later phase. Supersedes the managed-vendor OIDC matrix.
28. **Audit retention:** 13 months hot in Postgres (monthly partitions, write-once GRANTs); 7 years cold in the S3-compatible object store (Parquet + JSONL) with object-lock / WORM retention on the `committed=true/` prefix.
29. **RPO/RTO:** operator-determined by backup configuration. Recommended defaults: control-plane RPO ~24h (daily backups; PITR available on managed/`custom` backends), RTO 4h; trace plane RPO 24h / RTO 8h via ClickHouse daily backups. Cross-region replication is the operator's responsibility.
30. **Tenant isolation:** Defense-in-depth, automated test-enforced. Native Postgres RLS + ClickHouse row policies are required. Multi-tenant core is retained; the documented quickstart default is single-tenant (a default workspace).
31. **Cancellation:** p95 < 3s; propagates via AbortSignal to the provider call.
32. **Admin panel scope (V1):** Locked at 5 surfaces — per-workspace limits, auth-policy, member management, BYOK config, retention/redaction. New surfaces require a PRD edit.
33. **Trust posture:** the project ships **no SLA, no status page, and no third-party pen-test attestation** (an operator may add their own). These remain V1 non-goals.
34. **Backup responsibility (supersedes the Supabase Pro upgrade trigger):** backups, restore drills, and PITR configuration are the operator's responsibility, scoped to the chosen `DB_MODE` backend and ClickHouse deployment.
35. **Tier-free retry policy (supersedes the tier-bound override):** `workflow_step_retries` is a single operator default, admin-configurable per workspace (no commercial tiers). `Branch.retry_count_override` cannot exceed the workspace value.
36. **Removed in OSS pivot:** the credit-pack purchase flow (no billing — see decision 4).
37. **System banners for ops comms (round-3 H-R3.12):** the `system_banners` table is the operational banner mechanism, now **FastAPI/Redis-backed** SSE (not a Cloudflare Workers relay). Admin-edited via the admin panel or the `/v1/internal/banners` endpoint.
38. **Quarterly restore drills (round-3 D-R3.Q1):** a periodic restore drill (recommended quarterly) is the operator's responsibility, paired with the multi-recipient key custody in decision 41 when a KEK is used.
39. **`forkreplay-sdk[auto]` install posture (round-3 §0.1 override):** `[auto]` extra is detection logic only (`forkreplay-auto` core + `importlib.metadata` walker). Users must install per-framework extras (`[langgraph]`, `[claude]`, `[openai-agents]`) explicitly for each framework they want auto-instrumented. The `[all]` extra remains as a convenience meta-package with compatibility-range pins (per G-R3.4) but ships with a production warning.
40. **SDK env-var contract (round-3 §0.3 + D-R3.Q7 + G-R3.1 + G-R3.7):** `FORKREPLAY_AUTO_INSTRUMENT=1` (opt-in `.pth` bootstrap; no-op when unset), `FORKREPLAY_AUTO_SAMPLE=0.1` (probabilistic drop at the SDK before the OTLP endpoint), `FORKREPLAY_AUTO_DISABLE=1` (hard kill-switch), `FORKREPLAY_VERBOSE=1` (INFO-level logs from the auto-instrument path; silent default).
41. **Backup key custody (round-3 §0.4):** when a KEK is used, age multi-recipient encryption (operator + 1 recovery recipient) eliminates bus-factor-1. The recovery recipient never operates the key under normal ops; it exists only as a recovery path. Annual rotation (per B-R3.6).
42. **Removed in OSS pivot:** the refund batch cadence (no billing — see decision 4).
43. **Removed in OSS pivot:** `retry_amplification_factor` — it scaled refund estimates and has no purpose without billing (see decision 4).
44. **Removed in OSS pivot:** reconciliation mismatch alarms (no billing reconciliation — see decision 4).

With these decisions resolved, the product docs are ready to support a concrete implementation plan.

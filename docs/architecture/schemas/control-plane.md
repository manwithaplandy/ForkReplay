# Control-Plane Postgres — Schema Sketches

> **Status: design sketch.** This is the direct input to the **Phase 1 schema lock**
> (the migrations live there, not here). Column lists are *sketch-level* — enough to
> pin shape, keys, and tenant-isolation intent — not final DDL. Names are grounded in the
> canonical object model in [`implementation-readiness-spec.md`](../../../implementation-readiness-spec.md) §2.
>
> **Scope.** The control plane is the **pluggable Postgres** store selected by
> [`DB_MODE`](../db-mode-matrix.md). It holds workspaces, identity, branch/trace
> metadata, the tool/mock catalog, governance, and the audit trail. The columnar
> span/frame analytics live in **ClickHouse** (see
> [`clickhouse.md`](./clickhouse.md)), which is **required in every mode** — it is not
> Postgres-substitutable.

---

## Tenant-isolation model (applies to every tenant-scoped table)

Tenant isolation is **defense-in-depth, CI-enforced** (readiness spec §8). The
control-plane layer of that defense is **native Postgres Row-Level Security (RLS)**:

- **Tenant key.** Every tenant-scoped table carries a `workspace_id UUID NOT NULL`
  column. `workspaces` is the tenant root; everything else fans out from it.
- **RLS policy intent.** Each tenant-scoped table has RLS **enabled and forced**, with a
  policy whose `USING` / `WITH CHECK` predicate restricts rows to the caller's workspace.
  The request's workspace is bound per-transaction from the validated GoTrue JWT, e.g.:

  ```sql
  ALTER TABLE <table> ENABLE ROW LEVEL SECURITY;
  ALTER TABLE <table> FORCE ROW LEVEL SECURITY;

  CREATE POLICY tenant_isolation ON <table>
    USING       (workspace_id = current_setting('app.workspace_id')::uuid)
    WITH CHECK  (workspace_id = current_setting('app.workspace_id')::uuid);
  ```

- **Conformance gate.** A CI tenant-isolation conformance test fails the build if any
  tenant-scoped table is missing RLS or its `workspace_id` policy. Cross-workspace leak
  is a P0. The same gate is mirrored in ClickHouse via **row policies on `workspace_id`**.
- **Required for V1 launch**, not optional, and identical across all three `DB_MODE`
  values. The documented quickstart is single-tenant (one default workspace) but the
  multi-tenant policies are always present.

The **RLS tenant-isolation note** on each table below states which column scopes the
tenant (always `workspace_id`) and the policy intent. Tables that are not tenant-scoped
(the tenant root and global operator tables) are called out explicitly.

Required Postgres extensions for these sketches: `pgcrypto`, `uuid-ossp` (and `pg_cron`
if the optional in-database partition/retention scheduler is used).

---

## Core tables

### `workspaces` — tenant root

- **Purpose.** The tenant boundary. Every other tenant-scoped row references one
  workspace. (Readiness spec §2 `Workspace`.)
- **RLS note.** **Tenant root, not workspace-scoped by `workspace_id`.** RLS restricts a
  member to the workspaces they belong to (join through `members.auth_user_id`), not to a
  single `workspace_id` column. This is the one table whose policy keys off membership.

```sql
CREATE TABLE workspaces (
  workspace_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name                TEXT NOT NULL,
  slug                TEXT NOT NULL UNIQUE,
  limits_id           UUID REFERENCES workspace_limits(limits_id),
  retention_policy_id UUID,
  redaction_policy_id UUID,
  llm_routing_status  TEXT,            -- e.g. unconfigured | configured
  auth_policy         JSONB,           -- enabled methods, allowed domains, verified-email
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### `members` — workspace membership

- **Purpose.** A user's membership and role in a workspace; maps GoTrue identities to
  workspace access. (Readiness spec §2 `Member`.)
- **RLS note.** **Tenant-scoped on `workspace_id`.** Policy: a row is visible/writable
  only when `workspace_id` matches the caller's workspace; role changes are audited.

```sql
CREATE TABLE members (
  member_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id  UUID NOT NULL REFERENCES workspaces(workspace_id),
  auth_user_id  UUID NOT NULL,                 -- GoTrue user id
  email         TEXT NOT NULL,
  role          TEXT NOT NULL,                 -- admin | editor | viewer
  status        TEXT NOT NULL DEFAULT 'invited',-- invited | active | disabled | removed
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (workspace_id, auth_user_id)
);
```

### `api_keys` — programmatic / SDK access

- **Purpose.** SDK ingest and programmatic access keys with verb-on-resource scopes.
  (Readiness spec §2 `ApiKey`.)
- **RLS note.** **Tenant-scoped on `workspace_id`.** Create/revoke/use of privileged
  scopes is audited. The secret is stored as a hash, never plaintext.

```sql
CREATE TABLE api_keys (
  api_key_id    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id  UUID NOT NULL REFERENCES workspaces(workspace_id),
  name          TEXT NOT NULL,
  key_hash      TEXT NOT NULL,                 -- hashed secret, never plaintext
  scopes        TEXT[] NOT NULL,               -- e.g. traces:write, branches:read, workspace:admin
  status        TEXT NOT NULL DEFAULT 'active',-- active | revoked | expired
  created_by    UUID,
  last_used_at  TIMESTAMPTZ,
  expires_at    TIMESTAMPTZ,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### `traces` — captured executions

- **Purpose.** Immutable captured agent execution metadata. The span/frame analytics
  projection lives in ClickHouse; this is the control-plane index. (Readiness spec §2
  `Trace`.)
- **RLS note.** **Tenant-scoped on `workspace_id`.** Access to `restricted` traces is
  additionally audited.

```sql
CREATE TABLE traces (
  trace_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id     UUID NOT NULL REFERENCES workspaces(workspace_id),
  source_trace_id  TEXT,
  source           TEXT NOT NULL,    -- otlp_http | otlp_grpc | adapter | file_import
  capture_mode     TEXT NOT NULL,    -- passive | active
  service_name     TEXT,
  environment      TEXT,
  session_id       TEXT,
  root_span_id     TEXT,
  status           TEXT NOT NULL,    -- ingesting | ready | failed | expired | deleted
  content_capture  TEXT,             -- none | metadata_only | messages | messages_and_tools
  semconv_source   TEXT,             -- otel_genai | openinference | framework | custom
  privacy_classification TEXT,       -- normal | sensitive | restricted
  started_at       TIMESTAMPTZ,
  ended_at         TIMESTAMPTZ,
  expires_at       TIMESTAMPTZ,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### `branches` — forked trajectories

- **Purpose.** A forked trajectory rooted at a trace fork point, executed via Temporal.
  Forks can recurse; descendants inherit the minimum fidelity across ancestors.
  (Readiness spec §2 `Branch`.)
- **RLS note.** **Tenant-scoped on `workspace_id`.** Fork execution is audited.
  `cost_estimate` is **informational only** — there is no metering or charge.

```sql
CREATE TABLE branches (
  branch_id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id              UUID NOT NULL REFERENCES workspaces(workspace_id),
  root_trace_id             UUID REFERENCES traces(trace_id),
  parent_trace_id           UUID REFERENCES traces(trace_id),
  parent_branch_id          UUID REFERENCES branches(branch_id),
  fork_point_step_id        UUID,
  base_frame_id             UUID,            -- FK to frames(frame_id)
  base_frame_content_hash   TEXT,            -- denormalized content hash
  intervention_manifest_id  UUID REFERENCES intervention_manifests(intervention_manifest_id),
  status                    TEXT NOT NULL,   -- draft|estimating|blocked|queued|running|paused|completed|failed|cancelled
  depth                     INTEGER NOT NULL DEFAULT 0,
  fidelity_at_fork          TEXT,            -- exact | schema_equivalent | approximate
  fidelity_min_ancestor     TEXT,
  failure_attribution       TEXT,            -- platform | provider | user_config | unknown
  owner_id                  UUID,
  name                      TEXT,
  cost_estimate             JSONB,           -- informational range (low/high); not metered, not charged
  tokens_actual             JSONB,           -- operational token observation; not a billing record
  created_at                TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### `byok_config` — workspace LLM routing / bring-your-own-key

- **Purpose.** Per-workspace LLM routing configuration and the custody record for a
  workspace's own provider key (BYOK). Maps to the readiness-spec LLM-routing/key config
  whose create/update/delete is audited (§2 audit list). Secret key material is
  envelope-encrypted at rest when an optional KEK is configured (`KEK_PROVIDER=age|libsodium`);
  it is **never** stored or committed in plaintext.
- **RLS note.** **Tenant-scoped on `workspace_id`.** This is the most sensitive
  tenant-scoped table; RLS plus envelope encryption are both required, and every mutation
  is audited.

```sql
CREATE TABLE byok_config (
  byok_config_id    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id      UUID NOT NULL REFERENCES workspaces(workspace_id),
  provider_slug     TEXT NOT NULL,         -- openrouter | openai | anthropic | ollama
  api_base          TEXT,                  -- optional base-URL override (e.g. local Ollama)
  key_ciphertext    BYTEA,                 -- envelope-encrypted under the KEK; NULL for keyless local
  kek_provider      TEXT,                  -- none | age | libsodium (custody mode used)
  status            TEXT NOT NULL DEFAULT 'active',
  created_by        UUID,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

> Key custody uses the optional KEK (`age` / `libsodium`); there is **no Vault
> dependency** (this replaced the earlier external-vault design). See
> [`configuration.md`](../../deployment/configuration.md#byok-key-custody--optional-kek-kek_provider).

### `workspace_limits` — operational guardrails

- **Purpose.** Per-workspace **operational quotas** — concurrency, branch depth,
  wall-clock, token volume, retention, AI-mock generation budget, inactivity window.
  (Readiness spec §2 / §9 `WorkspaceLimits`.) These are **resource guardrails, not
  billing or metering**.
- **RLS note.** Referenced by `workspaces.limits_id`. Treat as **tenant-scoped**: a
  workspace reads/writes only its own limits row; operator-set hard ceilings are enforced
  server-side.

```sql
CREATE TABLE workspace_limits (
  limits_id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id                       UUID REFERENCES workspaces(workspace_id),
  concurrent_branches                INTEGER NOT NULL DEFAULT 5,
  branch_wall_clock_minutes          INTEGER NOT NULL DEFAULT 10,
  max_steps_per_branch               INTEGER NOT NULL DEFAULT 200,
  max_tool_invocations_per_branch    INTEGER NOT NULL DEFAULT 100,
  max_input_tokens_per_branch        BIGINT  NOT NULL DEFAULT 2000000,
  max_output_reasoning_tokens_per_branch BIGINT NOT NULL DEFAULT 500000,
  branches_per_source_trace          INTEGER NOT NULL DEFAULT 50,
  max_branch_depth                   INTEGER NOT NULL DEFAULT 25,   -- hard ceiling 100
  max_repeated_trial_k               INTEGER NOT NULL DEFAULT 10,
  monthly_ai_mock_generations        INTEGER NOT NULL DEFAULT 200,
  retention_days                     INTEGER NOT NULL DEFAULT 90,
  inactivity_window_seconds          INTEGER NOT NULL DEFAULT 30,   -- 10–300 range
  token_alert_threshold              BIGINT,
  token_cutoff_threshold             BIGINT,
  created_at                         TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### `system_banners` — operator broadcast notices

- **Purpose.** Operator/admin broadcast banners surfaced in the workbench and pushed to
  clients over Redis-backed SSE (architecture doc: "branch progress + system banners").
  Used for maintenance windows, degraded-provider notices, and announcements.
- **RLS note.** A banner may be **global** (`workspace_id IS NULL`, operator-only write,
  readable by all workspaces) or **workspace-scoped** (`workspace_id` set, tenant-isolated
  like every other table). The RLS policy admits a row when
  `workspace_id IS NULL OR workspace_id = current_setting('app.workspace_id')::uuid`;
  only operators may insert global banners.

```sql
CREATE TABLE system_banners (
  banner_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id  UUID REFERENCES workspaces(workspace_id),  -- NULL = global/operator banner
  level         TEXT NOT NULL DEFAULT 'info',  -- info | warning | critical
  message       TEXT NOT NULL,
  active        BOOLEAN NOT NULL DEFAULT true,
  starts_at     TIMESTAMPTZ,
  ends_at       TIMESTAMPTZ,
  created_by    UUID,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### `audit_log` — immutable audit trail

- **Purpose.** Immutable, append-only record of security/product-critical actions —
  auth/role changes, API-key create/revoke, LLM-routing/`byok_config` changes, restricted
  trace access, fork execution, export creation/download, redaction/retention changes.
  (Readiness spec §2 `AuditEvent`.)
- **RLS note.** **Tenant-scoped on `workspace_id`** for reads; **write-once** at the
  Postgres role level (GRANT INSERT only; no UPDATE/DELETE GRANT) so the trail cannot be
  retroactively edited.
- **Operational characteristics.** Partitioned **monthly** by `occurred_at`; the next
  month's partition is created ahead of time by the optional slim scheduler / `pg_cron`.
  Retention: **13 months hot** in Postgres, then **7 years cold** in the S3-compatible
  object store (Parquet + JSONL) with object-lock / WORM retention on the `committed=true/`
  prefix.

```sql
CREATE TABLE audit_log (
  audit_event_id  UUID NOT NULL DEFAULT gen_random_uuid(),
  workspace_id    UUID NOT NULL REFERENCES workspaces(workspace_id),
  actor_type      TEXT NOT NULL,   -- user | api_key | system
  actor_id        TEXT,
  action          TEXT NOT NULL,
  object_type     TEXT NOT NULL,
  object_id       TEXT,
  result          TEXT NOT NULL,   -- success | failure
  request_context JSONB,
  occurred_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (audit_event_id, occurred_at)
) PARTITION BY RANGE (occurred_at);
-- Monthly partitions, e.g. audit_log_2026_06; write-once role GRANTs (INSERT only).
```

---

## Supporting tables (catalog, content index, governance)

These round out the object model so the Phase 1 lock has the full control-plane surface.
All are **tenant-scoped on `workspace_id`** with the standard RLS policy unless noted.

| Table | Purpose | Tenant key / RLS note |
|-------|---------|-----------------------|
| `steps` | Logical units of agent work; belong to a trace **or** a branch (XOR). Promote-on-demand rows; ClickHouse is the authoritative span/step projection. | via parent `trace_id`/`branch_id` → `workspace_id` |
| `step_buildability` | Per-step frame-buildability state machine (`awaiting_spans`→`buildable`→`built`…); 30s inactivity default. | `workspace_id` (composite PK with `trace_id`, `step_ordinal`) |
| `frames` | Forkable state at a step boundary; content-addressed (`content_hash`), payload in S3 under `frames/<workspace_id>/...`. Control-plane row indexes the blob; `valid_for_fork` gates fork. | `workspace_id` |
| `frame_references` | Reference-counted GC for content-addressed frames (branch / intervention / test_case / export_snapshot / step_current). | `workspace_id` |
| `messages` | Normalized conversational units (role, content blocks, provider format). Hidden-reasoning export hard-filter applies. | via `source_step_id` → `workspace_id` |
| `tool_definitions` | Per-workspace tool catalog (schema, execution policy mock/ai_mock/block, side-effect class). | `workspace_id` |
| `tool_calls` / `tool_results` | Requested tool invocations and their (mocked/forced/original) outputs with fidelity. | via parent `step_id` → `workspace_id` |
| `mock_definitions` | Versioned, approval-gated mocked tool behavior (`draft`→`approved`); AI-generated mocks start `draft`. | `workspace_id` |
| `capability_contracts` | Agent capability declarations, cache-keyed on `(workspace_id, agent_name, tool_catalog_hash, system_prompt_hash)`. | `workspace_id` |
| `intervention_manifests` | Append-once record of fork-point changes (edit/insert/delete message, swap model, force tool call/result, …). | via parent trace/branch → `workspace_id` |
| `trial_sets` | K repeated executions of one intervention with aggregate summary. | `workspace_id` |
| `test_cases` | Evaluation/regression artifacts (scope: final_output / selected_steps / full_trajectory). | `workspace_id` |
| `export_snapshots` | Immutable exported datasets / test bundles (promptfoo / inspect / …). | `workspace_id` |
| `sessions` | Cross-trace grouping by `gen_ai.conversation.id`; composite PK `(workspace_id, conversation_id)`. | `workspace_id` |
| `rate_cards` / `model_rates` | **Informational** operator-maintained model price reference used only to compute the pre-fork cost **estimate**. Not a billing ledger; nothing is metered or charged. | global / operator-scoped |
| `limit_usage` | **Operational** token/usage projection for quota accounting and the informational actual-vs-estimate ratio. Tracked, not capped by default; **not a billing record**. | `workspace_id` |

---

## Billing removed — explicit negative list (OSS pivot)

Billing and metering were **removed** in the OSS pivot (readiness spec §0, §2, §11
decision 4). The self-host product ships **no billing system of record**. The following
tables **must not exist** in the control-plane schema — they are listed here only to
document their **removal**, so the Phase 1 lock does not reintroduce them:

| Table (do NOT create) | Status | Why |
|-----------------------|--------|-----|
| `usage_event` | **Removed** | Was a meter event feeding billing; no metering remains. |
| `byok_usage_event` | **Removed** | Was BYOK-specific metering; dropped with billing. |
| `credit_pack_grants` | **Removed** | Was the credit-pack purchase artifact; no credits remain. |
| `stripe_webhooks_processed` | **Removed** — there is no `stripe_webhooks_processed` table because billing was **removed**. | Was the webhook idempotency ledger for the deleted billing integration. |

There is **no** metering ledger, **no** credit/meter object model, and **no** payment
webhook table. The only token observation that survives is operational: `limit_usage`
(quota accounting + the informational estimate ratio) and the per-branch `tokens_actual`
column — neither is metered or charged. Operators who want to bill their own users bring
their own billing layer entirely outside this schema.

---

## Inputs to the Phase 1 schema lock

The Phase 1 lock turns these sketches into versioned migrations and must additionally:

1. Enable + **force** RLS on every tenant-scoped table and attach the `workspace_id`
   `USING`/`WITH CHECK` policy; bind `app.workspace_id` per request from the GoTrue JWT.
2. Wire the **tenant-isolation conformance test** so the build fails if any tenant-scoped
   table lacks RLS or its policy (mirrored by ClickHouse row policies — see
   [`clickhouse.md`](./clickhouse.md)).
3. Create `audit_log` as a monthly-partitioned table with **write-once** role GRANTs and
   provision the next partition ahead of time.
4. Keep ClickHouse as a hard dependency — see the [DB_MODE matrix](../db-mode-matrix.md);
   `DB_MODE` selects **only** the control-plane Postgres, never whether ClickHouse exists.

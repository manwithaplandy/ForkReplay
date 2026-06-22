# ClickHouse — Span/Frame Analytics Schema Sketches

> **Status: design sketch.** Direct input to the **Phase 1 schema lock**. Engine and
> `ORDER BY` choices are *sketch-level* recommendations to be confirmed under load, not
> final DDL. Names trace the canonical object model in
> [`implementation-readiness-spec.md`](../../../implementation-readiness-spec.md) §2.

> **ClickHouse is REQUIRED in every deployment mode.** It is the columnar span/frame
> analytics store and has **no Postgres substitute** — there is **no disable path**.
> `DB_MODE` (`supabase | custom | compose`) selects the *control-plane Postgres only*;
> it never makes ClickHouse optional. Bundled as an OSS container in compose; a required
> component in Helm and both Terraform modules. See the
> [DB_MODE matrix](../db-mode-matrix.md).

ClickHouse is the **authoritative span/step projection**. The control-plane Postgres
([`control-plane.md`](./control-plane.md)) holds promote-on-demand step rows and branch
metadata; ClickHouse holds the high-cardinality, high-write-rate span and frame-index
data that powers the workbench queries (trace open, DAG timeline, message + tool search,
compare). Ingest target: ~10k spans/sec/node.

---

## Tenant isolation — row policies on `workspace_id`

ClickHouse is the **analytics-plane** layer of the same defense-in-depth tenant isolation
enforced by Postgres RLS in the control plane:

- **Every queryable table carries `workspace_id`** as the **first** `ORDER BY` key, so
  every read is workspace-pruned at the storage layer.
- **A ClickHouse row policy on `workspace_id` is attached to every table**, restricting
  rows to the caller's workspace. The query role never reads cross-workspace rows even if
  a `WHERE workspace_id = …` filter is omitted by a bug:

  ```sql
  CREATE ROW POLICY tenant_isolation ON spans
    FOR SELECT USING workspace_id = currentWorkspace()   -- bound per-connection from JWT
    TO query_role;
  ```

  (`currentWorkspace()` is sketch shorthand for the per-connection workspace setting bound
  from the validated GoTrue JWT — Phase 1 fixes the exact binding mechanism, e.g. a
  session setting or query parameter substitution.)
- **CI conformance.** The tenant-isolation conformance test fails the build if any
  ClickHouse table is missing its `workspace_id` row policy — the mirror of the Postgres
  RLS gate. Cross-workspace leak is a P0.

---

## `spans` — raw OTel span projection

- **Purpose.** The columnar projection of ingested OpenTelemetry spans (GenAI / OpenInference /
  framework / custom semconv). Powers the DAG timeline and step inspector. Spans are
  immutable after capture.
- **Engine.** `MergeTree` (append-only); spans are never mutated in place.

```sql
CREATE TABLE spans (
  workspace_id    UUID,
  trace_id        UUID,
  span_id         String,
  parent_span_id  String,
  step_id         UUID,
  step_ordinal    UInt32,
  name            String,
  span_kind       LowCardinality(String),
  step_type       LowCardinality(String),   -- llm_call | tool_execution | agent_invocation | ...
  service_name    LowCardinality(String),
  status_code     LowCardinality(String),
  start_time      DateTime64(9),
  end_time        DateTime64(9),
  duration_ns     UInt64,
  attributes      Map(String, String),      -- flattened gen_ai.* / openinference.* attrs
  semconv_source  LowCardinality(String)
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(start_time)
ORDER BY (workspace_id, trace_id, start_time, span_id);
-- Row policy: tenant_isolation ON spans USING workspace_id = currentWorkspace()
```

## `frames` — frame index / step-boundary projection

- **Purpose.** The analytics index of forkable frames at step boundaries
  (`before_step` / `after_step`). The full frame payload lives in S3
  (`frames/<workspace_id>/...`); this table indexes it for compare, fork-point pickers,
  and message/tool search. One row per built frame.
- **Engine.** `ReplacingMergeTree(last_rebuilt_at)` so a rebuilt frame's latest version
  wins on merge (rebuilt frames cap fidelity at `schema_equivalent`).

```sql
CREATE TABLE frames (
  workspace_id        UUID,
  frame_id            UUID,
  trace_id            UUID,
  branch_id           UUID,
  step_id             UUID,
  step_ordinal        UInt32,
  boundary            LowCardinality(String),  -- before_step | after_step
  content_hash        String,                  -- sha256-<hex>; S3 content address
  object_key          String,                  -- frames/<workspace_id>/<hh>/<hh>/<hash>
  fidelity_badge      LowCardinality(String),  -- exact | schema_equivalent | approximate
  valid_for_fork      UInt8,
  message_count       UInt32,
  tool_catalog_hash   String,
  size_bytes          UInt64,
  rebuild_count       UInt32,
  last_rebuilt_at     DateTime64(3)
)
ENGINE = ReplacingMergeTree(last_rebuilt_at)
PARTITION BY toYYYYMM(last_rebuilt_at)
ORDER BY (workspace_id, trace_id, step_ordinal, frame_id);
-- Row policy: tenant_isolation ON frames USING workspace_id = currentWorkspace()
```

> **Message + tool search projection.** In V1, message/tool-content search reads frame
> payloads from the object store; a dedicated denormalized search projection (e.g.
> `frame_messages` exploding `messages`/`tool_calls` into searchable rows) is the V1.1
> evolution. The query-shape sketch below describes the V1.1 target shape so the Phase 1
> lock leaves room for it; it carries `workspace_id` + a row policy like every other table.

---

## The four query shapes

These are the workbench read paths the schema must serve. Each is **workspace-pruned**
(the row policy on `workspace_id` enforces it even without the explicit predicate shown).

### 1. trace-open

Open a trace: header counts + the ordered step list for the step inspector.

```sql
-- trace-open: ordered steps + per-step span counts for one trace
SELECT step_ordinal, step_id, step_type,
       min(start_time) AS step_start,
       max(end_time)   AS step_end,
       count()         AS span_count
FROM spans
WHERE workspace_id = currentWorkspace() AND trace_id = {trace_id:UUID}
GROUP BY step_ordinal, step_id, step_type
ORDER BY step_ordinal;
```

### 2. dag-timeline

The DAG / timeline view: parent→child span edges + timing for the interactive graph
(≤2k step-DAG nodes interactive; progressive disclosure above).

```sql
-- dag-timeline: span nodes + parent edges + durations for the DAG/timeline render
SELECT span_id, parent_span_id, step_ordinal, name, span_kind,
       start_time, duration_ns, status_code
FROM spans
WHERE workspace_id = currentWorkspace() AND trace_id = {trace_id:UUID}
ORDER BY start_time;
```

### 3. message+tool-search

Search message content and tool calls/results across a workspace's frames (V1: hydrate
from object store; V1.1: served from the `frame_messages` search projection).

```sql
-- message+tool-search: locate frames whose messages/tool calls match a query
SELECT frame_id, trace_id, branch_id, step_ordinal, boundary, object_key
FROM frames
WHERE workspace_id = currentWorkspace()
  AND ( {q:String} = '' OR positionCaseInsensitive(tool_catalog_hash, {q:String}) > 0 )
ORDER BY step_ordinal
LIMIT 200;
-- V1.1 evolves this onto a denormalized frame_messages projection (role/content/tool_name),
-- also workspace_id-keyed with a row policy.
```

### 4. compare

Compare two trajectories (trace vs. branch, or branch vs. branch) step-by-step at frame
boundaries to surface the first divergence.

```sql
-- compare: align frames of two trajectories by step_ordinal/boundary
SELECT a.step_ordinal, a.boundary,
       a.frame_id   AS left_frame,  a.content_hash AS left_hash,
       b.frame_id   AS right_frame, b.content_hash AS right_hash,
       a.content_hash != b.content_hash AS diverged
FROM frames AS a
FULL JOIN frames AS b
  ON a.step_ordinal = b.step_ordinal AND a.boundary = b.boundary
WHERE a.workspace_id = currentWorkspace()
  AND a.trace_id  = {left_id:UUID}      -- left trajectory (trace or branch)
  AND b.branch_id = {right_id:UUID}     -- right trajectory
ORDER BY a.step_ordinal, a.boundary;
```

---

## Inputs to the Phase 1 schema lock

1. Confirm engine / `ORDER BY` under the 10k spans/sec/node ingest target; keep
   `workspace_id` first in every `ORDER BY` for tenant-pruned reads.
2. Attach a **row policy on `workspace_id`** to **every** queryable table and wire the CI
   tenant-isolation conformance check (mirror of the Postgres RLS gate).
3. Bind the per-connection workspace identity from the validated GoTrue JWT (the exact
   `currentWorkspace()` mechanism is a Phase 1 decision).
4. Keep ClickHouse a **hard dependency in every `DB_MODE`** — there is no Postgres-only or
   ClickHouse-disabled configuration. See the [DB_MODE matrix](../db-mode-matrix.md).

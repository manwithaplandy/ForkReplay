# DB_MODE Matrix

> **Status: design sketch.** Direct input to the **Phase 1 schema lock** and the
> deployment-packaging phase. Companion to the schema sketches in
> [`schemas/control-plane.md`](./schemas/control-plane.md) and
> [`schemas/clickhouse.md`](./schemas/clickhouse.md).

`DB_MODE` selects how the **control-plane Postgres** and its **GoTrue** auth are
provisioned. It is the *only* knob for the control plane's backing store. It has **no
effect on ClickHouse**: the span/frame analytics store is **required in every mode**.

```
DB_MODE = supabase | custom | compose       # control-plane Postgres only
ClickHouse                                    # REQUIRED regardless of DB_MODE
```

---

## The matrix

| `DB_MODE` | Postgres provisioned by | GoTrue (auth) provided by | ClickHouse (analytics) | Typical target |
|-----------|-------------------------|---------------------------|------------------------|----------------|
| **`compose`** | **Bundled Postgres container** in the Docker Compose stack (quickstart default). | **Bundled GoTrue container** running against the bundled Postgres. | **REQUIRED** — bundled OSS ClickHouse container. | Local dev / single-node quickstart |
| **`custom`** | **Bring-your-own Postgres** — managed RDS, Azure Database for PostgreSQL, or self-managed. Connection via `DATABASE_URL` (or discrete `POSTGRES_*`). | **Bundled GoTrue container** pointed at your Postgres (you supply `GOTRUE_JWT_SECRET`). | **REQUIRED** — self-managed / subchart ClickHouse via `CLICKHOUSE_*`. | Helm / Terraform (AWS / Azure) |
| **`supabase`** | **Supabase Postgres** (managed or self-hosted Supabase). | **Supabase-managed GoTrue (Supabase Auth)** — the same GoTrue JWTs, issued by Supabase. | **REQUIRED** — Supabase has **no** ClickHouse; you still run ClickHouse separately via `CLICKHOUSE_*`. | Teams already on Supabase |

**GoTrue is the auth provider in all three modes.** Every service validates GoTrue-issued
JWTs identically regardless of `DB_MODE`; only *where the GoTrue instance lives* changes
(a bundled container in `compose`/`custom`, the managed Auth service in `supabase`).

---

## ClickHouse is required regardless of DB_MODE

This is the load-bearing invariant of the matrix:

- **ClickHouse is required in every mode** — `compose`, `custom`, and `supabase` alike.
  It is the columnar span/frame analytics store (see
  [`schemas/clickhouse.md`](./schemas/clickhouse.md)) and has **no Postgres substitute**.
- **There is no "disable ClickHouse" path** and **no Postgres-only mode.** "Pluggable
  Postgres" via `DB_MODE` applies to the *control plane only*.
- **`supabase` does not provide ClickHouse.** Choosing `DB_MODE=supabase` swaps only where
  the control-plane Postgres + GoTrue come from; you must still stand up ClickHouse
  yourself and point `CLICKHOUSE_*` at it.
- Tenant isolation is enforced in **both** planes: Postgres **RLS** on every tenant-scoped
  table and ClickHouse **row policies on `workspace_id`** on every queryable table, with a
  single CI conformance gate across all three DB modes.

| Concern | Selected by | Varies with `DB_MODE`? |
|---------|-------------|------------------------|
| Control-plane Postgres location | `DB_MODE` + `DATABASE_URL` / `POSTGRES_*` | **Yes** |
| GoTrue auth location | `DB_MODE` (bundled vs. Supabase-managed) | **Yes** (provider/JWT validation identical) |
| ClickHouse span/frame analytics | `CLICKHOUSE_*` | **No — always required** |

---

## Relevant configuration

| Variable | Role |
|----------|------|
| `DB_MODE` | `compose` \| `custom` \| `supabase` — control-plane Postgres provisioning |
| `DATABASE_URL` / `POSTGRES_*` | Control-plane Postgres connection (DSN overrides discrete vars) |
| `GOTRUE_JWT_SECRET`, `GOTRUE_*` | Auth signing material / GoTrue endpoints (all modes) |
| `CLICKHOUSE_URL`, `CLICKHOUSE_*` | **Required** analytics store endpoint/credentials — every mode |

See [`docs/deployment/configuration.md`](../deployment/configuration.md) for the full
environment-variable reference and
[`docs/deployment/architecture.md`](../deployment/architecture.md) for the self-host
topology.

---

## Inputs to the Phase 1 schema lock

1. The control-plane migrations (RLS-forced, `workspace_id`-scoped) must apply identically
   across all three `DB_MODE` values — the tenant-isolation conformance gate runs against
   each mode.
2. ClickHouse schema + `workspace_id` row policies are provisioned the same way in every
   mode; `DB_MODE` never gates ClickHouse.
3. `supabase` mode uses Supabase's managed GoTrue; `compose`/`custom` bundle a GoTrue
   container — but the JWT contract every service validates is identical.

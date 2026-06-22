# ForkReplay — Configuration Reference

Full environment-variable reference for a self-hosted deployment, grouped by component.

The authoritative list of variable **names** lives in [`.env.example`](../../.env.example) —
copy it to `.env.local` and fill in values. This page describes what each group does, which
values are **secrets**, and how the pluggable backends are selected. Every value shown here
is a `${PLACEHOLDER}` or a non-sensitive default; **never commit real secrets** (see
[`SECURITY.md`](../../SECURITY.md)).

> **ClickHouse is required in every mode.** The `DB_MODE` choice below is for the *control
> plane only*; the analytics store is always ClickHouse.

Secret-handling rule of thumb: any variable marked **secret** belongs in your secret manager
or a gitignored `.env.local`, never in a committed file. Templates use `${PLACEHOLDER}`
markers exclusively.

---

## Control-plane Postgres — `DB_MODE`

The control-plane database is pluggable via three modes. ClickHouse is unaffected by this
setting.

| Mode | Meaning | Postgres comes from |
|------|---------|---------------------|
| `compose` | Bundled Postgres container (quickstart default) | Docker Compose stack |
| `custom` | Bring-your-own Postgres | Managed RDS / Azure Database for PostgreSQL / self-managed |
| `supabase` | Managed or self-hosted Supabase Postgres | Supabase |

| Variable | Secret? | Notes |
|----------|---------|-------|
| `DB_MODE` | no | `compose` \| `custom` \| `supabase` |
| `POSTGRES_HOST` | no | Host for the discrete-var connection form |
| `POSTGRES_PORT` | no | Default `5432` |
| `POSTGRES_DB` | no | Default `forkreplay` |
| `POSTGRES_USER` | no | Application role |
| `POSTGRES_PASSWORD` | **yes** | Application role password |
| `DATABASE_URL` | **yes** | Full DSN; **overrides** the discrete `POSTGRES_*` vars when set |

Required Postgres extensions: `pgcrypto`, `uuid-ossp` (and `pg_cron` if you run the optional
in-database partition/retention scheduler).

---

## Auth — GoTrue (Supabase Auth OSS)

GoTrue is the auth provider in **all** DB modes; every service validates GoTrue-issued JWTs
the same way. In `compose`/`custom` a GoTrue container runs against your Postgres; in
`supabase` it is the Supabase-managed Auth service.

| Variable | Secret? | Notes |
|----------|---------|-------|
| `GOTRUE_SITE_URL` | no | Base site URL for confirmation links |
| `GOTRUE_API_EXTERNAL_URL` | no | External issuer URL |
| `GOTRUE_JWT_SECRET` | **yes** | Signing secret / JWKS material |
| `GOTRUE_JWT_AUD` | no | Audience; default `authenticated` |

Email confirmations require an email backend (see [Email](#email-pluggable)).

---

## ClickHouse (REQUIRED)

The span/frame analytics store. Bundled as an OSS container in compose; a required component
in Helm and both Terraform modules.

| Variable | Secret? | Notes |
|----------|---------|-------|
| `CLICKHOUSE_URL` | no | HTTP(S) endpoint |
| `CLICKHOUSE_NATIVE_PORT` | no | Native protocol port; default `9000` |
| `CLICKHOUSE_USERNAME` | no | Default `default` |
| `CLICKHOUSE_PASSWORD` | **yes** | ClickHouse user password |
| `CLICKHOUSE_DB` | no | Default `forkreplay` |

---

## Object storage — S3-compatible

One abstraction backs MinIO (compose), AWS S3 (Terraform AWS), and Azure Blob (Terraform
Azure). Frames, export bundles, and the audit cold archive live here under workspace-scoped
key prefixes.

| Variable | Secret? | Notes |
|----------|---------|-------|
| `S3_ENDPOINT` | no | S3-compatible endpoint (selects the backend) |
| `S3_REGION` | no | Default `us-east-1` |
| `S3_ACCESS_KEY_ID` | **yes** | Access key |
| `S3_SECRET_ACCESS_KEY` | **yes** | Secret key |
| `S3_BUCKET_FRAMES` | no | Frames bucket; default `forkreplay-frames` |
| `S3_BUCKET_BLOBS` | no | Externalized blob bucket; default `forkreplay-frames-blobs` |

For the 7-year audit cold archive, enable object-lock / WORM retention on the
`committed=true/` prefix (AWS S3 Object Lock, MinIO retention, or the provider equivalent).

---

## Ingest queue — `QUEUE_BACKEND`

NATS is the primary queue; Redis Streams is the lighter alternative.

| Variable | Secret? | Notes |
|----------|---------|-------|
| `QUEUE_BACKEND` | no | `nats` (primary) \| `redis` |
| `NATS_URL` | no | NATS connection URL |
| `NATS_CREDS` | **yes** | NATS credentials, if auth is enabled |

---

## Live streaming — Redis pub/sub

Redis backs FastAPI SSE for branch progress and system banners (and is the alternative
ingest queue when `QUEUE_BACKEND=redis`).

| Variable | Secret? | Notes |
|----------|---------|-------|
| `REDIS_URL` | **yes** | May embed credentials — treat as a secret |

---

## Durable orchestration — Temporal

| Variable | Secret? | Notes |
|----------|---------|-------|
| `TEMPORAL_HOST` | no | Temporal frontend host |
| `TEMPORAL_NAMESPACE` | no | Default `default` |
| `TEMPORAL_TLS_CERT` | **yes** | Only if Temporal mTLS is enabled |
| `TEMPORAL_TLS_KEY` | **yes** | Only if Temporal mTLS is enabled |

---

## LLM routing — `LLM_PROVIDER`

Pluggable provider abstraction. `ollama` is keyless for local use.

| Variable | Secret? | Notes |
|----------|---------|-------|
| `LLM_PROVIDER` | no | `openrouter` \| `openai` \| `anthropic` \| `ollama` |
| `LLM_API_BASE` | no | Override base URL (e.g. a local Ollama endpoint) |
| `LLM_API_KEY` | **yes** | Operator default key; omit for keyless local Ollama |

Workspace-scoped BYOK keys are stored separately and may be envelope-encrypted with the
optional KEK below.

---

## BYOK key custody — optional KEK (`KEK_PROVIDER`)

Optional key-encryption-key for envelope-encrypting workspace LLM keys at rest. `none` is
acceptable for a single-operator self-host that relies on database/secret-store at-rest
encryption.

| Variable | Secret? | Notes |
|----------|---------|-------|
| `KEK_PROVIDER` | no | `none` \| `age` \| `libsodium` |
| `KEK_AGE_RECIPIENTS` | no | Comma-separated age recipient public keys (multi-recipient supported) |
| `KEK_AGE_IDENTITY_FILE` | **yes** | Path to the operator-held age identity used to decrypt — **never commit** |

There is **no Vault dependency**; this replaces the earlier Supabase Vault design.

---

## Email (pluggable) — `EMAIL_BACKEND` {#email-pluggable}

Required for GoTrue confirmation emails. `console` prints links to logs (fine for local dev).

| Variable | Secret? | Notes |
|----------|---------|-------|
| `EMAIL_BACKEND` | no | `smtp` \| `resend` \| `console` |
| `SMTP_HOST` | no | SMTP server host |
| `SMTP_PORT` | no | Default `587` |
| `SMTP_USERNAME` | **yes** | SMTP auth user |
| `SMTP_PASSWORD` | **yes** | SMTP auth password |
| `EMAIL_FROM` | no | From address |

---

## Observability (optional)

Any OTLP-compatible sink (self-hosted OTel Collector + Prometheus/Grafana, or an external
endpoint). Leave unset to disable.

| Variable | Secret? | Notes |
|----------|---------|-------|
| `OTEL_EXPORTER_OTLP_ENDPOINT` | no | OTLP sink endpoint |
| `OTEL_EXPORTER_OTLP_HEADERS` | **yes** | Auth headers, if your sink requires them |

---

## Web (Next.js standalone container)

| Variable | Secret? | Notes |
|----------|---------|-------|
| `WEB_PUBLIC_URL` | no | Public URL of the workbench |
| `NEXT_PUBLIC_API_BASE_URL` | no | Public base URL of `services/api` |
| `NEXT_PUBLIC_GOTRUE_URL` | no | Public GoTrue URL for the browser |

`NEXT_PUBLIC_*` values are baked into the client bundle — keep secrets out of them.

---

## Deprecated (legacy Cloudflare workers only)

Only needed to deploy the deprecated `workers/otlp-gateway` / `workers/sse-relay`, which are
slated for removal. Supply at deploy time; never hard-code account IDs in `wrangler.toml`.

| Variable | Secret? | Notes |
|----------|---------|-------|
| `CLOUDFLARE_ACCOUNT_ID` | **yes** | Provided via env, not committed |

---

## Minimum viable configuration by target

| Target | Must set | Notes |
|--------|----------|-------|
| **Docker Compose** | `DB_MODE=compose`, ClickHouse vars, S3 (MinIO) vars, `QUEUE_BACKEND`, `REDIS_URL`, `TEMPORAL_HOST`, `LLM_PROVIDER` + `LLM_API_KEY` | The shipped `.env.example` defaults work for local dev |
| **Helm** | Same component vars, with `DB_MODE=custom`/`supabase` if using external Postgres | ClickHouse subchart or external endpoint |
| **Terraform (AWS/Azure)** | `DB_MODE=custom`, managed S3/Blob `S3_*`, self-managed ClickHouse `CLICKHOUSE_*`, Redis/NATS, Temporal | ClickHouse is self-managed and required |

See [docker-compose.md](./docker-compose.md), [helm.md](./helm.md),
[terraform-aws.md](./terraform-aws.md), and [terraform-azure.md](./terraform-azure.md) for
per-target details.

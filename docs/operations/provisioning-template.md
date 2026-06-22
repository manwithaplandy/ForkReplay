# ForkReplay — Provisioning Template (self-host)

Sanitized successor to the original provisioning log. **This file contains no real
credentials or account identifiers — only `${PLACEHOLDER}` markers.** Copy it to
`PROVISIONING.local.md` (gitignored) when you record real values for your own
deployment, and never commit the filled-in copy.

> **Secrets policy:** Do not commit secrets, account IDs, project refs, API keys,
> endpoints, or operator PII to this repository. See `SECURITY.md`. Real values for a
> live deployment belong in your secret manager and in a local, gitignored runbook.

ForkReplay is self-hostable. The components below are the OSS target stack. Which ones
you provision depends on the deployment mode you choose (see
`docs/deployment/configuration.md` for the full env reference and the three `DB_MODE`
options). **ClickHouse is required in every mode** — it is the columnar span/frame
analytics store and has no Postgres substitute.

---

## Control-plane Postgres (`DB_MODE`)

ForkReplay supports three control-plane database modes:

- `DB_MODE=compose` — bundled Postgres container (docker-compose quickstart default).
- `DB_MODE=custom` — bring-your-own Postgres (managed RDS / Azure DB / self-managed).
- `DB_MODE=supabase` — managed or self-hosted Supabase Postgres.

Record only placeholders here:

- **Mode:** `${DB_MODE}`
- **Postgres host:** `${POSTGRES_HOST}`
- **Postgres port:** `${POSTGRES_PORT}`
- **Database name:** `${POSTGRES_DB}`
- **Application user:** `${POSTGRES_USER}`
- **Application password:** `${POSTGRES_PASSWORD}` *(secret — store in your secret manager)*
- **Connection URL:** `${DATABASE_URL}`

Required Postgres extensions: `pgcrypto`, `uuid-ossp` (and `pg_cron` if you run the
optional in-database partition/retention scheduler).

---

## Auth — GoTrue (Supabase Auth OSS)

GoTrue is the auth provider in **all** DB modes. In `compose`/`custom` modes a GoTrue
container is bundled; the application validates GoTrue-issued JWTs everywhere.

- **GoTrue site URL:** `${GOTRUE_SITE_URL}`
- **GoTrue external URL / issuer:** `${GOTRUE_API_EXTERNAL_URL}`
- **JWT secret / JWKS:** `${GOTRUE_JWT_SECRET}` *(secret)*
- **JWT audience:** `${GOTRUE_JWT_AUD}`

GoTrue email confirmations require an SMTP backend (see Email below). Tenant isolation is
enforced by native Postgres Row-Level Security keyed on `workspace_id`.

---

## Analytics store — ClickHouse (required)

Bundled OSS ClickHouse container in compose; a required component in Helm/Terraform.

- **HTTP(S) endpoint:** `${CLICKHOUSE_URL}`
- **Native port:** `${CLICKHOUSE_NATIVE_PORT}`
- **Username:** `${CLICKHOUSE_USERNAME}`
- **Password:** `${CLICKHOUSE_PASSWORD}` *(secret)*
- **Database:** `${CLICKHOUSE_DB}`

---

## Object storage — S3-compatible

ForkReplay uses an S3-compatible object-store abstraction for frames, export bundles, and
the audit cold archive:

- **compose:** MinIO container.
- **Terraform (AWS):** AWS S3.
- **Terraform (Azure):** Azure Blob (S3-compatible gateway or native SDK).

Record placeholders:

- **Endpoint:** `${S3_ENDPOINT}`
- **Region:** `${S3_REGION}`
- **Access key ID:** `${S3_ACCESS_KEY_ID}` *(secret)*
- **Secret access key:** `${S3_SECRET_ACCESS_KEY}` *(secret)*
- **Frames bucket:** `${S3_BUCKET_FRAMES}`
- **Blobs bucket:** `${S3_BUCKET_BLOBS}`

---

## Ingest queue — NATS (Redis Streams documented as alternative)

- **Queue backend:** `${QUEUE_BACKEND}` (`nats` primary; `redis` alternative)
- **NATS URL:** `${NATS_URL}`
- **NATS credentials:** `${NATS_CREDS}` *(secret, if auth enabled)*

---

## Live streaming — Redis pub/sub

FastAPI SSE is backed by Redis pub/sub for branch progress and system banners.

- **Redis URL:** `${REDIS_URL}` *(may embed credentials — treat as secret)*

---

## Durable orchestration — Temporal (self-hosted)

- **Temporal host:** `${TEMPORAL_HOST}`
- **Temporal namespace:** `${TEMPORAL_NAMESPACE}`
- **Temporal TLS material:** `${TEMPORAL_TLS_CERT}` / `${TEMPORAL_TLS_KEY}` *(secret, if mTLS enabled)*

---

## LLM routing (pluggable)

- **Provider mode:** `${LLM_PROVIDER}` (`openrouter` / `openai` / `anthropic` / `ollama`)
- **API base URL:** `${LLM_API_BASE}`
- **API key:** `${LLM_API_KEY}` *(secret; omit for keyless local Ollama)*

Workspace-scoped BYOK keys are operator/workspace secrets supplied via env/secret, with an
optional KEK (age/libsodium) for envelope encryption. There is no Vault dependency.

---

## Email (pluggable SMTP) — required for GoTrue confirmations

- **Email backend:** `${EMAIL_BACKEND}` (`smtp` / `resend` / `console`)
- **SMTP host:** `${SMTP_HOST}`
- **SMTP port:** `${SMTP_PORT}`
- **SMTP username:** `${SMTP_USERNAME}` *(secret)*
- **SMTP password:** `${SMTP_PASSWORD}` *(secret)*
- **From address:** `${EMAIL_FROM}`

---

## Observability (optional)

Self-hosted OTel collector + Prometheus/Grafana, or any OTLP-compatible sink:

- **OTLP endpoint:** `${OTEL_EXPORTER_OTLP_ENDPOINT}`
- **OTLP headers/auth:** `${OTEL_EXPORTER_OTLP_HEADERS}` *(secret, if used)*

---

## Web (Next.js standalone container)

- **Public app URL:** `${WEB_PUBLIC_URL}`
- **Public API base URL:** `${NEXT_PUBLIC_API_BASE_URL}`
- **Public GoTrue URL:** `${NEXT_PUBLIC_GOTRUE_URL}`

---

## Provisioning checklist

1. Pick a deployment target (docker-compose / Helm / Terraform-AWS / Terraform-Azure) and
   a `DB_MODE`. See `docs/deployment/`.
2. Provision the required backing services above for your target. **ClickHouse is always
   required.**
3. Generate secrets (DB passwords, GoTrue JWT secret, S3 keys, optional KEK) in your
   secret manager — not in this repo.
4. Fill a local, gitignored `PROVISIONING.local.md` (or your secret manager) with the real
   values that replace the `${PLACEHOLDER}` markers.
5. Populate `.env.local` from `.env.example`.
6. Bring the stack up and run the deployment smoke test (deferred to the implementation
   phase that authors the IaC; see `docs/deployment/docker-compose.md`).

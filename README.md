# ForkReplay

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](./LICENSE)

**Fork and replay captured AI agent conversations.** ForkReplay ingests OpenTelemetry
traces from your AI agents, projects them into a replayable frame/branch model, and lets
you fork any point in a captured conversation to explore alternate outcomes — with durable,
deterministic replay against real or mocked LLM responses.

ForkReplay is **open source (Apache-2.0) and self-hostable**. Run it on your own
infrastructure with Docker Compose, Kubernetes (Helm), or Terraform (AWS / Azure).

---

## ClickHouse is required

> **Every ForkReplay deployment requires ClickHouse.** It is the columnar span/frame
> analytics store and has **no Postgres substitute**. The "pluggable Postgres" choice
> (`DB_MODE`) applies to the *control plane only*; the analytics store is always ClickHouse.
> ClickHouse is bundled as an OSS container in the Docker Compose stack and is a required
> component in the Helm chart and both Terraform modules. See
> [docs/deployment/architecture.md](./docs/deployment/architecture.md).

---

## 5-minute quickstart (Docker Compose)

The fastest way to run ForkReplay locally is the bundled Docker Compose stack. It brings up
the full self-host stack — control-plane Postgres, GoTrue auth, ClickHouse, MinIO, NATS,
Redis, Temporal, the five Python services, and the Next.js web app — with a single command,
defaulting to a **single-tenant default workspace**.

```bash
git clone https://github.com/forkreplay/forkreplay.git
cd forkreplay
cp .env.example .env.local      # fill in placeholders; the defaults work for local dev
docker compose up
```

Then open `http://localhost:3000`.

> **Status note:** Planning is complete and implementation is phased. The deployment
> artifacts themselves — the `deploy/docker-compose/docker-compose.yml`, the Helm chart,
> and the Terraform modules — are authored in a **future implementation phase**. The
> documents under [docs/deployment/](./docs/deployment/) describe the intended design and
> environment contract that those artifacts will implement. See
> [docs/deployment/docker-compose.md](./docs/deployment/docker-compose.md) for the full
> quickstart walkthrough.

---

## Deployment matrix

| Target | What it provides | Control-plane DB | ClickHouse | Object storage | Best for |
|--------|------------------|------------------|------------|----------------|----------|
| **Docker Compose** | Full single-host stack, bundled backing services | Bundled Postgres (`DB_MODE=compose`) | Bundled container (required) | MinIO container | Local dev, evaluation, small single-node installs |
| **Helm (Kubernetes)** | Umbrella chart + subcharts for every component | Bundled subchart or external (`DB_MODE=custom`/`supabase`) | Required subchart | MinIO subchart or external S3 | Production on any Kubernetes cluster |
| **Terraform (AWS)** | Cloud module: RDS, S3, EKS/ECS, self-managed ClickHouse | RDS or self-managed (`DB_MODE=custom`) | Self-managed on EC2/EKS (required) | AWS S3 | Production on AWS |
| **Terraform (Azure)** | Cloud module: Azure DB, Blob, AKS, self-managed ClickHouse | Azure Database for PostgreSQL (`DB_MODE=custom`) | Self-managed on AKS/VMs (required) | Azure Blob (via S3-compatible layer) | Production on Azure |

Full guides: [docker-compose](./docs/deployment/docker-compose.md) ·
[helm](./docs/deployment/helm.md) ·
[terraform-aws](./docs/deployment/terraform-aws.md) ·
[terraform-azure](./docs/deployment/terraform-azure.md).

---

## Components at a glance

ForkReplay is a small set of Python services plus a Next.js web app, backed by a handful of
open-source data stores. Everything runs on infrastructure you control.

| Component | Role | Selected by |
|-----------|------|-------------|
| Control-plane Postgres | Workspaces, users, branch metadata, audit trail; tenant isolation via native RLS | `DB_MODE` |
| GoTrue (Supabase Auth OSS) | Authentication in **all** modes; app validates GoTrue JWTs everywhere | always on |
| ClickHouse | **Required** columnar span/frame analytics store | always on |
| S3-compatible object storage | Frames, export bundles, audit cold archive | `S3_ENDPOINT` (MinIO / AWS S3 / Azure Blob) |
| FastAPI OTLP endpoint | OTLP ingress (in `ingest`/`api`); replaces the deprecated CF Workers gateway | always on |
| NATS | Primary ingest queue (Redis Streams is the lighter alternative) | `QUEUE_BACKEND` |
| Redis | SSE pub/sub backing for branch progress + system banners (and the queue alt) | always on |
| Temporal | Durable orchestration for fork/replay; replaces the deprecated CF Workflows | always on |
| `api`, `ingest`, `replay-worker`, `mock-gen-worker`, `export-worker` | The five Python services | always on |
| Next.js web | Standalone container workbench; replaces the Vercel deployment | always on |
| Pluggable LLM routing | OpenRouter / OpenAI / Anthropic / Ollama | `LLM_PROVIDER` |
| Pluggable email | Resend / SMTP / console (needed for GoTrue confirmations) | `EMAIL_BACKEND` |

See [docs/deployment/configuration.md](./docs/deployment/configuration.md) for the full env
reference, and [docs/operations/provisioning-template.md](./docs/operations/provisioning-template.md)
for a sanitized provisioning worksheet.

### Control-plane database modes (`DB_MODE`)

The control-plane Postgres is pluggable via three modes (the analytics store is always
ClickHouse regardless of this setting):

- **`DB_MODE=compose`** — bundled Postgres container. The Docker Compose quickstart default.
- **`DB_MODE=custom`** — bring-your-own Postgres (managed RDS / Azure Database for
  PostgreSQL / self-managed).
- **`DB_MODE=supabase`** — managed or self-hosted Supabase Postgres.

---

## Project status

Planning is **complete**; implementation is **phased**. This pivot converts ForkReplay from
a managed, multi-vendor SaaS to an open-source, self-hostable product. The canonical
specification docs describe the product; the phased build sequence (Phase 0–6) is tracked as
GitHub milestones; and the deployment artifacts (Compose / Helm / Terraform) are authored in
a future phase. The documents under `docs/deployment/` are the authoritative design and
environment contract for those artifacts.

| Doc | Version | What it is |
|-----|---------|------------|
| `agent-trace-fork-prd.md` | v0.9 | Product requirements, scope, success metrics |
| `implementation-readiness-spec.md` | v0.5 | Canonical object model, API contracts, event taxonomy, security contracts, planning-decision audit trail |
| `competitive_analysis.md` | v0.4 | Market landscape, positioning, differentiation thesis |
| GitHub milestones (Phase 0–6) | — | Phase build sequence, per-phase issue breakdown, milestone exit criteria |

---

## Documentation

- **Architecture (design sketches)**
  - [Architecture index](./docs/architecture/README.md) — services, schemas, API surface, Temporal workflows, SDK, deployment modes
- **Deployment**
  - [Architecture](./docs/deployment/architecture.md) — self-host topology and data flow
  - [Configuration](./docs/deployment/configuration.md) — full environment-variable reference
  - [Docker Compose](./docs/deployment/docker-compose.md) — bundled stack + 5-minute quickstart
  - [Helm](./docs/deployment/helm.md) — Kubernetes chart design
  - [Terraform (AWS)](./docs/deployment/terraform-aws.md) — AWS module design
  - [Terraform (Azure)](./docs/deployment/terraform-azure.md) — Azure module design
- **Operations**
  - [Provisioning template](./docs/operations/provisioning-template.md) — sanitized worksheet
- [Documentation index](./docs/README.md)

---

## Contributing

Contributions are welcome. See [CONTRIBUTING.md](./CONTRIBUTING.md) for local setup, the
monorepo layout, coding conventions, the docs-drift contract, the PR process, and the
DCO sign-off requirement. Please also read the [Code of Conduct](./CODE_OF_CONDUCT.md).

**Never commit secrets or proprietary identifiers.** ForkReplay docs and config use the
`${PLACEHOLDER}` convention exclusively. See [SECURITY.md](./SECURITY.md) and the
secrets policy in CONTRIBUTING.

---

## License

ForkReplay is licensed under the **Apache License, Version 2.0**. See [LICENSE](./LICENSE)
for the full text.

```
Copyright 2026 The ForkReplay Authors
```

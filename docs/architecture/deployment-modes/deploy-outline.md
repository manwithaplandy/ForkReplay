# ForkReplay — `deploy/` Artifact Outline

The planned layout of the `deploy/` tree across the three self-host targets: the
docker-compose all-in-one stack, the Helm (Kubernetes) chart, and the Terraform skeletons
for AWS + Azure. This is the design outline that Phase 6 turns into running artifacts.

> **Phase-6 design outline only.** Per the Phase 6 GitHub milestone, the actual `deploy/`
> artifacts (the Compose file, the Helm chart, the Terraform modules) are authored in a
> future implementation phase. **No functional deploy code is
> authored here** — this page sketches the directory layout, the bundled components, and the
> variable surfaces so the implementation has a fixed target. The deployment-target design
> narratives live under [`docs/deployment/`](../../deployment/architecture.md); this page is
> the consolidated `deploy/`-tree view.

> **ClickHouse is required in every mode.** It is the columnar span/frame analytics store and
> has **no Postgres substitute**. The `DB_MODE` choice applies to the *control plane only*;
> the analytics plane is always ClickHouse. ClickHouse is **required with no disable option**
> in every target below — it is never optional and cannot be disabled.

---

## Planned `deploy/` tree

```
deploy/
├── docker-compose/                 # single-host / dev all-in-one bundle
│   ├── docker-compose.yml          # the bundled stack (see component list below)
│   ├── docker-compose.observability.yml   # optional OTel collector + Grafana + Prometheus
│   └── .env.example -> ../../.env.example  # same variable contract as the repo root
├── helm/
│   └── forkreplay/                 # umbrella chart (Kubernetes)
│       ├── Chart.yaml              # declares subchart dependencies
│       ├── values.yaml             # top-level values (DB_MODE, clickhouse.enabled, …)
│       ├── templates/              # ForkReplay service workloads + ingress + secrets
│       └── charts/                 # vendored / dependency subcharts
└── terraform/
    ├── aws/                        # AWS IaC skeleton
    │   ├── main.tf  variables.tf  outputs.tf
    │   └── modules/                # network / postgres / clickhouse / object-store /
    │                               # queue / redis / temporal / compute
    └── azure/                      # Azure IaC skeleton
        ├── main.tf  variables.tf  outputs.tf
        └── modules/                # network / postgres / clickhouse / object-store /
                                    # queue / redis / temporal / compute
```

The environment contract (the variables in [`.env.example`](../../../.env.example)) is
**identical across all three targets**; targets differ only in *where* each backend runs and
*how* endpoints/secrets are supplied. A configuration that works in compose maps onto Helm or
Terraform by swapping endpoints and flipping `DB_MODE`.

---

## Target 1 — docker-compose (all-in-one, single-host / dev)

A single `docker compose up` brings up the full self-host stack on one host — the fastest way
to evaluate ForkReplay or run a small single-node install. `DB_MODE=compose` is the default.
See [docker-compose.md](../../deployment/docker-compose.md) for the quickstart UX.

**Bundled backing services** (all run as containers in the compose stack):

| Service | Role | Selected / configured by |
|---------|------|--------------------------|
| **PostgreSQL** | Control-plane DB (workspaces, users, branch metadata, audit) | `DB_MODE=compose` |
| **GoTrue** | Auth provider; issues JWTs validated everywhere | bundled in compose/custom |
| **ClickHouse** | **Required** span/frame analytics store (no disable option) | always on |
| **MinIO** | S3-compatible object storage (frames, exports, audit archive) | `S3_ENDPOINT` |
| **NATS** | Ingest queue | `QUEUE_BACKEND=nats` |
| **Redis** | SSE pub/sub (and the alternative ingest queue when `QUEUE_BACKEND=redis`) | `REDIS_URL` |
| **Temporal** | Durable orchestration for fork/replay | `TEMPORAL_HOST` |

**Bundled ForkReplay services:** `api` (FastAPI — OTLP ingress + REST + SSE), `ingest`,
`replay-worker`, `mock-gen-worker`, `export-worker`, `web` (Next.js standalone), and the
optional `scheduler` (partition/retention cron).

The compose default is **single-tenant** (a pre-created default workspace) even though the
multi-tenant core is always present.

---

## Target 2 — Helm (Kubernetes)

An umbrella chart at `deploy/helm/forkreplay/` composes the ForkReplay service workloads and
their backing dependencies. See [helm.md](../../deployment/helm.md) for the chart design and
`values.yaml` outline.

- Each backing dependency is either a **bundled subchart** (dev/test) or an **external
  endpoint** (recommended for production), toggled per-dependency in `values.yaml`.
- **ClickHouse is a required dependency with no disable option** — it is always either the
  bundled subchart or an external cluster pointed at via `CLICKHOUSE_*`; there is no
  `clickhouse.enabled: false` path. Temporal is likewise required.
- `DB_MODE` selects the control-plane Postgres source (`compose`-in-cluster subchart,
  `custom` external, or `supabase`).
- Secrets are supplied through `global.existingSecret` (or a secrets operator), never inlined
  into `values.yaml`.

---

## Target 3 — Terraform skeletons (AWS + Azure)

Infrastructure-as-code skeletons under `deploy/terraform/aws/` and `deploy/terraform/azure/`,
each wiring the same module set (network / postgres / clickhouse / object-store / queue /
redis / temporal / compute). See [terraform-aws.md](../../deployment/terraform-aws.md) and
[terraform-azure.md](../../deployment/terraform-azure.md).

| Component | AWS | Azure |
|-----------|-----|-------|
| Control-plane Postgres (`DB_MODE=custom`) | RDS for PostgreSQL | Azure Database for PostgreSQL |
| **ClickHouse** (**required**, no disable) | Self-managed on EC2/EKS | Self-managed on AKS/VMs |
| Object storage (`S3_*`) | S3 | Azure Blob via the S3-compatible layer |
| Ingest queue (`QUEUE_BACKEND`) | MSK or self-managed NATS | Self-managed NATS (Redis Streams alt) |
| SSE pub/sub (`REDIS_URL`) | ElastiCache for Redis | Azure Cache for Redis |
| Durable orchestration (`TEMPORAL_*`) | Self-managed Temporal on EKS/ECS | Self-managed Temporal on AKS |
| Services + web | EKS / ECS | AKS |

There is **no managed AWS/Azure ClickHouse service**, so ClickHouse is self-managed on both —
required, never optional. The modules emit the same environment contract as `.env.example`;
endpoints become Terraform outputs wired into the compute tier, and secrets live in AWS
Secrets Manager / Azure Key Vault (referenced by ARN / Key Vault reference), never in
committed `.tfvars`.

---

## Variable surfaces (the deploy-time configuration contract)

The authoritative variable **names** live in [`.env.example`](../../../.env.example); the
full reference is [configuration.md](../../deployment/configuration.md). The load-bearing
surfaces every target must expose:

| Surface | Values / form | Selects |
|---------|---------------|---------|
| `DB_MODE` | `supabase` \| `custom` \| `compose` | Control-plane Postgres source (control plane only; ClickHouse unaffected) |
| `QUEUE_BACKEND` | `nats` \| `redis` | Ingest queue backend (NATS primary, Redis Streams alternative) |
| `S3_*` | `S3_ENDPOINT`, `S3_REGION`, `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY`, `S3_BUCKET_FRAMES`, `S3_BUCKET_BLOBS` | S3-compatible object store (MinIO / AWS S3 / Azure Blob) |
| `REDIS_URL` | connection URL (treat as secret) | Redis used for SSE pub/sub |
| `TEMPORAL_*` | `TEMPORAL_HOST`, `TEMPORAL_NAMESPACE`, optional `TEMPORAL_TLS_CERT` / `TEMPORAL_TLS_KEY` | Temporal frontend + namespace + optional mTLS |

Adjacent pluggable surfaces that the abstraction layers also read:
`LLM_PROVIDER` (`openrouter` \| `openai` \| `anthropic` \| `ollama`), `EMAIL_BACKEND`
(`smtp` \| `resend` \| `console`), GoTrue `GOTRUE_*`, and `CLICKHOUSE_*` (required in every
mode). See [abstraction-layers.md](./abstraction-layers.md) for how each variable selects a
backend behind a stable interface. All example values are `${PLACEHOLDER}` markers — never
commit real secrets.

---

## Where to go next

- [abstraction-layers.md](./abstraction-layers.md) — the interfaces that keep these backends pluggable
- [docs/deployment/architecture.md](../../deployment/architecture.md) — self-host topology + environment contract
- [docs/deployment/docker-compose.md](../../deployment/docker-compose.md) / [helm.md](../../deployment/helm.md) / [terraform-aws.md](../../deployment/terraform-aws.md) / [terraform-azure.md](../../deployment/terraform-azure.md)

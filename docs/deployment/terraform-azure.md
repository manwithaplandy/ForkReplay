# ForkReplay — Terraform (Azure) Deployment

Infrastructure-as-code skeleton for running ForkReplay on Azure.

> **Status:** This page describes the intended **module design**. The Terraform modules
> (under `deploy/terraform/azure/`) are authored in a future implementation phase; they are
> not yet shipped. `terraform validate` / `terraform plan` become a CI gate when the modules
> exist.

> **ClickHouse is required** and is **self-managed** on Azure — there is no Azure-managed
> ClickHouse service. Plan capacity for it from the start; it is not optional.

---

## Module layout

```
deploy/terraform/azure/
├── main.tf                # wires the modules below
├── variables.tf
├── outputs.tf
└── modules/
    ├── network/           # VNet, subnets, NSGs
    ├── postgres/          # Azure Database for PostgreSQL — DB_MODE=custom
    ├── clickhouse/        # self-managed ClickHouse on AKS/VMs (REQUIRED)
    ├── object-store/      # Azure Blob via the S3-compatible layer
    ├── queue/             # self-managed NATS (or Azure Cache for Redis Streams)
    ├── redis/             # Azure Cache for Redis (SSE pub/sub)
    ├── temporal/          # self-managed Temporal on AKS
    └── compute/           # AKS for the ForkReplay services + web
```

---

## Component → Azure mapping

| Component | Azure resource | Required? | Notes |
|-----------|----------------|-----------|-------|
| Control-plane Postgres | **Azure Database for PostgreSQL** | required | `DB_MODE=custom`; PITR available |
| **ClickHouse** | **Self-managed on AKS or VMs** | **required** | No managed Azure ClickHouse; size storage/IO deliberately |
| Object storage | **Azure Blob** via the S3-compatible layer | required | ForkReplay speaks S3; use an S3-compatible gateway/config in front of Blob. Apply immutability (WORM) policy to the audit-archive container |
| Ingest queue | Self-managed **NATS** on AKS | required | `QUEUE_BACKEND=nats`; Redis Streams is the lighter alternative |
| SSE pub/sub | **Azure Cache for Redis** | required | Backs FastAPI SSE |
| Durable orchestration | **Self-managed Temporal** on AKS | required | Or an external Temporal cluster |
| Services + web | **AKS** | required | Runs the 5 Python services + `apps/web` |
| Auth | GoTrue container on AKS | required | Validates JWTs everywhere |
| LLM provider | External (`LLM_PROVIDER`) | required | OpenRouter / OpenAI / Anthropic / self-hosted Ollama |
| Observability | Optional OTLP sink | optional | Self-managed collector or external endpoint |

ForkReplay's object-storage abstraction is **S3-compatible**; on Azure you front Azure Blob
with an S3-compatible gateway (or compatible configuration) so `S3_ENDPOINT` and the `S3_*`
credentials resolve against Blob. GoTrue and the ForkReplay services run as workloads on AKS.

---

## Configuration

The modules emit the same environment contract as [`.env.example`](../../.env.example) —
endpoints (`DATABASE_URL`, `CLICKHOUSE_URL`, `S3_ENDPOINT`, `NATS_URL`, `REDIS_URL`,
`TEMPORAL_HOST`) become Terraform outputs wired into the AKS pod environment. Secrets
(`POSTGRES_PASSWORD`, `CLICKHOUSE_PASSWORD`, `S3_SECRET_ACCESS_KEY`, `GOTRUE_JWT_SECRET`,
`LLM_API_KEY`, optional `KEK_AGE_IDENTITY_FILE`) belong in **Azure Key Vault**, referenced by
the AKS CSI Secrets Store driver — never in `.tfvars` committed to the repo. See
[configuration.md](./configuration.md).

Recommended provider hygiene:

- Use Workload Identity / managed identities for Blob and Key Vault access (least privilege).
- Keep ClickHouse and Postgres on private subnets; expose only the compute tier via the
  ingress / Application Gateway.
- Ensure the ingress allows long-lived, unbuffered SSE connections from `api`.

---

## Validation (future gate)

When the modules are authored, CI will run `terraform fmt -check`, `terraform validate`, and
a `terraform plan` against a throwaway workspace. Until then this document is the design
contract.

For AWS, see [terraform-aws.md](./terraform-aws.md). For a non-cloud or in-cluster option,
see [helm.md](./helm.md).

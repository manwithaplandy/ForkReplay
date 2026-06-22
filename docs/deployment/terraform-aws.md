# ForkReplay — Terraform (AWS) Deployment

Infrastructure-as-code skeleton for running ForkReplay on AWS.

> **Status:** This page describes the intended **module design**. The Terraform modules
> (under `deploy/terraform/aws/`) are authored in a future implementation phase; they are not
> yet shipped. `terraform validate` / `terraform plan` become a CI gate when the modules
> exist.

> **ClickHouse is required** and is **self-managed** on AWS — there is no AWS-managed
> ClickHouse service. Plan capacity for it from the start; it is not optional.

---

## Module layout

```
deploy/terraform/aws/
├── main.tf                # wires the modules below
├── variables.tf
├── outputs.tf
└── modules/
    ├── network/           # VPC, subnets, security groups
    ├── postgres/          # RDS for PostgreSQL (or self-managed) — DB_MODE=custom
    ├── clickhouse/        # self-managed ClickHouse on EC2/EKS (REQUIRED)
    ├── object-store/      # S3 buckets (frames, blobs, audit archive)
    ├── queue/             # MSK (Kafka) or self-managed NATS
    ├── redis/             # ElastiCache for Redis (SSE pub/sub)
    ├── temporal/          # self-managed Temporal on EKS/ECS
    └── compute/           # EKS or ECS for the ForkReplay services + web
```

---

## Component → AWS mapping

| Component | AWS resource | Required? | Notes |
|-----------|--------------|-----------|-------|
| Control-plane Postgres | **RDS for PostgreSQL** (or self-managed on EC2) | required | `DB_MODE=custom`; PITR available via RDS |
| **ClickHouse** | **Self-managed on EC2 or EKS** | **required** | No managed AWS ClickHouse; size storage/IO deliberately |
| Object storage | **S3** | required | Frames/exports/audit; enable **Object Lock** on the `committed=true/` prefix for the audit archive |
| Ingest queue | **MSK** or self-managed NATS on EC2/EKS | required | `QUEUE_BACKEND=nats`; Redis Streams is the lighter alternative |
| SSE pub/sub | **ElastiCache for Redis** | required | Backs FastAPI SSE |
| Durable orchestration | **Self-managed Temporal** on EKS/ECS | required | Or an external Temporal cluster |
| Services + web | **EKS** (recommended) or **ECS** | required | Runs the 5 Python services + `apps/web` |
| Auth | GoTrue container on EKS/ECS | required | Validates JWTs everywhere |
| LLM provider | External (`LLM_PROVIDER`) | required | OpenRouter / OpenAI / Anthropic / self-hosted Ollama |
| Observability | Optional OTLP sink | optional | Self-managed collector or external endpoint |

GoTrue and the ForkReplay services run as workloads on the EKS/ECS compute tier; the table
lists the managed AWS resources you provision around them.

---

## Configuration

The modules emit the same environment contract as [`.env.example`](../../.env.example) —
endpoints (`POSTGRES_HOST`/`DATABASE_URL`, `CLICKHOUSE_URL`, `S3_ENDPOINT`, `NATS_URL`,
`REDIS_URL`, `TEMPORAL_HOST`) become Terraform outputs wired into the compute tier's task/pod
environment. Secrets (`POSTGRES_PASSWORD`, `CLICKHOUSE_PASSWORD`, `S3_SECRET_ACCESS_KEY`,
`GOTRUE_JWT_SECRET`, `LLM_API_KEY`, optional `KEK_AGE_IDENTITY_FILE`) belong in **AWS Secrets
Manager** (or SSM Parameter Store), referenced by ARN — never in `.tfvars` committed to the
repo. See [configuration.md](./configuration.md).

Recommended provider/IAM hygiene:

- Scope S3 access to the ForkReplay buckets with least-privilege IAM roles (IRSA on EKS).
- Keep ClickHouse and RDS in private subnets; expose only the compute tier via an ALB.
- Use ALB idle-timeout settings compatible with long-lived SSE connections.

---

## Validation (future gate)

When the modules are authored, CI will run `terraform fmt -check`, `terraform validate`, and
a `terraform plan` against a throwaway workspace. Until then this document is the design
contract.

For Azure, see [terraform-azure.md](./terraform-azure.md). For a non-cloud or in-cluster
option, see [helm.md](./helm.md).

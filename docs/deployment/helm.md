# ForkReplay — Helm (Kubernetes) Deployment

Running ForkReplay on any Kubernetes cluster via an umbrella Helm chart.

> **Status:** This page describes the intended chart **design**. The chart itself (under
> `deploy/helm/`) is authored in a future implementation phase; it is not yet shipped.

> **ClickHouse is required.** It is a required subchart (or an external endpoint you point
> at) in every Helm install — never optional.

---

## Chart layout

An umbrella chart composes the ForkReplay services and their backing dependencies:

```
deploy/helm/forkreplay/            # umbrella chart
├── Chart.yaml                     # declares dependencies (subcharts) below
├── values.yaml                    # top-level values (see outline)
├── templates/                     # ForkReplay service workloads
│   ├── api-deployment.yaml        # FastAPI: OTLP ingress + REST + SSE
│   ├── ingest-deployment.yaml
│   ├── replay-worker-deployment.yaml
│   ├── mock-gen-worker-deployment.yaml
│   ├── export-worker-deployment.yaml
│   ├── scheduler-cronjob.yaml     # optional partition/retention
│   ├── web-deployment.yaml        # Next.js standalone
│   ├── ingress.yaml
│   ├── secrets.yaml               # references existingSecret by default
│   └── configmap.yaml
└── charts/                        # vendored / dependency subcharts
```

### Dependencies (subcharts or external)

| Dependency | Required? | Bundled subchart | External option |
|------------|-----------|------------------|-----------------|
| **ClickHouse** | **Required** | yes (subchart) | external endpoint via `CLICKHOUSE_*` |
| PostgreSQL | required (control plane) | yes (subchart) | external via `DB_MODE=custom`/`supabase` |
| GoTrue | required | yes | external (Supabase Auth) |
| S3 object storage | required | MinIO subchart | external S3 via `S3_*` (recommended for prod) |
| NATS | required (or Redis) | yes | external; or `QUEUE_BACKEND=redis` |
| Redis | required | yes | external (managed Redis) |
| Temporal | required | yes | external Temporal cluster |

For production, point Postgres, ClickHouse, S3, Redis, and Temporal at managed/HA endpoints
and disable the corresponding bundled subcharts.

---

## `values.yaml` outline

```yaml
global:
  image:
    registry: ${REGISTRY}
    tag: ${VERSION}
  # Provide secrets via an existing Kubernetes Secret rather than inline values.
  existingSecret: forkreplay-secrets    # GOTRUE_JWT_SECRET, POSTGRES_PASSWORD,
                                        # CLICKHOUSE_PASSWORD, S3_SECRET_ACCESS_KEY, etc.

dbMode: custom                          # compose | custom | supabase

postgresql:
  enabled: false                        # use the bundled subchart, or:
  external:
    host: ${POSTGRES_HOST}
    database: forkreplay

clickhouse:
  enabled: true                         # REQUIRED — bundled subchart...
  external:                             # ...or point at an external cluster
    url: ${CLICKHOUSE_URL}

objectStore:
  minio:
    enabled: true                       # dev; disable and use external S3 in prod
  s3:
    endpoint: ${S3_ENDPOINT}
    bucketFrames: forkreplay-frames
    bucketBlobs: forkreplay-frames-blobs

queue:
  backend: nats                         # nats | redis
  nats:
    enabled: true

redis:
  enabled: true

temporal:
  enabled: true

llm:
  provider: openrouter                  # openrouter | openai | anthropic | ollama

email:
  backend: smtp                         # smtp | resend | console

kek:
  provider: none                        # none | age | libsodium

services:
  api: { replicas: 2 }
  ingest: { replicas: 2 }
  replayWorker: { replicas: 2 }
  mockGenWorker: { replicas: 1 }
  exportWorker: { replicas: 1 }
  web: { replicas: 2 }

ingress:
  enabled: true
  host: ${WEB_PUBLIC_URL}
```

The full set of variable names is the same contract as
[`.env.example`](../../.env.example); see [configuration.md](./configuration.md). Secrets are
supplied through `global.existingSecret` (or your secrets operator), never committed to
`values.yaml`.

---

## Notes

- **Workers vs HTTP services:** `api` and `web` sit behind the Ingress; the workers
  (`ingest`, `replay-worker`, `mock-gen-worker`, `export-worker`) are queue/Temporal-driven
  and need no inbound Ingress.
- **SSE:** ensure your Ingress controller does not buffer responses on the SSE path served by
  `api`, and allows long-lived connections.
- **Scaling:** scale `replay-worker` for branch throughput and `ingest` for span volume
  independently.
- **Validation gate:** `helm lint` and `helm template` are a future CI gate added when the
  chart is authored.

For cloud-managed backing services instead of in-cluster subcharts, see
[terraform-aws.md](./terraform-aws.md) and [terraform-azure.md](./terraform-azure.md).

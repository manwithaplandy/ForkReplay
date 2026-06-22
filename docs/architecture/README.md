# ForkReplay — Architecture Deliverables Index

This directory holds the **technical-architecture** design sketches. Together they
convert the locked product direction (`../../implementation-readiness-spec.md`,
`../../agent-trace-fork-prd.md`) into implementable, service-level designs. This work was
tracked by the **Architecture & Milestone Breakdown** epic (issue **#1**) and
**gates the Phase 1 schema lock**.

> **Scope reminder.** ForkReplay is an **open-source, self-hostable** product (Apache-2.0).
> The control-plane Postgres is pluggable (`DB_MODE=supabase|custom|compose`), but
> **ClickHouse is required in every mode** — it is the columnar span/frame analytics store
> and has no Postgres substitute. The managed-SaaS layer (and its billing) were **removed**
> in the OSS pivot; see the "OSS V1 scope" section in [`../../AGENTS.md`](../../AGENTS.md).

## How to read this tree

These are **design sketches**, not shipped code. They pin contracts, ownership boundaries,
schemas, and the build sequence *before* product code is written so the Phase 1 schema lock
has something stable to freeze against. Runtime topology (how the pieces wire together) lives
in [`../deployment/architecture.md`](../deployment/architecture.md); the docs here focus on
ownership, contracts, and sequencing.

## Architecture artifacts

| Artifact | Issue | What it covers |
|----------|-------|----------------|
| [`service-responsibilities.md`](./service-responsibilities.md) | #2 | Per-service ownership boundaries (and explicit "does NOT own"), upstream/downstream edges, and required infra per container. |
| [`schemas/control-plane.md`](./schemas/control-plane.md) | #3 | Control-plane Postgres schema sketch — workspaces, members, traces, branches, frames, audit, `system_banners`, `WorkspaceLimits` — with RLS notes (billing tables removed). |
| [`schemas/clickhouse.md`](./schemas/clickhouse.md) | #3 | ClickHouse span/step/message/tool projection tables, row policies on `workspace_id`, and TTL/retention sketch (required analytics store). |
| [`db-mode-matrix.md`](./db-mode-matrix.md) | #3 | The `DB_MODE=supabase\|custom\|compose` matrix for the control plane, with the standing "ClickHouse is required regardless of `DB_MODE`" invariant. |
| [`api-surface/endpoint-inventory.md`](./api-surface/endpoint-inventory.md) | #4 | First REST/OpenAPI endpoint inventory plus the FastAPI OTLP ingress and FastAPI SSE surfaces. |
| [`orchestration/temporal-workflows.md`](./orchestration/temporal-workflows.md) | #5 | Temporal workflow lifecycle sketches for the branch loop — state machine, activities, signals/queries, worker pools (replaces the deprecated Cloudflare Workflows path). |
| [`sdk/python-package-outline.md`](./sdk/python-package-outline.md) | #6 | Python SDK package outline — explicit-capture core, decorator sugar, framework adapters, and `forkreplay-auto` (Python-only in V1; the TypeScript SDK is deprecated/off-roadmap for V1). |
| [`deployment-modes/deploy-outline.md`](./deployment-modes/deploy-outline.md) | #7 | The `deploy/` artifact outline (docker-compose / Helm / Terraform AWS+Azure) — authored in Phase 6, sketched here. |
| [`deployment-modes/abstraction-layers.md`](./deployment-modes/abstraction-layers.md) | #7 | The pluggable abstraction-layer interfaces — `AuthProvider`/GoTrue client, `ObjectStore`, `QueueConsumer`, Temporal workers, Redis SSE relay, FastAPI OTLP endpoint. |

> **Phasing note.** The execution-ready, phase-by-phase issue breakdown is tracked as the
> GitHub milestones (Phase 0–6) — each phase's issues carry scope, acceptance criteria,
> dependencies/blocks, and `phase:*`/`type:*` labels. The artifacts above are the
> design-sketch deliverables those phases execute against.

## Related canonical docs

- The GitHub milestones (Phase 0–6) — the build sequence these artifacts execute against.
- [`../../implementation-readiness-spec.md`](../../implementation-readiness-spec.md) — the object model, contracts, and acceptance gates.
- [`../../agent-trace-fork-prd.md`](../../agent-trace-fork-prd.md) — product requirements and scope.
- [`../../AGENTS.md`](../../AGENTS.md) "OSS V1 scope" — the OSS-pivot scope constraints (removed managed-SaaS layer + billing).
- [`../deployment/architecture.md`](../deployment/architecture.md) — runtime topology of the self-host stack.

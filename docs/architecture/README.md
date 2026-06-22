# ForkReplay — Architecture Deliverables Index

This directory holds the **technical-architecture & milestone-breakdown** artifacts
produced under Plan §11 — the "Immediate Next Artifact After This Plan." Together they
convert the locked product direction (`../../implementation-plan.md`,
`../../implementation-readiness-spec.md`, `../../agent-trace-fork-prd.md`) into
implementable, service-level designs and an execution-ready issue list. This work is
tracked by the **Architecture & Milestone Breakdown (§11)** epic (issue **#1**) and
**gates the Phase 1 schema lock**.

> **Scope reminder.** ForkReplay is an **open-source, self-hostable** product (Apache-2.0).
> The control-plane Postgres is pluggable (`DB_MODE=supabase|custom|compose`), but
> **ClickHouse is required in every mode** — it is the columnar span/frame analytics store
> and has no Postgres substitute. The managed-SaaS layer (and its billing) were **removed**
> in the OSS pivot; see the re-gate in [`../../READINESS-GATE-REPORT.md`](../../READINESS-GATE-REPORT.md).

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
| [`milestones/issue-list.md`](./milestones/issue-list.md) | #8 | The execution-ready milestone/issue list — every phase's issues with scope, acceptance criteria, dependencies/blocks, and suggested `phase:*`/`type:*` labels, plus the critical path and OSS-pivot re-gate. |

> **Sibling-artifact note.** `sdk/python-package-outline.md` (#6) and the two
> `deployment-modes/*` files (#7) are authored on parallel branches and may merge around the
> same time as this index; they are linked here by their known paths so this README is the
> single canonical entry point for the milestone-#1 architecture deliverables once all
> branches land.

## Related canonical docs

- [`../../implementation-plan.md`](../../implementation-plan.md) — the v0.4 build sequence (Phases 0–6) these artifacts execute against.
- [`../../implementation-readiness-spec.md`](../../implementation-readiness-spec.md) — the object model, contracts, and acceptance gates.
- [`../../READINESS-GATE-REPORT.md`](../../READINESS-GATE-REPORT.md) — the readiness verdict and the **OSS-pivot re-gate** (voided gates + new OSS gates).
- [`../deployment/architecture.md`](../deployment/architecture.md) — runtime topology of the self-host stack.

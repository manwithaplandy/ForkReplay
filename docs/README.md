# ForkReplay documentation

This directory holds the user-facing documentation for ForkReplay (concept overviews,
API reference exports, SDK quickstarts, runbook excerpts). The content here is the
canonical surface for anything we ship to customers or expose publicly.

## Drift coupling — the docs-update contract

The contract surface and the docs that describe it must move together. The following
globs are watched by `.github/workflows/docs-drift-check.yml`:

- `services/api/openapi/**` — API spec edits
- `packages/contracts/**` — shared schema edits
- `sdk/python/**` — SDK surface edits

If any PR touches one of those globs **without** also touching `docs/**`, the
`docs-drift-check` job fails. This is intentional: every contract change must be paired
with the matching user-facing doc update in the same PR.

Local agents should follow the `.claude/skills/docs-update.md` (or `.codex/skills/docs-update.md`)
skill, which:

1. Detects edits to the watched globs above.
2. Prompts the agent to draft a matching `docs/**` change before committing.
3. Scans the diff for V1 scope-creep terms ("SLA", "status page", "pen test",
   "TypeScript SDK", "TS SDK") and warns if any are introduced — these are
   explicit V1 non-goals per the root `AGENTS.md`.

## Layout

Built out today:

- [`architecture/`](./architecture/README.md) — technical-architecture design sketches:
  service responsibilities, control-plane + ClickHouse schemas, the API surface, Temporal
  workflows, the Python SDK outline, and the pluggable deployment-mode abstractions.

Filled in over Phase 1+:

- `concepts/` — frame model, branch model, replay determinism
- `api/` — rendered OpenAPI reference
- `sdk/python/` — quickstart, adapters, recipe cookbook
- `operations/` — runbooks excerpted from the internal ops handbook

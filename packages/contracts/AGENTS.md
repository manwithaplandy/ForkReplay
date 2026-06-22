# packages/contracts — shared OpenAPI + JSON schemas

Canonical schemas consumed by every service. Dual-published:

- JS package `@forkreplay/contracts` (via pnpm workspace) — consumed by `apps/web` and Workers
- Python package `forkreplay-contracts` (via uv workspace) — consumed by services and SDK

Schema changes here are gated by `.github/workflows/docs-drift-check.yml`: any edit under
`packages/contracts/**`, `services/api/openapi/**`, or `sdk/python/**` must be paired
with a matching `docs/**` edit in the same PR.

See ../../AGENTS.md or root AGENTS.md for project-wide context.

# @forkreplay/contracts / forkreplay-contracts

Canonical OpenAPI specs and JSON schemas shared across every ForkReplay service.

## Dual-publish strategy

This directory is published to two registries from a single source tree:

- **npm**: `@forkreplay/contracts` (via the pnpm workspace) — consumed by `apps/web`
  and the Cloudflare Workers in `workers/*` and `workflows/*`.
- **PyPI**: `forkreplay-contracts` (via the uv workspace) — consumed by `services/*`
  and the Python SDK in `sdk/python`.

Both packages ship the same `openapi/` and `schemas/` payload; only the build metadata
differs (`package.json` vs `pyproject.toml`). Treat any change here as breaking until
proven otherwise — every service depends on these contracts.

## Drift guard

Any edit under `packages/contracts/**`, `services/api/openapi/**`, or `sdk/python/**`
must be paired with a matching `docs/**` edit in the same PR; this is enforced by
`.github/workflows/docs-drift-check.yml`.

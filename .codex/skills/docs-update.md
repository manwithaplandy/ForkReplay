---
name: docs-update
description: Prompt to update docs/** when contracts or SDK surface changes, and to gate against OSS scope-creep / removed-component terms and committed secrets.
---

# docs-update skill

## When this skill triggers

Invoke this skill whenever the working tree (or pending diff) touches any of:

- `services/api/openapi/**`
- `packages/contracts/**`
- `sdk/python/**`

These three globs define the **public contract surface** of ForkReplay. Every change to
them must ship with a paired update under `docs/**`, because self-hosters and integrators
read `docs/**` to learn how to use the contract. The CI job
`.github/workflows/docs-drift-check.yml` enforces this and will fail the PR otherwise.

When you touch deployment design (`docs/deployment/**`, future `deploy/**`,
`.env.example`, `docs/operations/provisioning-template.md`), keep the env-var names and
component list consistent across all of them.

## What to do

1. **List the watched-glob files that changed.** Run `git status` (or inspect the diff)
   and enumerate every modified path under the three globs above.

2. **For each watched change, identify the docs page it affects.** A new endpoint in
   `services/api/openapi/**` needs a `docs/api/**` update. A new schema field in
   `packages/contracts/**` needs an entry in the corresponding concepts/reference page.
   A new SDK adapter or function in `sdk/python/**` needs a `docs/sdk/python/**` entry.

3. **Draft the docs change in the same commit / PR.** Do not commit the contract edit
   without the matching docs edit; the PR will fail CI.

4. **Run the OSS scope-creep / removed-component check.** Before finalizing the diff, scan
   newly-added lines for any of these substrings (case-insensitive). These name components
   removed in the OSS pivot, or V1 non-goals:

   - `Stripe`, `replay credit`, `credit pack` (billing/metering — removed; only operational
     `WorkspaceLimits` remain)
   - `Supabase Vault` (replaced by operator/workspace KEK via env/secret)
   - `Cloudflare Workflow`, `Cloudflare Queue`/`CF Queue` (replaced by Temporal / NATS)
   - `billing-batch-worker` (service removed from core)
   - `TypeScript SDK`, `TS SDK` (V1 non-goal — Python-only SDK)

   If any appear in **new** lines outside a clearly-removal/deprecation/changelog context,
   **stop and warn the user**: the diff is reintroducing a removed component or scope-creep
   and needs explicit approval. Quote the offending line(s). The CI job
   `removed-component-guard` enforces the same rule (overridable only with the
   `allow-removed-component` label by a maintainer).

5. **Run the secrets check.** Never let the diff add secrets or proprietary identifiers —
   credentials, API keys, JWTs, DB passwords, cloud account IDs, project refs, endpoints,
   or PII. Committed templates must use `${PLACEHOLDER}` markers. The CI `secret-scan`
   (gitleaks) job is the deterministic backstop; if it would flag the diff, fix it before
   committing. See `SECURITY.md`.

6. **Confirm with the user before committing** if anything in steps 1–5 looked ambiguous.

## What this skill does NOT do

- It does not modify code. It only checks coupling and prompts the agent.
- It does not bypass CI. `docs-drift-check`, `removed-component-guard`, and `secret-scan`
  remain the source of truth.
- It does not enforce style on docs themselves — that's a separate concern.

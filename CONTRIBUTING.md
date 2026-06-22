# Contributing to ForkReplay

Thanks for your interest in contributing! ForkReplay is open source under
[Apache-2.0](./LICENSE), and we welcome issues, pull requests, docs improvements, and
deployment-target feedback.

By participating you agree to abide by our [Code of Conduct](./CODE_OF_CONDUCT.md).

---

## > Never commit secrets or proprietary identifiers

This is the single most important rule in this repository.

**Do not commit** secrets, real account IDs, project refs, API keys, endpoints, tokens, or
operator PII — not in code, not in docs, not in fixtures, not in commit messages, and not in
example files. ForkReplay uses the `${PLACEHOLDER}` convention everywhere a real value would
otherwise appear (see [docs/operations/provisioning-template.md](./docs/operations/provisioning-template.md)
for the canonical example).

- Real values for a live deployment belong in **your secret manager** and in a local,
  gitignored runbook (e.g. `PROVISIONING.local.md`), never in this repo.
- Local environment values go in `.env.local`, which is gitignored. Only `.env.example`
  (placeholders only) is committed.
- If you discover a vulnerability or an accidentally committed secret, follow the disclosure
  process in [SECURITY.md](./SECURITY.md) — do not open a public issue for security reports.

PRs that introduce real secrets or identifiers will be rejected, and any exposed credential
must be rotated immediately.

---

## Local setup

ForkReplay is a polyglot monorepo: Python services + a Next.js web app, backed by
open-source data stores. The fastest path to a running stack is the bundled Docker Compose
environment:

```bash
git clone https://github.com/forkreplay/forkreplay.git
cd forkreplay
cp .env.example .env.local      # placeholders; local-dev defaults work out of the box
docker compose up
```

This brings up the full stack (control-plane Postgres, GoTrue, ClickHouse, MinIO, NATS,
Redis, Temporal, the five Python services, and web) with a single-tenant default workspace.
See [docs/deployment/docker-compose.md](./docs/deployment/docker-compose.md) for details.

> **ClickHouse is required** in every deployment mode — it is the columnar span/frame
> analytics store and has no Postgres substitute. The Compose stack bundles it; do not
> design a code path that assumes it can be omitted.

> **Status note:** The `deploy/docker-compose/docker-compose.yml`, Helm chart, and Terraform
> modules are authored in a future implementation phase. Until then the
> [docs/deployment/](./docs/deployment/) documents are the authoritative design and
> environment contract.

For service-specific setup (Python versions, package managers, test commands), read the
`AGENTS.md` in the relevant directory — see Coding conventions below.

---

## Monorepo layout

| Path | What it is |
|------|------------|
| `apps/web` | Next.js standalone workbench (deployable anywhere) |
| `services/api` | FastAPI control plane (also hosts the OTLP ingress endpoint) |
| `services/ingest` | OTel span → frame projection; consumes the ingest queue |
| `services/replay-worker` | Durable replay execution |
| `services/mock-gen-worker` | AI-mock generation |
| `services/export-worker` | Test-case + promptfoo export |
| `sdk/python` | `forkreplay-sdk` (PyPI) + framework extras |
| `packages/contracts` | Shared OpenAPI + JSON schemas |
| `docs/` | User-facing documentation (deployment, operations, concepts) |
| `deploy/*` | Compose / Helm / Terraform deployment artifacts (**authored in a future phase**) |

> The `services/billing-batch-worker`, `workers/otlp-gateway`, `workers/sse-relay`, and
> `workflows/cloudflare` paths are **deprecated** by the open-source pivot (slated for
> removal, not yet deleted). Do not add new work there; their roles are replaced by the
> FastAPI OTLP endpoint, FastAPI SSE + Redis pub/sub, and Temporal respectively. Billing
> is removed entirely in favor of operational `WorkspaceLimits`.

---

## Coding conventions

- Each top-level service directory has its own `AGENTS.md` with service-specific context
  (runtime, dependencies, test commands, conventions). **Read the root `AGENTS.md` plus the
  relevant service `AGENTS.md` before working in a sub-directory.**
- Match the style of the surrounding code: naming, comment density, and idiom.
- Keep environment-variable names consistent with
  [docs/deployment/configuration.md](./docs/deployment/configuration.md) and the
  provisioning template. If you add a config knob, document it in both.

---

## Docs-drift contract

The contract surface and the docs that describe it move together. The following globs are
watched by `.github/workflows/docs-drift-check.yml`:

- `services/api/openapi/**` — API spec edits
- `packages/contracts/**` — shared schema edits
- `sdk/python/**` — SDK surface edits

If a PR touches one of those globs **without** also touching `docs/**`, the
`docs-drift-check` job fails. This is intentional: every contract change must be paired with
the matching user-facing doc update in the same PR.

Local agents should follow the `.claude/skills/docs-update.md` (or
`.codex/skills/docs-update.md`) skill, which detects edits to the watched globs, prompts for
a matching `docs/**` change before committing, and scans the diff for known scope-creep terms.
See [docs/README.md](./docs/README.md) for the full description.

---

## Pull request process

1. **Open an issue first** for anything non-trivial, so we can agree on the approach before
   you invest time.
2. **Branch** from `main`. Keep PRs focused — one logical change per PR.
3. **Write tests** for new behavior and run the existing suite (see the relevant
   `AGENTS.md` for commands).
4. **Update docs** in the same PR when you touch a watched contract glob (see Docs-drift
   contract above).
5. **Sign off your commits** (see DCO below).
6. **Describe the change** clearly in the PR body: what, why, and how you tested it. Flag
   any scope expansion explicitly.
7. A maintainer will review. Address feedback by pushing follow-up commits to the same
   branch.

---

## Developer Certificate of Origin (DCO)

ForkReplay uses the [Developer Certificate of Origin](https://developercertificate.org/) as
its contribution agreement. **Sign off every commit** to certify that you wrote the patch (or
have the right to submit it) under the project's Apache-2.0 license:

```bash
git commit -s -m "Your commit message"
```

The `-s` flag adds a `Signed-off-by: Your Name <your.email@example.com>` trailer matching the
DCO. PRs whose commits are not signed off will be asked to amend before merge. (We use DCO
rather than a CLA — there is no separate agreement to sign.)

---

## Reporting bugs and requesting features

- **Bugs:** Open an issue with reproduction steps, your deployment target (Compose / Helm /
  Terraform-AWS / Terraform-Azure), your `DB_MODE`, and the relevant component versions.
  Redact all secrets and identifiers.
- **Features:** Open an issue describing the use case and the problem it solves before
  sending a PR.
- **Security:** Do **not** open a public issue. Follow [SECURITY.md](./SECURITY.md).

Thank you for helping make ForkReplay better!

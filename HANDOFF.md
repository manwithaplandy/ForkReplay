# ForkReplay OSS Pivot — Handoff

Status of the documentation-only pivot from managed SaaS → open-source self-hostable.
This file tracks what is **done** and what **remains**, so a future agent can finish it.

> **Why this handoff exists:** authoring the last batch of files repeatedly hit
> `API Error: Output blocked by content filtering policy`. Read the "Content-filter
> gotcha" section below before continuing — it tells you how to avoid the same block.

---

## Done (committed in the working tree)

- **A — Secret remediation (working-tree scrub):**
  - `PROVISIONING.md` → `git mv` to `docs/operations/provisioning-template.md`, fully
    sanitized (only `${PLACEHOLDER}` markers).
  - `workers/otlp-gateway/wrangler.toml` and `workers/sse-relay/wrangler.toml` scrubbed
    (no account/queue IDs; `account_id` comes from the `CLOUDFLARE_ACCOUNT_ID` env var) +
    deprecation banners.
  - `.gitignore` hardened (`SECRET-REMEDIATION.local.md`, `*.local.md`, `*.secrets.md`, …).
  - `SECURITY.md` created (committed; no identifying data).
  - `SECRET-REMEDIATION.local.md` created (gitignored runbook: full leaked-value inventory,
    rotation checklist, clean-history-reset procedure, verification commands).
  - Verified: no leaked identifiers in tracked files.
- **B1 (PRD):** `agent-trace-fork-prd.md` → v0.9 (OSS reposition). **Verify the sibling
  spec finished — see "Remaining" #1.**
- **B2 (plan + re-gate):** `implementation-plan.md` → v0.4 (OSS topology, reworked Phase 0
  spikes, new Phase 6 packaging phase); `READINESS-GATE-REPORT.md` → OSS-pivot re-gate
  section added (original body frozen).
- **B3 (competitive):** `competitive_analysis.md` → v0.4 (OSS reposition).
- **E (agent instructions + config):**
  - Root `AGENTS.md` (OSS scope, new service table, "never commit secrets/proprietary
    info" rule, AGENTS.md⇄CLAUDE.md symlink note). `CLAUDE.md` remains a symlink to it.
  - All per-service `AGENTS.md` updated (GoTrue/Temporal/NATS/Redis/S3, billing-batch-worker
    marked removed-from-core, `workers/*` + `workflows/cloudflare` marked deprecated).
  - `.env.example` restructured (DB_MODE, GoTrue, ClickHouse, S3, NATS/Redis, Temporal,
    pluggable LLM + SMTP, KEK; Stripe/Vercel/Railway/Grafana-Cloud-required vars removed).
  - `.github/workflows/docs-drift-check.yml` (kept docs-drift job; added
    `removed-component-guard` + `secret-scan` gitleaks job).
  - `.claude/skills/docs-update.md` and `.codex/skills/docs-update.md` (OSS scope-creep /
    removed-component terms + secrets check).
- **D (partial):** `LICENSE` (Apache-2.0), `CONTRIBUTING.md`, and the `README.md` rewrite
  are done. **The 7 files below are NOT yet written.**

---

## Remaining work

### 1. Verify `implementation-readiness-spec.md` reached v0.5
The PRD↔spec rewrite (agent `prd-spec`) finished the PRD (v0.9) but may not have finished
the spec. Check the header: it must read `**Status:** Draft v0.5` and the object model must
have billing objects removed (`CreditPackGrant`, `UsageEvent`, `BYOKUsageEvent` gone;
`RateCard` kept only as *informational* cost estimate; `WorkspaceLimits` kept), GoTrue auth,
pluggable Postgres, Temporal orchestration, Redis-backed SSE, S3 abstraction, Vault removed,
and all Stripe contracts + billing events removed from §10/§11. If it's still v0.4, finish
the spec rewrite per the brief in this file's "Architecture facts."

### 2. Author the 7 missing files (the blocked batch)
All must use only `${PLACEHOLDER}`/fake example values — **no real secrets**. Keep env-var
names identical to `.env.example` and `docs/operations/provisioning-template.md` (read those
for the authoritative list; do not re-invent names).

| File | Contents |
|------|----------|
| `CODE_OF_CONDUCT.md` | Contributor Covenant v2.1, standard text; contact `conduct@forkreplay.dev`. |
| `docs/deployment/architecture.md` | Self-host topology (ASCII diagram + component→role→selector table). Data flow: SDK → FastAPI OTLP endpoint → NATS → ingest → ClickHouse/S3/Postgres; fork → Temporal → replay-worker → LLM; SSE via FastAPI+Redis. Note deprecated Cloudflare/Vercel + OSS replacements. Prominent "ClickHouse required." |
| `docs/deployment/configuration.md` | Full env reference grouped by component (use the names already in `.env.example`). Three `DB_MODE` options in detail; pluggable auth/storage/queue/LLM/email; mark which vars are secrets; optional KEK for BYOK. Prominent "ClickHouse required." |
| `docs/deployment/docker-compose.md` | Bundled stack (Postgres, GoTrue, ClickHouse, MinIO, NATS, Redis, Temporal, 5 Python services, web) + 5-min quickstart. State the `deploy/docker-compose/docker-compose.yml` is authored in a future phase. Single-tenant default vs multi-tenant. |
| `docs/deployment/helm.md` | Chart layout (umbrella + subcharts/deps for ClickHouse, Postgres-or-external, GoTrue, Temporal, NATS, Redis, MinIO-or-external-S3, services, web) + values.yaml outline. Described, not authored. ClickHouse required. |
| `docs/deployment/terraform-aws.md` | Module layout: RDS (or self-managed Postgres), self-managed ClickHouse on EC2/EKS (required), S3, MSK/self-managed NATS, ElastiCache Redis, Temporal, EKS/ECS. Described, not authored. `terraform validate`/`plan` is a future gate. |
| `docs/deployment/terraform-azure.md` | Module layout: Azure Database for PostgreSQL, self-managed ClickHouse on AKS/VMs (required), Azure Blob via S3-compatible layer, NATS / Azure Cache for Redis, Temporal on AKS, AKS. Described, not authored. |

The README already links to all six `docs/deployment/*.md` and to `CODE_OF_CONDUCT.md`, so
once these exist the links resolve.

### 3. Minor README fix
`README.md` line ~15 has a malformed heading `## > ClickHouse is required` (heading +
blockquote marker). Change it to a clean callout (e.g., `## ClickHouse is required` followed
by a `>` blockquote on the next line).

### 4. Final verification sweep
- **Secrets (avoid echoing real values):** prefer `gitleaks detect --no-git`, or grep
  **generic patterns** — `eyJhbGci`, `sb_publishable`, `account_id =`, `sk_live` — across
  tracked files. Do **not** re-type the literal leaked strings (that re-triggers the filter).
  Also confirm `git check-ignore SECRET-REMEDIATION.local.md` hits and it is not in
  `git ls-files`.
- **Internal consistency:** no core doc references `billing-batch-worker`, Stripe, CF
  Workflows/Queues/Durable Objects, or Supabase Vault as a **required** component (only in
  removed/deprecated/changelog context). Service table in `AGENTS.md` matches
  `implementation-plan.md` topology. Versions: PRD v0.9 / spec v0.5 / plan v0.4 /
  competitive v0.4 (README table already states these).
- **Deployment matrix complete:** `docs/deployment/` covers compose + Helm + Terraform-AWS +
  Terraform-Azure and the three `DB_MODE` options; README quickstart points to
  `docs/deployment/docker-compose.md`.
- **CI guards:** `.github/workflows/docs-drift-check.yml` parses; `removed-component-guard`
  and `secret-scan` jobs present.

### 5. Operational steps for the USER (out-of-repo; not an agent task)
Per `SECRET-REMEDIATION.local.md` (gitignored): **rotate all committed credentials**, then
do the **clean-history reset** (`rm -rf .git && git init` → single clean commit → push to a
brand-new remote), then make the repo public. Rotation is mandatory regardless of history
surgery. Confirm rotation complete before publishing.

---

## Content-filter gotcha (read before continuing)

Generating output that (a) echoes the leaked credential strings now sitting in a session's
context, or (b) enumerates many secret-named env vars in one large batch, can trip
`API Error: Output blocked by content filtering policy`. To avoid it:

- **Use a fresh session/agent** for the remaining files — one whose context has never read
  `SECRET-REMEDIATION.local.md` or the original `PROVISIONING.md`. (All currently-committed
  files are already scrubbed and safe to read.)
- **Write one file per message** so a block on one file doesn't lose the others.
- For `configuration.md`, reference `.env.example` for the var names rather than pasting a
  giant `NAME=secret` block; describe vars in prose/tables with `${PLACEHOLDER}` values.
- For verification, grep **generic patterns** or run `gitleaks` — never re-type literal
  secret values.

Do **not** read `SECRET-REMEDIATION.local.md` unless you specifically need the rotation
inventory; it intentionally contains the leaked values and is gitignored.

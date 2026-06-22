---
name: complete-milestone
description: >-
  Use when the user wants to complete, finish, deliver, ship, or close out an
  entire GitHub milestone or project phase — taking every open issue in a
  milestone from open to merged. Triggers include "knock out milestone N",
  "finish Phase 0", "get the whole milestone merged", "complete all the issues
  in the milestone", or naming a milestone/phase with intent to drive all of its
  issues to done. Invoke even when the user does not say the word "skill".
---

# complete-milestone

Take a **whole GitHub milestone** from open issues to merged PRs, fully
autonomously, without lowering the bar: strict red→green→refactor TDD, an
objective validation per issue, thorough documentation, independent review,
live validation, and clean merges that auto-close their issues.

You are the **orchestrator**. You do as little hands-on coding as possible — you
decompose, schedule, delegate, gate, and drive to completion. Almost all real
work is done by **subagents**, and the discipline for that work comes from the
**Superpowers skills** below. Parallelize everything that has no dependency
between the parts.

## The engine: Superpowers skills

This skill is an orchestration layer over Superpowers. It does **not** reinvent
TDD, review, or worktree management — it composes the skills that already do
those, applied across every issue in a milestone. Read each as you reach the
step that needs it (do not pre-load them all):

| Need | Skill |
|---|---|
| Turn a milestone / an issue's Goal+Deliverables into a task plan | **REQUIRED SUB-SKILL:** superpowers:writing-plans |
| An ambiguous issue — explore intent before building | **REQUIRED SUB-SKILL:** superpowers:brainstorming |
| Execute an issue's tasks with per-task review loops | **REQUIRED SUB-SKILL:** superpowers:subagent-driven-development |
| Run independent issues concurrently, one per worktree | **REQUIRED SUB-SKILL:** superpowers:dispatching-parallel-agents |
| Isolated workspace per issue | **REQUIRED SUB-SKILL:** superpowers:using-git-worktrees |
| TDD discipline inside every implementer | **REQUIRED SUB-SKILL:** superpowers:test-driven-development |
| Independent pre-merge review | **REQUIRED SUB-SKILL:** superpowers:requesting-code-review |
| Acting on review feedback rigorously (not performatively) | **REQUIRED SUB-SKILL:** superpowers:receiving-code-review |
| A test/CI failure — find the root cause before fixing | **REQUIRED SUB-SKILL:** superpowers:systematic-debugging |
| Proving an objective validation actually passed | **REQUIRED SUB-SKILL:** superpowers:verification-before-completion |
| Landing a finished branch as a PR | **REQUIRED SUB-SKILL:** superpowers:finishing-a-development-branch |

> **No `/goal`.** Earlier drafts drove each issue with the native `/goal`
> command; `/goal` cannot be invoked as a tool from a skill or subagent, so this
> skill uses Superpowers instead. The mapping is direct: `/goal`'s autonomous
> drive-to-done → subagent-driven-development's continuous execution; its TDD →
> test-driven-development; its "verifiable from output" check →
> verification-before-completion; its parallelism → dispatching-parallel-agents
> across one-worktree-per-issue.

## Autonomy contract

Run **fully autonomously**: plan → implement → document → review → remediate →
validate → merge → repeat, with no check-ins, **except** stop and ask the user
when (and only when) one of these is true:

- **No milestone is identified** or the argument matches 0 or >1 milestones.
- **A validation cannot be run in this environment** — it needs cloud
  credentials, a live external provider, a real cluster, `terraform apply`, or a
  manual step you cannot perform. This is the AGENTS.md rule: name the
  validation, say why it is blocked, and ask. **Never fake it or mark done.**
- **A decision is genuinely the user's** — an ambiguous requirement in an issue
  (resolve via superpowers:brainstorming first; only ask if it stays
  ambiguous), a scope/architecture choice not settled by the issue or repo docs,
  or an irreversible/destructive action.
- **A guardrail trips** — a change would commit a secret, reintroduce a removed
  component, or expand V1 scope (see Guardrails below).
- **You are stuck** — an implementer reports BLOCKED you cannot resolve, or a PR
  cannot be made green/mergeable after the remediation cap (default 3 rounds).

Everything else: proceed. Do not ask "should I continue?" — continue. This
matches subagent-driven-development's continuous-execution rule.

## The loop, at a glance

1. **Resolve the milestone** and run preflight (`references/orchestration.md`).
2. **Plan** — delegate dependency analysis; build dependency-ordered **waves**
   and, per issue, a task plan (superpowers:writing-plans) and a validation
   strategy (`references/orchestration.md`).
3. **Execute a wave** — for each ready issue, in parallel and in its own
   worktree, run it to a `Closes #N` PR via subagent-driven-development + TDD,
   updating all affected docs (`references/issue-execution.md`).
4. **Review → remediate → validate → merge** each PR — independent review
   subagents, root-cause fixes, evidence-backed validation (incl. live browser
   validation for UI), then an autonomous squash-merge once every gate is green
   (`references/review-merge-validate.md`).
5. **Refetch & repeat** — merging unblocks the next wave. Loop until the
   milestone has **zero open issues** (the `type:epic` umbrella closes last).
6. **Close out** — verify every issue closed, close the epic/milestone, post a
   summary.

Track the run with a durable ledger (subagent-driven-development's
`.superpowers/sdd/progress.md` plus the live GitHub state) so it survives
compaction and is resumable — one entry per issue, plus the wave/milestone state.

## Step 1 — Resolve the milestone

The argument may be a number (`2`), a title substring (`"Phase 0"`), or a phase
label (`phase:0-spikes`). Resolve against the live list:

```bash
gh api 'repos/{owner}/{repo}/milestones?state=open' \
  --jq '.[] | {number, title, open_issues, closed_issues}'
```

- Exactly one match → use it.
- Zero or multiple matches, or no argument → **ask the user** which milestone
  (list the open milestones with their open-issue counts). This is the one
  expected up-front question.

## Step 2 — Preflight, then plan

Do not start coding until preflight passes and the plan exists. Both are detailed
in **`references/orchestration.md`**: confirm `gh` auth + write access + clean
tree on an up-to-date default branch; discover the merge method and the live
branch ruleset/protection (this repo gates `main` via a **ruleset** requiring
PRs — the classic protection endpoint 404s, so check rules too); discover the
**actual CI checks** (`docs-drift-check.yml` already runs three jobs); determine
whether the milestone touches the UI (`apps/web`, dev server `pnpm dev`). Then
delegate a **planning subagent** that reads every issue's Goal/Deliverables/
Exit-criteria, builds the dependency graph, identifies the `type:epic` umbrella,
classifies each issue's validation strategy, and — per issue — produces a task
plan with superpowers:writing-plans. Emit dependency-ordered **waves**.

## Step 3 — Execute waves (parallel, delegated, TDD)

For each wave, launch the ready issues **concurrently** (cap ~3–4) via
superpowers:dispatching-parallel-agents — **one git worktree per issue**
(superpowers:using-git-worktrees) so the parallel implementers share no state.
Each issue is taken to a focused `Closes #N` PR by applying
superpowers:subagent-driven-development to its task plan, with every implementer
following superpowers:test-driven-development and updating the docs the change
affects. Full protocol — worktree/branch conventions, how the implementer is
briefed, the documentation-is-part-of-Done matrix, and how a BLOCKED issue
surfaces — is in **`references/issue-execution.md`**.

## Step 4 — Review, remediate, validate, merge (parallel, delegated)

As each PR opens, run it through the gate in
**`references/review-merge-validate.md`**: independent review
(superpowers:requesting-code-review + the pr-review-toolkit agents, chosen by
change type) → remediation that acts on feedback rigorously
(superpowers:receiving-code-review) and roots out failures
(superpowers:systematic-debugging), looping until clean (cap 3) → CI watched
green → **live browser validation on the dev server for any UI change** → an
autonomous squash-merge via superpowers:finishing-a-development-branch's PR path
once every gate is green and verification-before-completion is satisfied.

PRs flow through this gate independently — do not barrier the whole wave on the
slowest PR.

## Step 5 — Loop until the milestone is empty

After merges, refetch the milestone. Merged PRs flip `blocked` issues to `ready`;
schedule the next wave. Repeat Steps 3–4 until `open_issues == 0` for everything
except the epic. Then close the epic (and the milestone if the team closes
milestones), and post a final summary comment on the epic: issues completed, PRs
merged, validations run, and anything escalated to the user.

## Guardrails (this repo)

Hard constraints from `AGENTS.md`/`CLAUDE.md`. A subagent that violates one has
failed the task — gate on them, do not paper over them.

- **Strict TDD, objective validation.** Every change is red→green→refactor with a
  machine-checkable validation you actually ran and observed pass
  (superpowers:test-driven-development + verification-before-completion). "Looks
  right" / "it compiles" is not a validation. If a validation can't run here,
  escalate (see Autonomy contract).
- **Never push to the default branch.** The `main` ruleset blocks direct pushes;
  one issue → one feature branch (in its own worktree) → one `Closes #N` PR.
  Merge only through the Step 4 gate.
- **No secrets, ever.** Public OSS repo. No credentials, keys, JWTs, passwords,
  cloud account IDs, project refs, endpoints, or PII — not in code, comments,
  fixtures, or examples. Use `${PLACEHOLDER}` in templates. The `secret-scan`
  (gitleaks) gate is the backstop; if it would flag the diff, fix it before
  merge — never disable a gate to land a change.
- **No OSS scope-creep / removed components.** Do not reintroduce
  billing/Stripe, the TypeScript SDK, Cloudflare Workflows/Queues,
  `billing-batch-worker`, Supabase Vault, etc. (the `removed-component-guard`
  gate enforces this). If an issue seems to require one, escalate as scope
  expansion.
- **Documentation is part of Done.** Every PR keeps docs thorough and current —
  `AGENTS.md` (edit the file, never the `CLAUDE.md` symlink) and any
  per-directory `AGENTS.md`, `README.md`, `docs/**`, and the planning docs when
  the change affects them. Contract changes (`services/api/openapi/**`,
  `packages/contracts/**`, `sdk/python/**`) must ship paired `docs/**` updates or
  `docs-drift-check` fails the PR.
- **Issues close via PRs.** Always link with `Closes #N` (or `Fixes #N`) so the
  merge closes the issue; carry the milestone and labels onto the PR.

## Reference files

- `references/orchestration.md` — preflight (incl. ruleset detection), the
  planning subagent, dependency/wave scheduling, concurrency, resumability, the
  stop-and-ask decision table.
- `references/issue-execution.md` — the per-issue engine: worktrees,
  subagent-driven-development + TDD applied to an issue's Deliverables,
  branch/PR conventions, the docs matrix, BLOCKED handling.
- `references/review-merge-validate.md` — review subagent selection, the
  remediation loop, CI-check discovery, browser validation on the dev server,
  and the autonomous merge gate.

# Issue execution — subagent-driven development per issue

How a single milestone issue goes from open to a focused, documented,
`Closes #N` PR. Every ready issue in a wave runs this independently and in
parallel, each in its own git worktree.

**REQUIRED SUB-SKILLS:** superpowers:using-git-worktrees,
superpowers:subagent-driven-development, superpowers:test-driven-development,
superpowers:writing-plans, superpowers:brainstorming. Read them; this file only
covers what is *milestone-specific* on top of them.

## The model: one issue = one SDD run in its own worktree

subagent-driven-development (SDD) executes a plan by dispatching a fresh
implementer subagent per task (each following TDD), with a spec+quality review
loop after each task and a whole-branch review at the end. An issue's
**Deliverables** are its tasks, so an issue maps onto exactly one SDD run.

Parallelism across a wave comes from superpowers:dispatching-parallel-agents:
the orchestrator launches the wave's independent issues **concurrently**, each in
its **own worktree on its own branch**. SDD's "never run implementers in parallel
— they conflict" rule is about one branch; issues on separate worktrees share no
state, which is exactly the independent-domains case dispatching-parallel-agents
is for. So: parallel **across** issues, SDD's sequential implement→review loop
**within** each issue.

If an issue is large enough that the orchestrator dispatching its implementer
subagents directly would serialize the wave, dispatch one **issue-lead subagent**
per issue that itself runs the SDD loop in its worktree. If your platform does
not allow a subagent to dispatch its own subagents, the issue-lead acts as the
implementer directly: it does TDD for each deliverable, self-reviews, commits,
and the **orchestrator** runs the independent review gate
(`references/review-merge-validate.md`) on the resulting branch. Either way the
implementing agent never reviews or merges its own work — that is a separate
subagent, per requesting-code-review.

## Worktree & branch isolation

Use superpowers:using-git-worktrees to create the workspace. Never run two issues
on the same branch or working copy.

- Branch prefix by type: `feat/` (feature), `fix/` (bug), `docs/` (docs),
  `infra/` (infra/spike), `test/` (testing), `chore/` (ci/build); name
  `<prefix>/<issue#>-<slug>`.
- The worktree is the cwd for that issue's implementers and its
  `pnpm install` / dev server, keeping parallel issues fully isolated.
- After the PR merges, the merge gate cleans the worktree up
  (finishing-a-development-branch handles provenance-safe removal).

## Briefing the implementer (from Goal/Deliverables/Exit-criteria)

Issues carry a structured body: **Goal**, **Deliverables**, **Exit criteria**,
a `Depends on:` / `Blocks: #N` block, and `Part of #N` (the epic). Turn it into
the implementer's brief — this is SDD's task brief plus the milestone specifics:

1. **Where it fits** — one line: this issue, its phase, the epic it rolls up to.
2. **The plan** — the task plan produced for this issue (superpowers:writing-plans
   over the Deliverables). One deliverable ≈ one task.
3. **TDD is mandatory** (superpowers:test-driven-development): for each task,
   write a failing test that pins the behavior and confirm it fails for the right
   reason, then the minimum code to pass, then refactor green. A bug fix starts
   with a reproducing test. No production code without a failing test first.
4. **The objective validation** — the issue's Exit criteria, expressed as the
   exact command(s) and expected result the implementer must run and show passing
   before claiming done (superpowers:verification-before-completion). Examples:
   `pytest services/ingest/tests/test_x.py -q`, `pnpm --filter ./apps/web lint`,
   a conformance suite, an HTTP status, a measured threshold.
5. **Docs are part of Done** (see matrix below) — list the docs files touched.
6. **Guardrails** — no secrets, no removed-component/scope-creep reintroductions.
7. **Output** — commit on the branch; the PR is opened with `Closes #N` carrying
   the milestone and the issue's `type:*` labels (the orchestrator may open the
   PR after the review gate, but the `Closes #N` linkage is non-negotiable).

Keep each PR **small and focused** — one issue, one PR. If an issue is genuinely
two unrelated changes, flag it; do not bundle unrelated work.

**Ambiguous issue?** Before planning, resolve intent with
superpowers:brainstorming. Only escalate to the user if it stays ambiguous after
that — do not guess a requirement into existence.

## Documentation is part of Done

A PR that changes behavior but not docs is incomplete. Map the change to docs:

| Change touches | Update |
|---|---|
| Public contract (`services/api/openapi/**`, `packages/contracts/**`, `sdk/python/**`) | Paired `docs/api/**`, `docs/sdk/python/**`, concepts/reference — **required**, `docs-drift-check` enforces it |
| Deployment design (`deploy/**`, `docs/deployment/**`, `.env.example`, provisioning template) | Keep env-var names + component list consistent across all of them |
| New/changed service behavior, config, or operability | `docs/operations/**`, the service's `AGENTS.md` |
| Architecture / scope / build-sequence decisions | `implementation-plan.md`, `implementation-readiness-spec.md`, `READINESS-GATE-REPORT.md`, `agent-trace-fork-prd.md` as relevant |
| Anything a new self-hoster/contributor must know | `README.md`, root `AGENTS.md` (edit the file — **never** the `CLAUDE.md` symlink) |

When in doubt, run the `docs-update` skill's logic over the diff before opening
the PR. Thorough, current docs are a completion criterion, not a nicety.

## PR conventions

- Body **must** contain `Closes #<N>` (or `Fixes #<N>`) so the merge closes the
  issue. Carry the milestone and the issue's `type:*` labels onto the PR.
- Title: conventional-commit style matching the branch prefix
  (`feat: …`, `fix: …`, `docs: …`).
- Body summarizes: what changed, the TDD test(s) added, the **exact objective
  validation command and its result** (verification-before-completion — paste
  evidence, don't assert), the docs updated, and any browser-validation evidence
  (added later by the validation step). One issue ↔ one PR.

## Outcomes an issue run can return

These mirror SDD's implementer statuses, lifted to the issue level:

- **completed** — branch pushed, validation shown passing with evidence, docs
  updated, `Closes #N` PR open. Hand to the review/merge gate.
- **blocked-needs-user** — a validation/decision requires the user (creds,
  cluster, ambiguous requirement that survived brainstorming, scope-creep).
  Surface it per the stop-and-ask table; do not merge or fake.
- **failed** — could not converge. Re-dispatch once with a tighter brief or a
  decomposed plan (SDD's BLOCKED handling); if it still fails, escalate per the
  remediation cap.

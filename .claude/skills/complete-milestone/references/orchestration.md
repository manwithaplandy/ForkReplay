# Orchestration — preflight, planning, scheduling

This is the orchestrator's playbook for everything before and around the per-issue
work: getting the environment safe to operate in, turning a milestone into a
dependency-ordered set of waves, running those waves with bounded concurrency,
staying resumable, and knowing exactly when to stop and ask the user.

## Preflight (run once, before any coding)

Gate the whole run on these. If any check needs a human, stop and ask.

1. **Auth & access.** `gh auth status` is logged in, and the token can write to
   the repo (open PRs, merge). `gh repo view --json nameWithOwner,defaultBranchRef,viewerPermission`
   — `viewerPermission` should be `WRITE`/`MAINTAIN`/`ADMIN`. Note the default
   branch (do not assume `main`).
2. **Clean starting point.** Working tree is clean (`git status --porcelain`
   empty) and the default branch is up to date (`git fetch` then compare with
   `@{u}`). If the tree is dirty, ask the user before touching anything — do not
   stash or discard their work.
3. **Merge method & protections — check rulesets, not just classic protection.**
   Discover how PRs merge:
   `gh api repos/{owner}/{repo} --jq '{squash:.allow_squash_merge, merge:.allow_merge_commit, rebase:.allow_rebase_merge}'`.
   The classic endpoint (`gh api '.../branches/<default>/protection'`) returns
   **404 "Branch not protected"** here because `main` is gated by a **repository
   ruleset**, which lives at a different endpoint — always check both:
   `gh api 'repos/{owner}/{repo}/rules/branches/<default>'`. This repo's ruleset
   (`enforcement: active`) blocks direct pushes (`update`/`creation`/`deletion`/
   `non_fast_forward`) and requires a `pull_request` with
   **`required_approving_review_count: 0`** and squash allowed. Net effect: you
   **cannot push to `main`** (always PR), but the PR author **can self-merge**
   once it is mergeable — no separate approver is needed, so autonomous merge is
   supported. Read the live `allowed_merge_methods` and required checks from the
   ruleset; prefer squash. Because 0 approvals are required, this skill's own
   gate (review-clean + CI-green + browser-validated) is the substantive merge
   guard — treat it as safety-critical and never weaken it.
4. **CI checks are discovered, not hardcoded.** The single
   `.github/workflows/docs-drift-check.yml` file **already** defines three live
   jobs — `docs-drift-check`, `removed-component-guard`, and `secret-scan
   (gitleaks)` — so expect a PR to be gated by all three from day one (a diff
   that reintroduces a removed component or trips gitleaks will fail). More jobs
   (tests, lint) may be added. After the first PR is up, read the actual checks
   with `gh pr checks <pr>` and gate on whatever is there. `AGENTS.md` names the
   *intended* gates — treat them as guidance, but the live `gh pr checks` list is
   ground truth.
5. **Dev server & UI surface.** The browser-validatable app is `apps/web`
   (Next.js); the dev server is `pnpm dev` (root) or
   `pnpm --filter ./apps/web dev`. Confirm dependencies install (`pnpm install`)
   and the server boots before you rely on it for validation. Determine whether
   the milestone touches the UI at all — many phases (e.g. infra spikes) do not,
   in which case browser validation is N/A for those issues.
6. **Subagents available.** This skill's engine is Superpowers, which needs
   subagent support (it dispatches implementers, reviewers, and parallel issue
   agents). Confirm the platform provides subagents; if not, the skill cannot run
   its parallel/review model — tell the user.

## Planning (delegate to a planning subagent)

Spawn one `Explore`/`Plan` subagent to produce the execution plan. It must not
write code — only read and analyze. Give it this brief:

- **Fetch every issue in the milestone** (open and closed, all pages — use the
  `--paginate` flag, the call does not auto-paginate without it):
  `gh api --paginate 'repos/{owner}/{repo}/issues?milestone=<n>&state=all&per_page=100'`.
  PRs are issues too — exclude anything with a `pull_request` field.
- **Read each issue's body.** Issues use a structured format with these exact
  sections: **Goal**, **Deliverables**, **Exit criteria**, a dependencies block
  (`Depends on:` / `Blocks: #N`), and `Part of #N` (the epic this rolls up to).
  Capture, per issue: number, title, type label
  (`type:spike|feature|infra|security|docs|sdk|testing|ci|epic`), `ready` vs
  `blocked`, `critical-path`, the Goal, the Deliverables, and the Exit criteria
  (which is the source of the objective validation).
- **Build the dependency graph.** Edges come from (a) the `blocked` label (the
  issue has unmet deps — do not start it in wave 1), (b) the explicit
  `Depends on: #N` lines (forward edges) and `Blocks: #N` lines (reverse edges —
  this issue must merge before #N starts) in the body, and (c) obvious ordering
  implied by Deliverables (e.g. a conformance suite depends on the abstraction it
  tests). When a dependency is implicit and uncertain, prefer to sequence
  conservatively rather than risk a broken parallel build.
- **Identify the `type:epic` umbrella** — the issue every child links to via
  `Part of #N` (and labelled `type:epic`). It tracks the whole phase, is closed
  **last** after all child issues merge, and is never implemented as a normal
  coding issue.
- **Classify each issue's validation strategy:**
  - `test-only` — backend/SDK/contracts; validate via the issue's tests + CI.
  - `ui` — touches `apps/web`; additionally requires live browser validation on
    the dev server.
  - `infra-spike` — terraform/helm/docker-compose/cloud/cluster work whose
    validation (`terraform apply`, a real cluster, provider creds) **may not be
    runnable in this environment**. Flag these now so the orchestrator knows to
    escalate rather than fake completion (CLAUDE.md rule).
- **Per issue, produce a task plan** with superpowers:writing-plans over the
  Deliverables (one deliverable ≈ one bite-sized task), so each issue's SDD run
  has a plan to execute. Keep these plan files on disk for the implementers.
- **Emit waves.** A topological grouping where every issue in a wave has all
  dependencies satisfied by earlier waves, so the wave can run in parallel.
  Output: ordered `waves: [[#a, #b], [#c], …]`, the epic number, and the
  per-issue `{type, validation_strategy, branch_prefix, depends_on, plan_path}`.

Record the plan as `TaskCreate` entries (one task per issue, grouped by wave) so
the run is visible and resumable. Because the run is fully autonomous, do **not**
pause for plan sign-off — but if planning reveals a milestone that is mostly
`infra-spike` work needing external creds, note up front that several issues will
likely escalate.

## Scheduling & concurrency

- Run **one wave at a time**; within a wave, run issues **concurrently** up to a
  cap (default **3–4**) via superpowers:dispatching-parallel-agents. The cap
  bounds token cost and local load from parallel issue agents and dev servers.
- Do **not** barrier a whole wave on its slowest issue. The moment an issue's PR
  is merged, refetch the milestone — a merge can flip a `blocked` issue to
  `ready` and let you start it without waiting for the rest of the wave.
- `critical-path` issues get priority within their wave (start them first; they
  gate the most downstream work).
- Keep one git worktree per in-flight issue (see `issue-execution.md`); never run
  two issues on the same branch or worktree.

## Resumability

This is a long run that may span context windows. Keep state durable:

- The **GitHub state is the source of truth** — open issues in the milestone,
  open PRs, and `Closes #N` links. On resume, re-derive what is left from
  `gh` rather than from memory.
- Mirror it in the task list (`TaskList`/`TaskUpdate`) and in
  subagent-driven-development's durable ledger
  (`.superpowers/sdd/progress.md`): `in_progress` issues have a branch/PR;
  `completed` issues have a merged PR that closed them. Trust the ledger and
  `gh`/`git log` over recollection after any compaction.
- On resume: refetch the milestone, reconcile open PRs to their issues, drop any
  stale worktrees for already-merged branches, and continue from the first wave
  that still has open issues.

## Stop-and-ask decision table

| Situation | Action |
|---|---|
| 0 or >1 milestones match the argument; or no argument | Ask which milestone (list open ones + counts). |
| Working tree dirty at preflight | Ask before altering — don't stash/discard. |
| Issue requirement ambiguous / under-specified | Resolve with superpowers:brainstorming first; only ask if it stays ambiguous (quote the issue text + the ambiguity). |
| Validation needs creds / cluster / `terraform apply` / manual step | Stop, name the validation, explain the block, ask. Don't fake. |
| Change would commit a secret | Stop; do not commit. Surface the line. |
| Change reintroduces a removed component / expands V1 scope | Stop; flag as scope expansion, ask for explicit approval. |
| PR can't be made green/mergeable after 3 remediation rounds | Stop; summarize what failed and ask for direction. |
| Implementer subagent reports BLOCKED you can't resolve | Read its report; if it's a user-decision, ask; else re-dispatch with more context or a more capable model (SDD's BLOCKED handling). |
| Anything else | Proceed autonomously. Do not ask "should I continue?". |

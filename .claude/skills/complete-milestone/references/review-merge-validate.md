# Review → remediate → validate → merge

Every PR passes through this gate before it merges. Each PR flows independently —
a PR that is clean, green, and validated merges while its siblings are still in
review. Do not barrier the whole wave here.

The gate is ordered so cheap, parallel checks run first and the irreversible step
(merge) runs last, only when every prior gate is green.

**REQUIRED SUB-SKILLS:** superpowers:requesting-code-review,
superpowers:receiving-code-review, superpowers:systematic-debugging,
superpowers:verification-before-completion,
superpowers:finishing-a-development-branch.

## 1. Review (parallel, independent subagents)

This is superpowers:requesting-code-review's whole-branch review, broadened with
ForkReplay's specialized reviewers. Dispatch the code-reviewer subagent from
requesting-code-review (its `code-reviewer.md` template, with `BASE_SHA` =
`git merge-base <default> HEAD` and `HEAD_SHA` = branch tip), **plus** the
pr-review-toolkit agents that match what the change touches — don't run all five
on a one-line docs fix:

| The PR changes… | Review subagents |
|---|---|
| Any code | `pr-review-toolkit:code-reviewer` (guideline/style/correctness vs AGENTS.md) |
| Error handling, fallbacks, try/except, network/IO | `pr-review-toolkit:silent-failure-hunter` |
| New/changed tests, or claims a validation | `pr-review-toolkit:pr-test-analyzer` (coverage, real assertions, TDD honored) |
| New/changed types, schemas, models, contracts | `pr-review-toolkit:type-design-analyzer` |
| Substantial new comments/docstrings/docs | `pr-review-toolkit:comment-analyzer` |

Run them concurrently (one message, multiple `Agent` calls). Give each the PR
number, the diff, and the instruction to focus on the changed lines. Collect
findings into one list, each tagged Critical / Important / Minor, with file:line.

**Reviewers are independent.** Do not use the subagent that wrote the code to
also approve it — the whole point is a separate perspective. The implementing
agent never reviews or merges its own PR.

## 2. Remediate (loop, capped)

If there are Critical/Important findings, dispatch a fix subagent to address them,
applying superpowers:receiving-code-review (verify each point with technical
rigor — implement the valid ones, push back with reasoning on the wrong ones;
never performative agreement) and superpowers:systematic-debugging for any test
or CI failure (find the root cause before fixing — don't paper over symptoms).
The fix subagent re-runs the issue's objective validation after the fix and
updates the PR. Then **re-review only what changed**. Loop until reviews are clean
or the cap (**3 rounds**) is hit. If still not clean at the cap, stop and ask the
user (stop-and-ask table) — do not merge a PR with unresolved Critical/Important
findings, and do not silence a finding by weakening the test or narrowing an
assertion.

Non-blocking findings: apply the cheap, clearly-correct ones; leave the rest as a
note. Don't spend unbounded rounds gold-plating.

## 3. CI green (discovered, not assumed)

After review is clean and the branch is pushed, watch the **actual** checks:

```bash
gh pr checks <pr> --watch
```

- Gate on every check GitHub reports. Today that is already three jobs —
  `docs-drift-check`, `removed-component-guard`, and `secret-scan (gitleaks)` —
  and lint/tests may appear as CI grows. Gate on whatever is live; don't
  hardcode and don't assume a green diff will pass the removed-component or
  gitleaks scans without checking.
- A failing check is a real failure: read the logs (`gh run view <id> --log-failed`),
  fix on the branch (loops back through review/remediate), re-push. Never merge
  red. Never disable a gate (e.g. the secret-scan) to land a change.
- If a check is stuck/queued for an external reason you can't resolve, surface it
  rather than bypassing it.

## 4. Browser validation (UI changes only — required when present)

If the PR touches `apps/web` (or otherwise changes user-visible behavior), it is
**not done until it has been validated live in a browser on a running dev
server.** Backend/contract/infra PRs skip this step (their validation is tests +
CI); do not stand up a browser for a pure-backend change.

1. **Stand up the dev server** from the PR's worktree:
   `pnpm install` (if needed) then `pnpm --filter ./apps/web dev` in the
   background. Wait until it serves (poll the local URL) before driving it.
2. **Drive the changed flow** with the `claude-in-chrome` tools (load them via
   ToolSearch first — `tabs_context_mcp`, `navigate`, `computer`, `read_page`,
   plus `read_console_messages`/`read_network_requests` for debugging). Open a
   **new tab**, exercise the specific user flow the issue describes, and confirm
   the acceptance behavior actually happens in the UI — not just that the page
   renders. Check the console for errors.
3. **Capture evidence** — a screenshot (or a `gif_creator` recording for a
   multi-step flow) of the working behavior — and attach/link it in a PR comment
   so the validation is auditable.
4. Tear the dev server down when done.

A UI PR that cannot be browser-validated here (e.g. it needs a backend or service
that isn't runnable in this environment) is a **blocked** outcome — surface it,
don't merge on the assumption it works.

## 5. Merge (autonomous, last)

This is superpowers:finishing-a-development-branch's "push and create PR" path,
driven to merge. The milestone autonomy contract has already chosen that path, so
do **not** present its interactive 1–4 menu — but keep its discipline: it
verifies tests before doing anything, and it never removes a worktree before the
merge succeeds.

Before merging, satisfy superpowers:verification-before-completion: you may only
claim a gate passed if you ran its command and read its output **in this session**
— reviews clean (no unresolved Critical/Important findings), every live CI check
green, browser validation done+evidence-attached for UI changes, the PR is
`MERGEABLE` (no conflicts), and the ruleset's requirements (PR present; 0 required
approvals here) are satisfied. Evidence before the merge, not assertions.

```bash
gh pr merge <pr> --squash --delete-branch
```

(Use a merge method the ruleset's `allowed_merge_methods` permits — discovered in
preflight; prefer squash.)

Then:

- **Confirm the issue closed.** `Closes #N` should auto-close it on merge into the
  default branch. Verify (`gh issue view <N> --json state`); if it's somehow
  still open, close it with a comment referencing the merged PR.
- **Clean up.** Remove the worktree and delete the branch via
  finishing-a-development-branch's provenance-safe cleanup (`cd` to the main repo
  root first; `git worktree remove` then `git worktree prune`; only remove
  worktrees this skill created).
- **Refetch the milestone.** A merge may flip `blocked` issues to `ready` —
  schedule them (back to the orchestrator's wave loop).
- **Update the task list** — mark the issue completed with its PR link.

If a conflict appears at merge time, rebase the branch on the latest default
branch (in its worktree), re-push, let CI re-run, and re-gate — don't force-merge
through a conflict or a red check.

## What never happens at this gate

- No merge with unresolved Critical/Important review findings.
- No merge on a red or skipped required check; no disabling a gate to land code.
- No merge of a UI change that was never exercised in a browser.
- No self-review/self-merge by the subagent that wrote the code.
- No completion claim without fresh verification evidence
  (verification-before-completion) — "CI should be green" is not "CI is green".
- No committing secrets or scope-creep through the gate — the guardrails in
  `SKILL.md` apply here too.

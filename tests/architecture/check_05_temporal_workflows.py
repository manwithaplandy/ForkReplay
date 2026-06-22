#!/usr/bin/env python3
"""Checker for issue #5 — Temporal workflow lifecycle sketches for the branch loop.

Standalone (no pytest). Asserts that the orchestration design doc exists and
covers the branch-loop lifecycle in enough detail to implement Temporal workers:
the workflow state machine (incl. the FIRST step), activity boundaries with
retry/idempotency, signals/queries (cancel + resume), WorkspaceLimits-bounded
timeouts/heartbeats, the FastAPI SSE + Redis progress path (Last-Event-ID resume),
the three worker pools (replay-worker / mock-gen-worker / export-worker), and the
note that this design replaces the deprecated Cloudflare Workflows path.

Usage:
    python3 tests/architecture/check_05_temporal_workflows.py

Exit 0 + "PASS" on success; prints missing items and exits 1 on failure.
Specific but not brittle: case-insensitive substring checks, grouped with
OR-alternatives where wording can reasonably vary.
"""

import os
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DOC_REL = "docs/architecture/orchestration/temporal-workflows.md"
DOC_PATH = os.path.join(REPO_ROOT, DOC_REL)


def _present(haystack, *needles):
    """True if every needle (case-insensitive) appears in haystack."""
    return all(n.lower() in haystack for n in needles)


def _any(haystack, *needles):
    """True if any needle (case-insensitive) appears in haystack."""
    return any(n.lower() in haystack for n in needles)


def main():
    failures = []

    if not os.path.isfile(DOC_PATH):
        print(f"FAIL: required doc is missing: {DOC_REL}")
        print("Create the doc to satisfy issue #5.")
        sys.exit(1)

    with open(DOC_PATH, "r", encoding="utf-8") as fh:
        raw = fh.read()
    text = raw.lower()

    if len(text.strip()) < 1500:
        failures.append(
            f"doc is too thin ({len(text.strip())} chars) — expected a thorough "
            "workflow design sketch"
        )

    # --- 1. Lifecycle / state-machine states ---------------------------------
    # create -> prepare -> execute step(s) (incl. first) -> mock-gen/LLM ->
    # redact/write -> progress emit -> complete/fail/cancel
    checks = [
        ("lifecycle state: create",
         lambda: _any(text, "create", "created")),
        ("lifecycle state: prepare",
         lambda: _any(text, "prepare", "prepare_context", "preparing")),
        ("lifecycle: execute step(s) loop",
         lambda: _present(text, "execute") and _any(text, "step", "steps")),
        ("lifecycle: the FIRST step is in the loop (no first-call bypass)",
         lambda: _any(text, "first step", "first model call", "including the first",
                      "incl. the first", "first call", "no first-call bypass")),
        ("lifecycle: mock-gen / LLM call",
         lambda: _any(text, "mock-gen", "mock gen", "generate_mock", "ai_mock",
                      "ai-mock") and _any(text, "llm", "call_llm", "model call",
                                          "model dispatch")),
        ("lifecycle: redact / write",
         lambda: _any(text, "redact", "redaction")
                 and _any(text, "write", "redact_and_write", "persist")),
        ("lifecycle: progress emit",
         lambda: _any(text, "progress")
                 and _any(text, "emit", "emit_progress", "publish")),
        ("lifecycle terminal: complete",
         lambda: _any(text, "complete", "completed")),
        ("lifecycle terminal: fail",
         lambda: _any(text, "fail", "failed", "failure")),
        ("lifecycle terminal: cancel",
         lambda: _any(text, "cancel", "cancelled", "cancellation")),
        ("lifecycle: paused/pause state present",
         lambda: _any(text, "pause", "paused")),
        ("state machine diagram / state list present",
         lambda: _any(text, "state machine", "```mermaid", "statediagram",
                      "state diagram", "-->", "->")),

        # --- 2. Activities + boundaries + idempotency + retry ----------------
        ("activities are named/enumerated",
         lambda: _present(text, "activit")
                 and _any(text, "prepare_context", "execute_step", "generate_mock",
                          "call_llm", "redact_and_write", "emit_progress")),
        ("workflow-decision vs side-effecting-activity boundary",
         lambda: _any(text, "workflow decision", "decision vs", "side-effect",
                      "side effect", "side-effecting", "activity boundar",
                      "deterministic")),
        ("idempotency keys / idempotent activities",
         lambda: _any(text, "idempoten")),
        ("retry policy / retry semantics",
         lambda: _present(text, "retry")
                 and _any(text, "retrypolicy", "retry policy", "backoff",
                          "workflow_step_retries", "retry max", "retry semantics")),

        # --- 3. Signals & queries --------------------------------------------
        ("signals concept present",
         lambda: _any(text, "signal")),
        ("cancel signal",
         lambda: _present(text, "cancel") and _any(text, "signal", "cancellation")),
        ("resume / pause-continue signal",
         lambda: _any(text, "resume", "pause/continue", "pause / continue",
                      "continue", "unpause")),
        ("query (status) present",
         lambda: _present(text, "quer")
                 and _any(text, "status", "progress query", "state query")),

        # --- 4. Timeouts/heartbeats bounded by WorkspaceLimits ---------------
        ("WorkspaceLimits referenced",
         lambda: "workspacelimits" in text),
        ("WorkspaceLimits: concurrency mapped",
         lambda: _any(text, "concurren")),
        ("WorkspaceLimits: depth mapped",
         lambda: _any(text, "depth", "max_branch_depth")),
        ("WorkspaceLimits: wall-clock mapped",
         lambda: _any(text, "wall-clock", "wall clock", "branch_wall_clock")),
        ("Temporal timeouts present",
         lambda: _present(text, "timeout")),
        ("heartbeat present",
         lambda: _any(text, "heartbeat")),

        # --- 5. Progress -> FastAPI SSE + Redis ------------------------------
        ("SSE referenced",
         lambda: "sse" in text),
        ("FastAPI referenced for SSE",
         lambda: "fastapi" in text),
        ("Redis pub/sub referenced",
         lambda: _present(text, "redis")
                 and _any(text, "pub/sub", "pubsub", "pub-sub", "publish")),
        ("Last-Event-ID resume referenced",
         lambda: _any(text, "last-event-id", "last event id", "lastevent")),
        ("channel naming / tenant (workspace) scoping for progress",
         lambda: _any(text, "channel")
                 and _any(text, "workspace", "tenant")),

        # --- 6. Worker pools / task queues -----------------------------------
        ("worker pool / task queue concept",
         lambda: _any(text, "task queue", "task-queue", "worker pool",
                      "worker-pool")),
        ("worker pool: replay-worker",
         lambda: _any(text, "replay-worker", "replay worker")),
        ("worker pool: mock-gen-worker",
         lambda: _any(text, "mock-gen-worker", "mock gen worker", "mock-gen worker")),
        ("worker pool: export-worker",
         lambda: _any(text, "export-worker", "export worker")),

        # --- Deprecated Cloudflare Workflows replacement note ----------------
        ("replaces deprecated Cloudflare Workflows path",
         lambda: _present(text, "cloudflare")
                 and _any(text, "deprecated", "replaces", "replaced", "supersed",
                          "legacy", "no longer", "instead of", "slated")),
    ]

    for label, fn in checks:
        try:
            ok = fn()
        except Exception as exc:  # defensive: a broken check is a failure
            ok = False
            label = f"{label} (check raised {exc!r})"
        if not ok:
            failures.append(label)

    if failures:
        print(f"FAIL: {DOC_REL} is missing {len(failures)} required item(s):")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)

    print("PASS: check_05_temporal_workflows")
    print(f"  doc: {DOC_REL} ({len(raw)} bytes)")
    print(f"  all {len(checks)} content checks satisfied:")
    print("    - branch/replay workflow state machine (create -> prepare -> "
          "execute step(s) incl. first -> mock-gen/LLM -> redact/write -> "
          "progress emit -> complete/fail/cancel/pause)")
    print("    - activities enumerated with workflow/activity boundary, "
          "idempotency keys, and retry policy")
    print("    - signals (cancel, resume/pause-continue) + status query")
    print("    - WorkspaceLimits (concurrency/depth/wall-clock) -> Temporal "
          "timeouts + heartbeats")
    print("    - progress -> FastAPI SSE + Redis pub/sub (Last-Event-ID resume, "
          "workspace-scoped channels)")
    print("    - worker pools / task queues: replay-worker, mock-gen-worker, "
          "export-worker")
    print("    - replaces the deprecated Cloudflare Workflows path")
    sys.exit(0)


if __name__ == "__main__":
    main()

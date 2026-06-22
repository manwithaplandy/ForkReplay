#!/usr/bin/env python3
"""Checker for issue #8 — milestone issue list suitable for execution.

Standalone (no pytest). Asserts that the execution-ready milestone/issue list
exists and covers all seven implementation-plan phases (Phase 0 spikes ->
Phase 6 packaging) with the right themes; that EACH phase carries the four
fileable-issue notions (scope, acceptance criteria, dependencies/blocks,
suggested labels); that there is a critical-path + OSS-pivot re-gate
subsection; and that Phase 0 spikes are marked as the entry point while the
Phase 1 schema lock is marked gated on the Architecture & Milestone Breakdown
epic (issue #1). Also asserts the architecture README index exists and links
the core architecture artifacts.

IMPORTANT scoping rule: this checker only asserts the EXISTENCE of files this
branch creates (issue-list.md, README.md). The issue-#6 SDK outline and issue-#7
deployment-mode docs are authored on parallel branches and may not be present on
disk here; for those, the checker only asserts that README *mentions/links*
their known paths as text.

Usage:
    python3 tests/architecture/check_08_milestone_list.py

Exit 0 + "PASS" on success; prints missing items and exits 1 on failure.
Specific but not brittle: case-insensitive substring checks, grouped with
OR-alternatives where wording can reasonably vary.
"""

import os
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

ISSUE_LIST_REL = "docs/architecture/milestones/issue-list.md"
README_REL = "docs/architecture/README.md"

ISSUE_LIST_PATH = os.path.join(REPO_ROOT, ISSUE_LIST_REL)
README_PATH = os.path.join(REPO_ROOT, README_REL)


def _present(haystack, *needles):
    """True if every needle (case-insensitive) appears in haystack."""
    return all(n.lower() in haystack for n in needles)


def _any(haystack, *needles):
    """True if any needle (case-insensitive) appears in haystack."""
    return any(n.lower() in haystack for n in needles)


def main():
    failures = []

    # ------------------------------------------------------------------ #
    # 0. Required files this branch creates must exist.
    # ------------------------------------------------------------------ #
    if not os.path.isfile(ISSUE_LIST_PATH):
        print(f"FAIL: required doc is missing: {ISSUE_LIST_REL}")
        print("Create the milestone issue list to satisfy issue #8.")
        sys.exit(1)

    if not os.path.isfile(README_PATH):
        print(f"FAIL: required doc is missing: {README_REL}")
        print("Create the architecture README index to satisfy issue #8.")
        sys.exit(1)

    with open(ISSUE_LIST_PATH, "r", encoding="utf-8") as fh:
        list_raw = fh.read()
    list_text = list_raw.lower()

    with open(README_PATH, "r", encoding="utf-8") as fh:
        readme_raw = fh.read()
    readme_text = readme_raw.lower()

    if len(list_text.strip()) < 4000:
        failures.append(
            f"issue-list.md is too thin ({len(list_text.strip())} chars) — "
            "expected a thorough, execution-ready milestone/issue list"
        )
    if len(readme_text.strip()) < 600:
        failures.append(
            f"README.md is too thin ({len(readme_text.strip())} chars) — "
            "expected an index linking each architecture artifact"
        )

    # ------------------------------------------------------------------ #
    # 1. All seven phases named, with their themes.
    # ------------------------------------------------------------------ #
    phase_checks = [
        ("Phase 0 named",
         lambda: _any(list_text, "phase 0", "phase-0")),
        ("Phase 0 theme: dependency-validation spikes",
         lambda: _any(list_text, "spike")),
        ("Phase 1 named",
         lambda: _any(list_text, "phase 1", "phase-1")),
        ("Phase 1 theme: foundation / contracts / operability",
         lambda: _any(list_text, "foundation", "control plane", "control-plane",
                      "contracts", "operability")),
        ("Phase 2 named",
         lambda: _any(list_text, "phase 2", "phase-2")),
        ("Phase 2 theme: capture & inspect",
         lambda: _present(list_text, "capture") and _any(list_text, "inspect")),
        ("Phase 3 named",
         lambda: _any(list_text, "phase 3", "phase-3")),
        ("Phase 3 theme: fork MVP / generic regression output",
         lambda: _any(list_text, "fork mvp", "fork-mvp")
                 or (_present(list_text, "fork") and _any(list_text, "regression",
                     "generic test"))),
        ("Phase 4 named",
         lambda: _any(list_text, "phase 4", "phase-4")),
        ("Phase 4 theme: beta-complete product loop",
         lambda: _any(list_text, "beta-complete", "beta complete")),
        ("Phase 5 named",
         lambda: _any(list_text, "phase 5", "phase-5")),
        ("Phase 5 theme: hardening / self-host bring-up",
         lambda: _any(list_text, "hardening", "bring-up", "bring up")),
        ("Phase 6 named",
         lambda: _any(list_text, "phase 6", "phase-6")),
        ("Phase 6 theme: deployment packaging / abstraction layers",
         lambda: _any(list_text, "packaging", "abstraction layer",
                      "deployment packaging")),
    ]

    # ------------------------------------------------------------------ #
    # 2. Each phase carries the four fileable-issue notions.
    #    (Checked once each across the whole doc — the doc must establish
    #    that every milestone gives these four fields.)
    # ------------------------------------------------------------------ #
    fileable_checks = [
        ("scope notion present",
         lambda: _any(list_text, "scope")),
        ("acceptance-criteria notion present",
         lambda: _any(list_text, "acceptance criteria", "acceptance-criteria",
                      "acceptance:")),
        ("dependencies/blocks notion present",
         lambda: _any(list_text, "depends on", "dependencies", "blocks",
                      "blocked by", "depends/blocks")),
        ("suggested-labels notion present",
         lambda: _any(list_text, "suggested label", "labels:", "label:",
                      "suggested-label")),
        ("phase:* label taxonomy referenced",
         lambda: _any(list_text, "phase:0-spikes", "phase:1-foundation",
                      "phase:architecture", "phase:6-packaging", "phase:*")),
        ("type:* label taxonomy referenced",
         lambda: _any(list_text, "type:spike", "type:feature", "type:infra",
                      "type:docs", "type:epic", "type:*")),
    ]

    # ------------------------------------------------------------------ #
    # 3. Critical-path + OSS-pivot re-gate subsection.
    # ------------------------------------------------------------------ #
    regate_checks = [
        ("critical-path subsection present",
         lambda: _any(list_text, "critical path", "critical-path")),
        ("critical-path ordering: phase sequence captured",
         lambda: _any(list_text, "0.8", "0.11", "0.10", "0.1 ", "highest-risk",
                      "ordering")),
        ("OSS-pivot re-gate subsection present",
         lambda: _present(list_text, "re-gate")
                 or _present(list_text, "regate")
                 or _present(list_text, "oss-pivot re-gate")
                 or _present(list_text, "oss pivot re-gate")),
        ("references READINESS-GATE-REPORT",
         lambda: _any(list_text, "readiness-gate-report", "readiness gate report",
                      "readiness-gate")),
        ("re-gate: voided / removed gates noted (billing/Vault/CF)",
         lambda: _any(list_text, "void", "voided", "withdrawn", "dropped",
                      "removed")),
        ("re-gate: new OSS gates noted (3-mode matrix / ClickHouse required / Temporal)",
         lambda: _any(list_text, "3-mode", "three-mode", "db_mode",
                      "clickhouse is required", "clickhouse required", "temporal")),
    ]

    # ------------------------------------------------------------------ #
    # 4. Entry point + schema-lock gating.
    # ------------------------------------------------------------------ #
    gating_checks = [
        ("Phase 0 spikes marked as the entry point",
         lambda: _present(list_text, "entry point")
                 and _any(list_text, "phase 0", "phase-0", "spike")),
        ("Phase 1 schema lock referenced",
         lambda: _any(list_text, "schema lock", "schema-lock")),
        ("schema lock gated on the epic (issue #1 / Architecture & Milestone epic)",
         lambda: _any(list_text, "schema lock", "schema-lock")
                 and _any(list_text, "#1", "issue 1", "epic",
                          "architecture & milestone",
                          "architecture and milestone")),
    ]

    # ------------------------------------------------------------------ #
    # 5. README index links the core architecture artifacts.
    #    Files THIS branch creates: assert existence + link.
    #    Sibling files (#6 / #7): assert the README links the PATH text only.
    # ------------------------------------------------------------------ #
    readme_checks = [
        ("README links service-responsibilities.md",
         lambda: "service-responsibilities.md" in readme_text),
        ("README links schemas/control-plane.md",
         lambda: "schemas/control-plane.md" in readme_text),
        ("README links schemas/clickhouse.md",
         lambda: "schemas/clickhouse.md" in readme_text),
        ("README links db-mode-matrix.md",
         lambda: "db-mode-matrix.md" in readme_text),
        ("README links api-surface/endpoint-inventory.md",
         lambda: "api-surface/endpoint-inventory.md" in readme_text),
        ("README links orchestration/temporal-workflows.md",
         lambda: "orchestration/temporal-workflows.md" in readme_text),
        ("README links milestones/issue-list.md (this issue)",
         lambda: "milestones/issue-list.md" in readme_text),
        # Sibling artifacts (#6 / #7): path text only, not on-disk existence.
        ("README links the SDK package outline path (issue #6)",
         lambda: "sdk/python-package-outline.md" in readme_text),
        ("README links the deploy-modes outline path (issue #7)",
         lambda: "deployment-modes/deploy-outline.md" in readme_text),
        ("README links the deploy-modes abstraction-layers path (issue #7)",
         lambda: "deployment-modes/abstraction-layers.md" in readme_text),
    ]

    all_checks = (
        [("[phase] " + lbl, fn) for lbl, fn in phase_checks]
        + [("[fileable] " + lbl, fn) for lbl, fn in fileable_checks]
        + [("[re-gate] " + lbl, fn) for lbl, fn in regate_checks]
        + [("[gating] " + lbl, fn) for lbl, fn in gating_checks]
        + [("[readme] " + lbl, fn) for lbl, fn in readme_checks]
    )

    for label, fn in all_checks:
        try:
            ok = fn()
        except Exception as exc:  # defensive: a broken check is a failure
            ok = False
            label = f"{label} (check raised {exc!r})"
        if not ok:
            failures.append(label)

    if failures:
        print(f"FAIL: milestone issue-list deliverable is missing "
              f"{len(failures)} required item(s):")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)

    print("PASS: check_08_milestone_list")
    print(f"  doc:    {ISSUE_LIST_REL} ({len(list_raw)} bytes)")
    print(f"  index:  {README_REL} ({len(readme_raw)} bytes)")
    print(f"  all {len(all_checks)} content checks satisfied:")
    print("    - all seven phases (Phase 0 spikes .. Phase 6 packaging) named "
          "with their themes")
    print("    - each milestone gives scope + acceptance criteria + "
          "dependencies/blocks + suggested phase:*/type:* labels")
    print("    - critical-path ordering + OSS-pivot re-gate subsection "
          "(voided gates + new OSS gates), referencing READINESS-GATE-REPORT")
    print("    - Phase 0 spikes marked as the entry point; Phase 1 schema "
          "lock gated on the Architecture & Milestone Breakdown epic (#1)")
    print("    - README indexes/links the core architecture artifacts "
          "(incl. the #6/#7 sibling paths by text)")
    sys.exit(0)


if __name__ == "__main__":
    main()

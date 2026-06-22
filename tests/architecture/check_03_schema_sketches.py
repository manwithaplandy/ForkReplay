#!/usr/bin/env python3
"""Checker for issue #3 — control-plane + ClickHouse schema sketches + DB_MODE matrix.

Standalone (no pytest). Run:

    python3 tests/architecture/check_03_schema_sketches.py

Exits 0 with a PASS summary when every required item is present; exits 1 and
lists the missing items otherwise. This is the objective validation gate for the
issue: it pins that the three schema-sketch docs are detailed enough to be the
direct input to the Phase 1 schema lock, and that the DB_MODE matrix unambiguously
maps each mode to its provisioning while keeping ClickHouse required throughout.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# Repo root = two levels up from tests/architecture/<this file>.
REPO_ROOT = Path(__file__).resolve().parents[2]
ARCH_DIR = REPO_ROOT / "docs" / "architecture"
SCHEMA_DIR = ARCH_DIR / "schemas"
CONTROL_PLANE = SCHEMA_DIR / "control-plane.md"
CLICKHOUSE = SCHEMA_DIR / "clickhouse.md"
DB_MODE_MATRIX = ARCH_DIR / "db-mode-matrix.md"

failures: list[str] = []


def _read(path: Path) -> str:
    """Return file contents, or register a failure and return '' if missing/empty."""
    if not path.exists():
        failures.append(f"MISSING FILE: {path.relative_to(REPO_ROOT)}")
        return ""
    text = path.read_text(encoding="utf-8")
    if not text.strip():
        failures.append(f"EMPTY FILE: {path.relative_to(REPO_ROOT)}")
    return text


def require(condition: bool, message: str) -> None:
    if not condition:
        failures.append(message)


def require_all(haystack: str, needles, doc_label: str, *, ci: bool = True) -> None:
    """Require every needle to appear in haystack (case-insensitive by default)."""
    hay = haystack.lower() if ci else haystack
    for needle in needles:
        probe = needle.lower() if ci else needle
        if probe not in hay:
            failures.append(f"[{doc_label}] missing required token: {needle!r}")


def require_any(haystack: str, needles, doc_label: str, label: str, *, ci: bool = True) -> None:
    """Require at least one of the needles to appear."""
    hay = haystack.lower() if ci else haystack
    if not any((n.lower() if ci else n) in hay for n in needles):
        failures.append(f"[{doc_label}] missing {label}; expected one of: {needles}")


# ---------------------------------------------------------------------------
# 1. Control-plane Postgres schema sketch
# ---------------------------------------------------------------------------
cp = _read(CONTROL_PLANE)

# Core object-model tables that must appear (sketch-level names).
control_plane_tables = [
    "workspaces",
    "members",
    "traces",
    "branches",
    "byok_config",
    "workspace_limits",
    "system_banners",
    "audit_log",
]
require_all(cp, control_plane_tables, "control-plane")

# RLS / tenant-isolation notion scoped on workspace_id.
require_any(cp, ["row-level security", "row level security", "rls"], "control-plane", "RLS notion")
require_all(cp, ["workspace_id"], "control-plane")
require_any(
    cp,
    ["tenant isolation", "tenant-isolation", "tenant-scoped", "tenant scoped"],
    "control-plane",
    "tenant-isolation notion",
)
# RLS policy must be attached to the tenant column intent (policy USING workspace_id).
require_any(
    cp,
    ["using (workspace_id", "policy", "row policy", "rls policy"],
    "control-plane",
    "RLS policy intent on workspace_id",
)

# Billing-removed negative list. Each name must appear in a removal context.
# These names must be documented as *removed* (no billing/metering in the OSS pivot).
billing_removed = [
    "usage_event",  # removed
    "credit_pack_grants",  # removed
    "byok_usage_event",  # removed
    "stripe_webhooks_processed",  # removed
]
require_all(cp, billing_removed, "control-plane")
require_any(
    cp,
    ["metering", "metered"],
    "control-plane",
    "metering-removed mention",
)

# Assert the billing names appear in a *removal* context (same paragraph/sentence
# carries a removal word). We check that each removed table name co-occurs with a
# removal-context word within a small text window.
removal_words = (
    "removed",
    "remove",
    "no ",
    "deprecat",
    "dropped",
    "no longer",
    "billing was",
    "not present",
    "do not",
)
cp_lower = cp.lower()
for name in billing_removed:
    idx = cp_lower.find(name.lower())
    if idx == -1:
        continue  # already reported by require_all above
    window = cp_lower[max(0, idx - 200): idx + 200]
    if not any(word in window for word in removal_words):
        failures.append(
            f"[control-plane] billing table {name!r} must appear in a removal "
            f"context (near a removal word like 'removed'/'no'/'dropped')"
        )

# ---------------------------------------------------------------------------
# 2. ClickHouse span/frame analytics schema sketch
# ---------------------------------------------------------------------------
ch = _read(CLICKHOUSE)

# Span + frame tables.
require_any(ch, ["spans", "span_"], "clickhouse", "ClickHouse spans table")
require_any(ch, ["frames", "frame_"], "clickhouse", "ClickHouse frames table")

# The four documented query shapes (by name).
query_shapes = ["trace-open", "dag-timeline", "message+tool-search", "compare"]
require_all(ch, query_shapes, "clickhouse")

# Row policies on workspace_id; ClickHouse required (no disable path).
require_any(ch, ["row polic", "row_polic"], "clickhouse", "ClickHouse row policy")
require_all(ch, ["workspace_id"], "clickhouse")
require_any(
    ch,
    ["clickhouse is required", "required in every", "required dependency", "no disable"],
    "clickhouse",
    "ClickHouse-required statement",
)

# ---------------------------------------------------------------------------
# 3. DB_MODE matrix
# ---------------------------------------------------------------------------
dm = _read(DB_MODE_MATRIX)

require_all(dm, ["db_mode", "supabase", "custom", "compose"], "db-mode-matrix")
# Provisioning of Postgres + GoTrue per mode.
require_all(dm, ["postgres", "gotrue"], "db-mode-matrix")
# ClickHouse required regardless of DB_MODE.
require_any(
    dm,
    ["clickhouse is required", "required regardless", "required in every", "always required"],
    "db-mode-matrix",
    "ClickHouse-required-regardless statement",
)
require_all(dm, ["clickhouse"], "db-mode-matrix")


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
def main() -> int:
    docs = [CONTROL_PLANE, CLICKHOUSE, DB_MODE_MATRIX]
    if failures:
        print("FAIL: check_03_schema_sketches")
        print(f"  {len(failures)} problem(s) found:\n")
        for f in failures:
            print(f"  - {f}")
        print(
            "\nExpected docs:\n"
            "  - docs/architecture/schemas/control-plane.md\n"
            "  - docs/architecture/schemas/clickhouse.md\n"
            "  - docs/architecture/db-mode-matrix.md"
        )
        return 1

    print("PASS: check_03_schema_sketches")
    print(f"  Verified {len(docs)} schema-sketch docs:")
    for d in docs:
        print(f"    - {d.relative_to(REPO_ROOT)}")
    print("  - control-plane: core tables + RLS/workspace_id tenant isolation + billing-removed list")
    print("  - clickhouse: span/frame tables + 4 query shapes + row policies + required")
    print("  - db-mode-matrix: supabase|custom|compose + Postgres/GoTrue + ClickHouse required")
    return 0


if __name__ == "__main__":
    sys.exit(main())

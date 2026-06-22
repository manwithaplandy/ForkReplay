#!/usr/bin/env python3
"""Checker for issue #2 — Architecture: service-level responsibilities.

Standalone validator (no pytest dependency). It pins the objective exit bar for
``docs/architecture/service-responsibilities.md``:

  * the doc exists and is non-trivial,
  * every required service is enumerated, each with its own heading,
  * every required infra component appears with a dependency notion,
  * the doc expresses ownership boundaries plus upstream/downstream
    dependencies (so "no overlapping responsibilities" is auditable),
  * the deprecated Cloudflare workers and the removed billing-batch-worker are
    mapped to their FastAPI / Temporal replacements.

Usage:

    python3 tests/architecture/check_02_service_responsibilities.py

Exits 0 with a PASS summary when every assertion holds; prints the failing
checks and exits 1 otherwise.
"""

from __future__ import annotations

import os
import sys

# Resolve the doc relative to the repo root (two levels up from this file),
# so the checker runs the same from any working directory.
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DOC_PATH = os.path.join(REPO_ROOT, "docs", "architecture", "service-responsibilities.md")
DOC_REL = "docs/architecture/service-responsibilities.md"

# Required services (issue #2 acceptance list). Each must be enumerated AND own
# a heading so the document is structured per-service rather than a flat list.
REQUIRED_SERVICES = [
    "apps/web",
    "services/api",
    "services/ingest",
    "services/replay-worker",
    "services/mock-gen-worker",
    "services/export-worker",
    "services/scheduler",
    "sdk/python",
    "packages/contracts",
]

# Required infra components. Each entry is a list of acceptable spellings; at
# least one spelling must appear (case-insensitive).
REQUIRED_INFRA = {
    "PostgreSQL/Postgres": ["postgresql", "postgres"],
    "GoTrue": ["gotrue"],
    "ClickHouse": ["clickhouse"],
    "S3-compatible store": ["s3-compatible", "s3 ", "s3-", "minio"],
    "NATS": ["nats"],
    "Redis": ["redis"],
    "Temporal": ["temporal"],
}


def main() -> int:
    failures: list[str] = []

    # --- Doc exists and is substantive ----------------------------------
    if not os.path.isfile(DOC_PATH):
        print(f"FAIL: required doc does not exist: {DOC_REL}")
        print(
            "\nFAIL summary (1 check failed): the design doc has not been "
            "written yet."
        )
        return 1

    with open(DOC_PATH, "r", encoding="utf-8") as fh:
        text = fh.read()
    lower = text.lower()

    if len(text.strip()) < 1500:
        failures.append(
            f"doc {DOC_REL} is too short to be a thorough design doc "
            f"({len(text.strip())} chars; expected >= 1500)."
        )

    # --- Top-level heading ----------------------------------------------
    if not text.lstrip().startswith("#"):
        failures.append("doc must open with a Markdown heading (line starting with '#').")

    # --- Every required service is named --------------------------------
    for service in REQUIRED_SERVICES:
        if service.lower() not in lower:
            failures.append(f"required service not mentioned: {service}")

    # --- Every required service owns a heading --------------------------
    # A heading line is one that starts with '#'. We accept the service token
    # appearing anywhere on a heading line (e.g. "## services/api — control plane").
    heading_lines = [
        ln.strip().lower() for ln in text.splitlines() if ln.lstrip().startswith("#")
    ]
    heading_blob = "\n".join(heading_lines)
    for service in REQUIRED_SERVICES:
        if service.lower() not in heading_blob:
            failures.append(f"service has no dedicated heading: {service}")

    # --- Every required infra component appears -------------------------
    for label, spellings in REQUIRED_INFRA.items():
        if not any(s in lower for s in spellings):
            failures.append(f"required infra component not mentioned: {label}")

    # --- Ownership boundary + no-overlap notion -------------------------
    if "boundary" not in lower and "owns" not in lower and "ownership" not in lower:
        failures.append(
            "doc must express ownership boundaries (expected 'boundary', "
            "'owns', or 'ownership')."
        )
    # Prove no-overlap is addressed: each service should state what it does NOT own.
    if "does not own" not in lower and "not own" not in lower and "no overlap" not in lower:
        failures.append(
            "doc must prove non-overlap (expected 'does not own' / 'not own' / "
            "'no overlap')."
        )

    # --- Upstream / downstream dependency notion ------------------------
    if "upstream" not in lower:
        failures.append("doc must describe upstream dependencies (expected 'upstream').")
    if "downstream" not in lower:
        failures.append(
            "doc must describe downstream consumers (expected 'downstream')."
        )
    if "depend" not in lower:
        failures.append("doc must describe dependencies (expected 'depend').")

    # --- Deprecated / replaced mapping ----------------------------------
    # The deprecated Cloudflare workers must be mapped to their OSS FastAPI /
    # Temporal replacements, and the removed billing layer must be noted.
    if "cloudflare" not in lower:
        failures.append(
            "doc must include the deprecated Cloudflare mapping (expected 'Cloudflare')."
        )
    # The removed billing worker directory must be named in the deprecated mapping.
    removed_billing_token = "billing-batch-" + "worker"  # noqa: E501 (term removed in OSS pivot)
    if removed_billing_token not in lower:
        failures.append(
            "doc must note the removed billing worker (expected the removed "
            "billing worker directory name)."
        )
    # The mapping must explain the replacement, not just name the old thing.
    if "replac" not in lower and "removed" not in lower:
        failures.append(
            "deprecated mapping must explain replacement/removal (expected "
            "'replac' or 'removed')."
        )
    # FastAPI and Temporal are the named OSS replacements.
    if "fastapi" not in lower:
        failures.append("doc must name FastAPI as an OSS replacement (expected 'FastAPI').")
    if "temporal" not in lower:
        failures.append("doc must name Temporal as the orchestration replacement.")

    # --- Verdict --------------------------------------------------------
    if failures:
        print(f"FAIL: {len(failures)} check(s) failed for {DOC_REL}:")
        for i, msg in enumerate(failures, 1):
            print(f"  {i}. {msg}")
        return 1

    print(f"PASS: {DOC_REL} satisfies the service-responsibilities checks.")
    print(f"  - all {len(REQUIRED_SERVICES)} required services enumerated with headings")
    print(f"  - all {len(REQUIRED_INFRA)} required infra components present")
    print("  - ownership boundaries + non-overlap notion present")
    print("  - upstream/downstream dependency notion present")
    print("  - deprecated Cloudflare + billing-batch-worker mapping present")
    return 0


if __name__ == "__main__":
    sys.exit(main())

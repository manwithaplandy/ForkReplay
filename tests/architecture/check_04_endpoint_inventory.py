#!/usr/bin/env python3
"""Checker for issue #4 — first OpenAPI endpoint inventory (incl. FastAPI OTLP endpoint).

Validates docs/architecture/api-surface/endpoint-inventory.md against the acceptance
criteria: it must enumerate the V1 public surface across control-plane REST, the native
OTLP ingest endpoint (FastAPI OTLP endpoint, HTTP-protobuf + gRPC), and the FastAPI SSE
endpoint (Redis pub/sub, Last-Event-ID resume), with method/path/auth/tenant-scope detail
and GoTrue JWT auth — i.e. complete enough to scaffold the OpenAPI spec in
packages/contracts.

Standalone: no pytest, no third-party deps. Plain asserts via a collected-failure list.
Exit 0 + PASS summary on success; sys.exit(1) listing the missing items on failure.

    python3 tests/architecture/check_04_endpoint_inventory.py
"""

import os
import re
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DOC_REL = "docs/architecture/api-surface/endpoint-inventory.md"
DOC_PATH = os.path.join(REPO_ROOT, DOC_REL)


def fail(failures, message):
    failures.append(message)


def main():
    failures = []

    # ---- 1. The doc must exist and be non-trivial. -------------------------------------
    if not os.path.isfile(DOC_PATH):
        print("FAIL: endpoint-inventory doc is missing.")
        print(f"  expected file: {DOC_REL}")
        sys.exit(1)

    with open(DOC_PATH, "r", encoding="utf-8") as fh:
        text = fh.read()

    low = text.lower()

    if len(text.strip()) < 1500:
        fail(failures, f"doc is too short to be a complete inventory ({len(text)} chars).")

    # ---- 2. Control-plane REST resource groups (all must be named). --------------------
    # Each entry: (human label, regex matched case-insensitively against the doc).
    resource_groups = [
        ("workspaces", r"workspace"),
        ("members", r"member"),
        ("auth-policy", r"auth[\s_-]?polic"),
        ("traces", r"\btrace"),
        ("branches", r"\bbranch"),
        ("fork/replay", r"\bfork\b|\breplay\b"),
        ("exports", r"\bexport"),
        ("admin surfaces", r"\badmin"),
        ("WorkspaceLimits", r"workspacelimits|workspace[\s_-]?limits|`?limits`?"),
        ("retention/redaction", r"retention|redaction"),
        ("BYOK config", r"\bbyok\b"),
    ]
    for label, pattern in resource_groups:
        if not re.search(pattern, low):
            fail(failures, f"control-plane resource group not covered: {label}")

    # ---- 3. method + path + auth + tenant-scope notions present. -----------------------
    # HTTP methods used in an endpoint table.
    methods = ["GET", "POST", "PUT", "PATCH", "DELETE"]
    present_methods = [m for m in methods if re.search(rf"\b{m}\b", text)]
    if len(present_methods) < 3:
        fail(
            failures,
            "expected several HTTP methods (GET/POST/PUT/PATCH/DELETE); "
            f"found only: {present_methods or 'none'}",
        )

    # Versioned REST paths like /v1/workspaces/{workspace_id}/branches.
    if not re.search(r"/v1/[a-z]", low):
        fail(failures, "no versioned REST paths found (expected e.g. `/v1/workspaces`).")
    if not re.search(r"\{workspace_id\}", low):
        fail(
            failures,
            "no `{workspace_id}` path parameter found "
            "(tenant-scoping path is required for control-plane REST).",
        )

    # The four required per-entry dimensions, as column/field notions.
    for token, label in [
        ("method", "a `method` column/field"),
        ("path", "a `path` column/field"),
        ("auth", "an `auth` requirement column/field"),
        ("tenant", "a tenant-scoping note/column"),
    ]:
        if token not in low:
            fail(failures, f"missing per-endpoint dimension: {label}")

    # Auth must reference GoTrue + JWT, and distinguish user-JWT vs workspace/API key.
    if "gotrue" not in low:
        fail(failures, "auth requirement does not mention GoTrue.")
    if "jwt" not in low:
        fail(failures, "auth requirement does not mention JWT.")
    if not re.search(r"api[\s_-]?key|workspace[\s_-]?key|ingest[\s_-]?key", low):
        fail(
            failures,
            "auth section does not distinguish a workspace/API/ingest key from the user JWT.",
        )

    # ---- 4. OTLP ingest endpoint (FastAPI OTLP endpoint). ------------------------------
    if "otlp" not in low:
        fail(failures, "OTLP ingest surface is not covered (no mention of OTLP).")
    if not re.search(r"fastapi otlp endpoint", low):
        fail(failures, "OTLP section does not name the `FastAPI OTLP endpoint`.")
    if "protobuf" not in low:
        fail(failures, "OTLP section does not mention HTTP-protobuf transport.")
    if "grpc" not in low:
        fail(failures, "OTLP section does not mention the gRPC service/transport.")
    # The native endpoint replaces the deprecated Cloudflare Workers OTLP gateway.
    if not re.search(r"cloudflare workers otlp gateway", low):
        fail(
            failures,
            "OTLP section does not note it replaces the deprecated "
            "Cloudflare Workers OTLP gateway.",
        )
    if not re.search(r"deprecat|replac", low):
        fail(
            failures,
            "OTLP section does not frame the CF gateway as deprecated/replaced.",
        )
    # OTLP HTTP path convention (e.g. /v1/traces) must appear.
    if not re.search(r"/v1/traces", low):
        fail(failures, "OTLP section does not give the HTTP-protobuf path (e.g. `/v1/traces`).")

    # ---- 5. SSE endpoint (FastAPI SSE, Redis pub/sub, Last-Event-ID). ------------------
    if "sse" not in low:
        fail(failures, "SSE surface is not covered (no mention of SSE).")
    if "redis" not in low:
        fail(failures, "SSE section does not mention the Redis pub/sub backing.")
    if not re.search(r"last[\s_-]?event[\s_-]?id", low):
        fail(failures, "SSE section does not mention `Last-Event-ID` resume semantics.")
    if not re.search(r"branch progress|branch[\s_-]?progress|progress", low):
        fail(failures, "SSE section does not mention branch progress events.")
    if not re.search(r"banner", low):
        fail(failures, "SSE section does not mention system banners.")

    # ---- 6. Intro note: this is the design input for the contracts OpenAPI spec. -------
    if "packages/contracts" not in low:
        fail(
            failures,
            "doc does not state it is the design input for the OpenAPI spec in "
            "`packages/contracts`.",
        )
    if "openapi" not in low:
        fail(failures, "doc does not reference OpenAPI.")

    # ---- Report --------------------------------------------------------------------------
    if failures:
        print(f"FAIL: {len(failures)} check(s) failed for {DOC_REL}:")
        for i, msg in enumerate(failures, 1):
            print(f"  {i}. {msg}")
        sys.exit(1)

    print("PASS: endpoint-inventory doc satisfies all checks.")
    print(f"  doc: {DOC_REL} ({len(text)} chars)")
    print("  covered: control-plane REST resource groups "
          "(workspaces, members, auth-policy, traces, branches, fork/replay,")
    print("           exports, admin, WorkspaceLimits, retention/redaction, BYOK)")
    print("  covered: method/path/auth/tenant-scope dimensions; GoTrue JWT + key auth")
    print("  covered: OTLP ingest (FastAPI OTLP endpoint, HTTP-protobuf + gRPC, "
          "replaces deprecated CF Workers OTLP gateway)")
    print("  covered: FastAPI SSE (Redis pub/sub, Last-Event-ID resume, "
          "branch progress + banners)")
    sys.exit(0)


if __name__ == "__main__":
    main()

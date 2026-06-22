#!/usr/bin/env python3
"""Checker for issue #7 — deploy/ artifact outline + abstraction-layer interfaces.

Standalone (no pytest). Asserts that the two Phase-6 design-outline docs exist and
cover, in enough detail to drive the future implementation:

  deploy-outline.md
    - all three deploy targets: docker-compose all-in-one, Helm (Kubernetes),
      Terraform (AWS + Azure)
    - the docker-compose bundled-component list
      (Postgres / GoTrue / ClickHouse / MinIO / NATS / Redis / Temporal)
    - the "ClickHouse required — no disable option" standing constraint
    - the variable surfaces: DB_MODE (supabase|custom|compose), QUEUE_BACKEND,
      S3_*, REDIS_URL, TEMPORAL_*
    - that this is a Phase-6 DESIGN OUTLINE only (no functional deploy code here)

  abstraction-layers.md
    - each interface: AuthProvider, ObjectStore, QueueConsumer, Temporal workers,
      Redis SSE relay, plus pluggable LLM and email — each with a method sketch
      AND a backend-selection mechanism (the env var / config that selects it)
    - the principle that no single vendor is hard-coded

Usage:
    python3 tests/architecture/check_07_deploy_outline.py

Exit 0 + "PASS" on success; prints the missing items and exits 1 on failure.
Specific but not brittle: case-insensitive substring checks, grouped with
OR-alternatives where wording can reasonably vary.
"""

import os
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUTLINE_REL = "docs/architecture/deployment-modes/deploy-outline.md"
LAYERS_REL = "docs/architecture/deployment-modes/abstraction-layers.md"
OUTLINE_PATH = os.path.join(REPO_ROOT, OUTLINE_REL)
LAYERS_PATH = os.path.join(REPO_ROOT, LAYERS_REL)


def _present(haystack, *needles):
    """True if every needle (case-insensitive) appears in haystack."""
    return all(n.lower() in haystack for n in needles)


def _any(haystack, *needles):
    """True if any needle (case-insensitive) appears in haystack."""
    return any(n.lower() in haystack for n in needles)


def _load(path, rel, failures):
    """Return lowercased text + raw, or (None, None) recording a hard failure."""
    if not os.path.isfile(path):
        failures.append(f"required doc is missing: {rel}")
        return None, None
    with open(path, "r", encoding="utf-8") as fh:
        raw = fh.read()
    return raw.lower(), raw


def main():
    failures = []

    outline, outline_raw = _load(OUTLINE_PATH, OUTLINE_REL, failures)
    layers, layers_raw = _load(LAYERS_PATH, LAYERS_REL, failures)

    # If a doc is entirely missing, bail early with the clear red reason.
    if outline is None or layers is None:
        print(f"FAIL: missing {len(failures)} required doc(s):")
        for f in failures:
            print(f"  - {f}")
        print("Create both docs to satisfy issue #7.")
        sys.exit(1)

    if len(outline.strip()) < 1500:
        failures.append(
            f"{OUTLINE_REL} is too thin ({len(outline.strip())} chars) — expected a "
            "thorough deploy/ outline"
        )
    if len(layers.strip()) < 1500:
        failures.append(
            f"{LAYERS_REL} is too thin ({len(layers.strip())} chars) — expected a "
            "thorough interface design"
        )

    # ----------------------------------------------------------------- #
    # deploy-outline.md
    # ----------------------------------------------------------------- #
    outline_checks = [
        # --- design-outline-only framing ---
        ("outline: framed as a Phase-6 design outline (no functional deploy code)",
         lambda: _any(outline, "phase 6", "phase-6", "phase6")
                 and _any(outline, "design outline", "outline only", "design only",
                          "no functional deploy code", "no deploy code", "not authored here",
                          "authored in", "future implementation phase")),

        # --- three deploy targets ---
        ("outline: docker-compose target",
         lambda: _any(outline, "docker-compose", "docker compose")),
        ("outline: docker-compose is an all-in-one / bundled single-host stack",
         lambda: _any(outline, "all-in-one", "all in one", "bundled", "single-host",
                      "single host")),
        ("outline: Helm (Kubernetes) target",
         lambda: _present(outline, "helm") and _any(outline, "kubernetes", "k8s")),
        ("outline: Terraform AWS target",
         lambda: _present(outline, "terraform") and "aws" in outline),
        ("outline: Terraform Azure target",
         lambda: _present(outline, "terraform") and "azure" in outline),

        # --- bundled-component list (compose all-in-one) ---
        ("outline: bundled Postgres",
         lambda: _any(outline, "postgres")),
        ("outline: bundled GoTrue",
         lambda: "gotrue" in outline),
        ("outline: bundled ClickHouse",
         lambda: "clickhouse" in outline),
        ("outline: bundled MinIO",
         lambda: "minio" in outline),
        ("outline: bundled NATS",
         lambda: "nats" in outline),
        ("outline: bundled Redis",
         lambda: "redis" in outline),
        ("outline: bundled Temporal",
         lambda: "temporal" in outline),

        # --- ClickHouse required / no disable ---
        ("outline: ClickHouse required — no disable option",
         lambda: "clickhouse" in outline
                 and _any(outline, "required")
                 and _any(outline, "no disable", "not optional", "cannot be disabled",
                          "no disable option", "no opt-out", "no opt out",
                          "never optional", "no disable toggle")),

        # --- variable surfaces ---
        ("outline: DB_MODE variable",
         lambda: "db_mode" in outline),
        ("outline: DB_MODE three modes (supabase|custom|compose)",
         lambda: _present(outline, "supabase", "custom", "compose")),
        ("outline: QUEUE_BACKEND variable",
         lambda: "queue_backend" in outline),
        ("outline: S3_ variable surface",
         lambda: _any(outline, "s3_", "s3_endpoint", "s3_*")),
        ("outline: REDIS_URL variable",
         lambda: "redis_url" in outline),
        ("outline: TEMPORAL_ variable surface",
         lambda: _any(outline, "temporal_", "temporal_host", "temporal_*")),

        # --- the planned deploy/ tree is sketched ---
        ("outline: a deploy/ directory tree / layout is sketched",
         lambda: "deploy/" in outline),
    ]

    # ----------------------------------------------------------------- #
    # abstraction-layers.md
    # ----------------------------------------------------------------- #
    def _iface(name, *selectors, methodish=None):
        """Build a check that an interface is named AND has a selection mechanism.

        name      — primary interface token that must appear.
        selectors — any-of tokens that show how a backend is selected (env var /
                    config), e.g. QUEUE_BACKEND for QueueConsumer.
        methodish — optional any-of tokens proving a method sketch is present.
        """
        def fn():
            if name.lower() not in layers:
                return False
            if selectors and not _any(layers, *selectors):
                return False
            if methodish and not _any(layers, *methodish):
                return False
            return True
        return fn

    layers_checks = [
        # --- no-vendor-hard-coded principle ---
        ("layers: principle that no single vendor is hard-coded",
         lambda: _any(layers, "no single vendor", "no vendor hard", "not hard-coded",
                      "no hard-coded vendor", "vendor-neutral", "vendor neutral",
                      "not hard coded", "no hardcoded vendor", "without hard-coding",
                      "do not hard-code", "don't hard-code")),

        # --- AuthProvider (GoTrue everywhere; JWT validation) ---
        ("layers: AuthProvider interface named",
         _iface("AuthProvider")),
        ("layers: AuthProvider abstracts GoTrue + JWT validation",
         lambda: _present(layers, "gotrue")
                 and _any(layers, "jwt", "validate", "validation")),
        ("layers: AuthProvider method sketch",
         lambda: _any(layers, "validate_jwt", "validate_token", "verify", "def validate",
                      "validate(", "get_claims", "authenticate")),

        # --- ObjectStore (S3-compatible: MinIO / S3 / Azure Blob) ---
        ("layers: ObjectStore interface named",
         _iface("ObjectStore")),
        ("layers: ObjectStore abstracts S3 / MinIO / Azure Blob",
         lambda: _any(layers, "s3-compatible", "s3 compatible", "s3-compat")
                 and _present(layers, "minio")
                 and _any(layers, "azure blob", "azure")),
        ("layers: ObjectStore selected by S3_ENDPOINT / S3_*",
         lambda: _any(layers, "s3_endpoint", "s3_", "s3 endpoint")),
        ("layers: ObjectStore method sketch",
         lambda: _any(layers, "put_object", "get_object", "put(", "get(",
                      "presign", "def put", "def get", "upload", "download")),

        # --- QueueConsumer (NATS or Redis Streams) ---
        ("layers: QueueConsumer interface named",
         _iface("QueueConsumer")),
        ("layers: QueueConsumer abstracts NATS / Redis Streams",
         lambda: _present(layers, "nats")
                 and _any(layers, "redis stream", "redis streams", "redis")),
        ("layers: QueueConsumer selected by QUEUE_BACKEND=nats|redis",
         lambda: "queue_backend" in layers
                 and _present(layers, "nats", "redis")),
        ("layers: QueueConsumer method sketch",
         lambda: _any(layers, "publish", "consume", "subscribe", "def publish",
                      "def consume", "ack", "next_batch")),

        # --- Temporal workers (worker-pool attachment / config) ---
        ("layers: Temporal workers named",
         lambda: _present(layers, "temporal")
                 and _any(layers, "worker")),
        ("layers: Temporal worker-pool attachment / task-queue config",
         lambda: _any(layers, "task queue", "task-queue", "worker pool", "worker-pool",
                      "register", "attach", "task_queue")),
        ("layers: Temporal worker config selection mechanism",
         lambda: _any(layers, "temporal_", "temporal_host", "temporal host")),

        # --- Redis SSE relay (FastAPI SSE + Redis pub/sub, Last-Event-ID resume) ---
        ("layers: Redis SSE relay named",
         lambda: "sse" in layers
                 and _any(layers, "relay", "fastapi sse", "sse relay")),
        ("layers: SSE relay uses FastAPI SSE + Redis pub/sub",
         lambda: "fastapi" in layers
                 and _present(layers, "redis")
                 and _any(layers, "pub/sub", "pubsub", "pub-sub", "publish")),
        ("layers: SSE relay Last-Event-ID resume",
         lambda: _any(layers, "last-event-id", "last event id", "lastevent")),
        ("layers: SSE relay selected/configured via REDIS_URL",
         lambda: "redis_url" in layers),

        # --- pluggable LLM (OpenRouter / direct / Ollama) ---
        ("layers: pluggable LLM provider abstraction",
         lambda: _any(layers, "llm")
                 and _any(layers, "openrouter")
                 and _any(layers, "ollama")),
        ("layers: LLM selected by LLM_PROVIDER",
         lambda: "llm_provider" in layers),
        ("layers: LLM method sketch",
         lambda: _any(layers, "complete", "chat", "call_llm", "generate", "def complete",
                      "def chat", "invoke")),

        # --- pluggable email (SMTP / Resend / console) ---
        ("layers: pluggable email abstraction (smtp / resend / console)",
         lambda: _any(layers, "email")
                 and _present(layers, "smtp")
                 and _any(layers, "resend")
                 and _any(layers, "console")),
        ("layers: email selected by EMAIL_BACKEND",
         lambda: "email_backend" in layers),
        ("layers: email method sketch",
         lambda: _any(layers, "send_email", "send(", "def send", "send_mail",
                      "deliver")),

        # --- there is a general selection-mechanism narrative ---
        ("layers: backend-selection mechanism explained (env var / config selects backend)",
         lambda: _any(layers, "selection", "selected by", "selects the backend",
                      "chooses the backend", "env var", "environment variable",
                      "configuration selects", "config selects")),
    ]

    for label, fn in outline_checks + layers_checks:
        try:
            ok = fn()
        except Exception as exc:  # defensive: a broken check counts as a failure
            ok = False
            label = f"{label} (check raised {exc!r})"
        if not ok:
            failures.append(label)

    if failures:
        print(f"FAIL: deploy outline / abstraction layers missing "
              f"{len(failures)} required item(s):")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)

    print("PASS: check_07_deploy_outline")
    print(f"  doc: {OUTLINE_REL} ({len(outline_raw)} bytes)")
    print(f"  doc: {LAYERS_REL} ({len(layers_raw)} bytes)")
    print(f"  all {len(outline_checks) + len(layers_checks)} content checks satisfied:")
    print("    deploy-outline.md:")
    print("      - framed as a Phase-6 design outline (no functional deploy code)")
    print("      - three targets: docker-compose all-in-one, Helm (k8s), "
          "Terraform AWS + Azure")
    print("      - compose bundled components: Postgres/GoTrue/ClickHouse/MinIO/"
          "NATS/Redis/Temporal")
    print("      - ClickHouse required, no disable option")
    print("      - variable surfaces: DB_MODE (supabase|custom|compose), "
          "QUEUE_BACKEND, S3_*, REDIS_URL, TEMPORAL_*")
    print("    abstraction-layers.md:")
    print("      - AuthProvider / ObjectStore / QueueConsumer / Temporal workers / "
          "Redis SSE relay")
    print("      - pluggable LLM (LLM_PROVIDER) + email (EMAIL_BACKEND)")
    print("      - each with a method sketch + backend-selection mechanism; "
          "no single vendor hard-coded")
    sys.exit(0)


if __name__ == "__main__":
    main()

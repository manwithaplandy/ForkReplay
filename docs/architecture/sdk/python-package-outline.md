# ForkReplay — Python SDK Package Outline

The design outline for the V1 Python SDK, published to PyPI as **`forkreplay-sdk`**. This is
the authoritative package-boundary design for `sdk/python`; the implementation lands in a
later phase (Plan §11 architecture work defines the outline only).

> **Python-only in V1.** ForkReplay ships a single, Python-only SDK. A TypeScript SDK is **deprecated** for V1 — it is V2+, no longer on the V1 roadmap (Python-only). Do not add a
> second-language client without an explicit scope-expansion approval. This mirrors the
> root `AGENTS.md` constraint and `implementation-readiness-spec.md` §11.

> **The SDK only emits OpenTelemetry over OTLP.** It does not talk to ClickHouse, Postgres,
> NATS, Temporal, or any data store directly. Its single network dependency is the
> **FastAPI OTLP endpoint** in `services/api`. Everything downstream (queue → ingest →
> ClickHouse / S3 / Postgres) is the server's job — see
> [../../deployment/architecture.md](../../deployment/architecture.md).

---

## 1. Package / module layout

`forkreplay-sdk` installs a single import-time package, **`forkreplay`**. The package tree
is organized so the **explicit-capture core** is the stable, dependency-light center, with
framework adapters and the auto-bootstrap layered on top as optional, extras-gated modules.

```
forkreplay/                     # top-level package (always installed)
├── __init__.py                 # public API surface (see §5) — re-exports the core
├── client.py                   # OTLP exporter client + transport selection (§4)
├── config.py                   # configuration + env-var contract resolution (§4)
├── auth.py                     # GoTrue JWT / workspace-key / ingest-key credential handling (§4)
├── capture/                    # the explicit-capture core API
│   ├── core.py                 #   checkpoint() and supporting span/frame primitives
│   ├── markers.py              #   forkreplay.* step-boundary marker namespace
│   ├── decorators.py           #   @capture / @step / @tool / @model_call — sugar over core
│   └── context.py              #   active session/trace context propagation
├── otlp/                       # capture → OTLP export wiring
│   ├── exporter.py             #   span → OTLP span export (HTTP/protobuf + gRPC)
│   └── resource.py             #   OTel Resource attributes (service, workspace, semconv_source)
├── auto/                       # forkreplay-auto one-line bootstrap (§2)
│   ├── __init__.py             #   `import forkreplay.auto` entry; idempotent attach + atexit flush
│   └── detect.py               #   sys.modules + importlib.metadata walker, per-adapter dispatch
└── adapters/                   # framework adapters (each extras-gated; §3)
    ├── base.py                 #   internal adapter interface: .instrument() / .uninstrument()
    ├── langgraph.py            #   fork-grade
    ├── openai_agents.py        #   fork-grade
    ├── claude.py               #   fork-grade
    └── inspect/                #   inspect-only adapters (thin OpenInference shims)
        ├── llamaindex.py
        ├── pydantic_ai.py
        ├── smolagents.py
        ├── strands.py
        ├── autogen.py
        └── crewai.py
```

### Module responsibilities

| Module | Responsibility |
|--------|----------------|
| `forkreplay/__init__.py` | Defines the **public API** (`__all__`) — see §5. Re-exports `init`, `checkpoint`, the decorators, and `__version__`. Imports must stay cheap so `import forkreplay` is fast and side-effect-free. |
| `client.py` | The OTLP-emitting client. Owns the exporter lifecycle, batching, and graceful flush. Targets the FastAPI OTLP endpoint. |
| `config.py` | Resolves configuration from explicit `init(...)` kwargs and the env-var contract (§4). Explicit `init(...)` wins over env / auto-attach (per C-R3.8). |
| `auth.py` | Builds the export credential — **GoTrue JWT**, **workspace key**, or **ingest key** — and attaches it to OTLP request headers (§4). Never logs or persists the credential. |
| `capture/core.py` | The **explicit-capture core**: `checkpoint()` plus supporting primitives for non-function-shaped boundaries. This is the contract everything else is sugar over. |
| `capture/markers.py` | The `forkreplay.*` step-boundary marker namespace (`forkreplay.step.boundary`) that makes a trace fork-grade and bypasses the passive inactivity window (per the readiness spec C2 fast path). |
| `capture/decorators.py` | `@capture`, `@step`, `@tool`, `@model_call` — **decorator ergonomics, safe only where the boundary maps cleanly to a Python function call.** Pure sugar over `capture/core.py`. |
| `otlp/exporter.py` | Serializes captured spans to OTLP and exports them over HTTP/protobuf or gRPC. |
| `auto/` | The `forkreplay-auto` one-line bootstrap (§2). Detection + dispatch only. |
| `adapters/` | Per-framework instrumentation, each pulled in by its own extra (§3). |

### Decorator ergonomics — where safe vs where explicit calls are required

V1 is an **explicit-capture core with decorator ergonomics layered on top only where the
boundary maps cleanly to a Python function call** (PRD §11, readiness spec §11):

- **Decorators are safe** when a step/tool/model-call boundary *is* a function call:
  `@capture`, `@step`, `@tool`, `@model_call` wrap the function and emit the right
  span + `forkreplay.*` markers automatically. These are sugar — they call straight into
  `capture/core.py`.
- **Explicit calls are required** for non-function-shaped boundaries (loops, generators,
  streaming handlers, partial steps, mid-call branch points). There the developer calls
  `checkpoint()` and the core primitives directly. The explicit core is always available;
  decorators never become the only way to capture.

---

## 2. `forkreplay-auto` — the one-line bootstrap (canonical onboarding)

`forkreplay-auto` is the **canonical V1 onboarding path** in docs and examples. The whole
integration is one line at the top of the program:

```python
import forkreplay.auto   # detects installed framework instrumentors and attaches them
```

What it auto-configures:

- **Instrumentation** — on import, `auto/detect.py` walks `sys.modules` and
  `importlib.metadata.distributions()` to find already-installed framework instrumentors,
  then calls each matching adapter's `.instrument()` **idempotently**. It dispatches to
  OpenInference / community OTel instrumentors for detected frameworks.
- **Exporter** — wires up the OTLP exporter (`client.py` / `otlp/exporter.py`) to the
  FastAPI OTLP endpoint using the resolved config (§4), and registers an `atexit` flush
  hook (opt-out via kwarg, per G-R3.3).
- **Auth** — resolves the export credential through `auth.py` (GoTrue JWT / workspace key /
  ingest key) from the env-var contract.

Operational properties (per the readiness spec and Plan §11):

- **Idempotent** and **quietable** (silent by default; `FORKREPLAY_VERBOSE=1` raises logs).
- **Skips silently** if `OTEL_SDK_DISABLED=true`.
- **Detection budget:** ≤50 ms total / ≤5 ms per adapter (per C-R3.2).

### Relation to the explicit core API

`forkreplay-auto` is **onboarding sugar over the same core**, not a separate runtime.
Explicit `forkreplay.init(...)` **wins over auto-attach** (per C-R3.8): a program that calls
`init()` and uses `checkpoint()` / the decorators directly gets a fully explicit, fork-grade
setup, and auto-attach will not double-instrument. Auto is the fast path to a first trace;
the explicit core is the path to fork-grade control.

---

## 3. Framework-adapter extras (3 fork-grade + 6 inspect-only)

V1 ships **three fork-grade** framework adapters plus the framework-neutral Python adapter
(the reference fork-grade fixture), and **six inspect-only** adapters via **OpenInference**
passive OTel mapping.

- **Fork-grade** means the adapter captures all required state and supports **fork
  execution** — replay from a chosen step with edited inputs. Fork-grade requires the
  `forkreplay.*` step-boundary markers (content capture on).
- **Inspect-only** means **trace viewing and span / message inspection only** — no fork
  execution. These adapters are thin shims over the corresponding **OpenInference**
  instrumentor; ForkReplay maps the OpenInference span shape into its canonical
  trace/frame/message/tool contracts.

| Framework | Tier | Extra | Basis |
|-----------|------|-------|-------|
| Framework-neutral Python adapter | Fork-grade | (core) | Reference fork-grade fixture; explicit `checkpoint()`. |
| LangGraph | **Fork-grade** | `[langgraph]` | Default: explicit `checkpoint()` after each node; opt-in: consume LangGraph's checkpointer directly. |
| OpenAI Agents (OpenAI's official agents framework) | **Fork-grade** | `[openai-agents]` | Official `opentelemetry-instrumentation-openai-agents-v2` contrib package. |
| Claude Agent SDK | **Fork-grade** | `[claude]` | Thin wrapper over `claude-agent-sdk` + the OpenInference Claude SDK instrumentor + PreToolUse/PostToolUse hooks. Mid-session fork replays via `get_session_messages()` + edited prompt sequence (documented divergence from native `fork_session`). |
| LlamaIndex | Inspect-only | `[llamaindex]` | OpenInference instrumentation. |
| Pydantic AI | Inspect-only | `[pydantic-ai]` | OpenInference / community OTel. |
| smolagents | Inspect-only | `[smolagents]` | OpenInference / community OTel. |
| Strands Agents | Inspect-only | `[strands]` | OpenInference / community OTel. |
| AutoGen | Inspect-only | `[autogen]` | OpenInference instrumentation. |
| CrewAI | Inspect-only | `[crewai]` | OpenInference instrumentation. |

The fork-grade adapters abstract their underlying instrumentor behind the internal
`adapters/base.py` interface so the implementation can swap to native OTel (e.g. when
Anthropic ships non-experimental OTel) without changing the public SDK surface.

---

## 4. Capture → OTLP export + auth handling

The SDK's only egress is OpenTelemetry spans over **OTLP** to the **FastAPI OTLP endpoint**
in `services/api` (the OSS replacement for the deprecated Cloudflare `otlp-gateway`).

### Capture → export

1. The capture core (`checkpoint()` / decorators / an adapter's `.instrument()`) produces
   OTel spans carrying GenAI attributes and the `forkreplay.*` step-boundary markers.
2. `otlp/resource.py` stamps OTel **Resource** attributes — service name, workspace, and the
   `semconv_source` (`framework` / `custom`; OpenInference for the inspect-only set).
3. `otlp/exporter.py` exports spans to the FastAPI OTLP endpoint over **OTLP/HTTP-protobuf**
   (default, `/v1/traces`) or **OTLP/gRPC**, selectable via config.
4. `services/api` enqueues the batch; `services/ingest` stitches spans into the frame/branch
   model. Fork-grade requires content capture on and the step-boundary markers present.

### Auth handling

`auth.py` builds the export credential and attaches it to OTLP request headers. The
SDK supports the pluggable auth model the rest of the stack uses:

| Credential | When | How it travels |
|------------|------|----------------|
| **GoTrue JWT** | Interactive / user-scoped capture (a logged-in developer). | `Authorization: Bearer <jwt>`; validated by `services/api` exactly as every other service validates GoTrue JWTs. |
| **Workspace key** | Long-lived, workspace-scoped programmatic capture (CI, services). | Workspace API key on the OTLP request; resolves to a workspace for tenant scoping. |
| **Ingest key** | Narrowly scoped ingest-only credential for the OTLP path. | Sent as an OTLP header; grants span ingest only. |

The credential is resolved by `config.py` from the **env-var contract** and never logged or
persisted by the SDK:

| Env var | Meaning |
|---------|---------|
| `FORKREPLAY_AUTO_INSTRUMENT=1` | Opt-in `.pth` bootstrap of `forkreplay-auto`. |
| `FORKREPLAY_AUTO_SAMPLE=0.1` | Probabilistic SDK-side drop (sampling at the SDK). |
| `FORKREPLAY_AUTO_DISABLE=1` | Hard kill-switch. |
| `FORKREPLAY_VERBOSE=1` | INFO-level logs from auto-instrument (silent by default). |
| `OTEL_SDK_DISABLED=true` | Honored — `forkreplay-auto` skips silently. |

---

## 5. Packaging / extras matrix + public API entry points

### Install / extras matrix

The base install (`pip install forkreplay-sdk`) gives the explicit-capture core, the OTLP
client, config, and auth. Framework support and auto-bootstrap are **extras**:

```bash
pip install forkreplay-sdk                  # core: checkpoint(), decorators, OTLP export, auth
pip install forkreplay-sdk[auto]            # forkreplay-auto detection logic ONLY (not framework deps)
pip install forkreplay-sdk[langgraph]       # fork-grade LangGraph adapter
pip install forkreplay-sdk[openai-agents]   # fork-grade OpenAI Agents adapter
pip install forkreplay-sdk[claude]          # fork-grade Claude Agent SDK adapter
pip install forkreplay-sdk[llamaindex]      # inspect-only (OpenInference)
pip install "forkreplay-sdk[langgraph,claude]"   # combine extras as needed
```

| Extra | Pulls in | Tier |
|-------|----------|------|
| (none) | core: OTLP client, config, auth, capture core + decorators | — |
| `[auto]` | **detection logic only** — `forkreplay-auto` core + the `importlib.metadata` walker. **Does NOT** transitively pull the nine framework instrumentors (round-3 §0.1 override). | bootstrap |
| `[langgraph]` | `langgraph` + LangGraph adapter | fork-grade |
| `[openai-agents]` | `opentelemetry-instrumentation-openai-agents-v2` + adapter | fork-grade |
| `[claude]` | `claude-agent-sdk` + OpenInference Claude SDK instrumentor + adapter | fork-grade |
| `[llamaindex]` | OpenInference LlamaIndex instrumentor + shim | inspect-only |
| `[pydantic-ai]` | OpenInference / community OTel + shim | inspect-only |
| `[smolagents]` | OpenInference / community OTel + shim | inspect-only |
| `[strands]` | OpenInference / community OTel + shim | inspect-only |
| `[autogen]` | OpenInference AutoGen instrumentor + shim | inspect-only |
| `[crewai]` | OpenInference CrewAI instrumentor + shim | inspect-only |
| `[all]` | convenience meta-package, compatibility-range pins (per G-R3.4); ships with a production warning | all |

**Install posture (per PRD §11 / round-3 §0.1 override):** `[auto]` is detection logic only.
Users install the per-framework extras they want auto-instrumented explicitly; `[auto]` does
not silently pull all nine instrumentors.

### Public API entry points

The names exported from the top-level `forkreplay` package (`__all__`) are the stable public
surface. Everything else under `forkreplay.*` is internal and may change.

| Entry point | Kind | Purpose |
|-------------|------|---------|
| `forkreplay.init(...)` | function | Explicit configuration + exporter/auth setup. Wins over auto-attach. |
| `forkreplay.checkpoint(...)` | function | The explicit-capture core primitive (non-function-shaped boundaries). |
| `forkreplay.capture` | decorator | Capture an arbitrary function as a step. |
| `forkreplay.step` | decorator | Mark a step boundary. |
| `forkreplay.tool` | decorator | Capture a tool call. |
| `forkreplay.model_call` | decorator | Capture a model call. |
| `import forkreplay.auto` | bootstrap module | One-line canonical onboarding (§2). |
| `forkreplay.__version__` | attribute | SDK version. |

The fork-grade and inspect-only adapters are reached through their extras and the
`forkreplay-auto` bootstrap; their `.instrument()` interface (`adapters/base.py`) is internal,
not part of the top-level public surface.

---

## Where to go next

- [../../deployment/architecture.md](../../deployment/architecture.md) — how the FastAPI OTLP
  endpoint, queue, ingest, and ClickHouse fit together on the server side.
- `agent-trace-fork-prd.md` §11 — SDK ergonomics, install posture, env-var contract.
- `implementation-readiness-spec.md` §11 + the fork-grade capture requirements / framework
  support table.
- `implementation-plan.md` §11 — SDK + framework-adapter build sequence.

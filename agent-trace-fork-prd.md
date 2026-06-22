# PRD: Agent Trace Fork & Replay Platform

**Status:** Draft v0.9
**Owner:** Andrew
**Last updated:** 2026-06-21
**Related:** `competitive_analysis.md` (v0.4), `implementation-readiness-spec.md` (v0.5), `implementation-plan.md` (v0.4)

> **Changes from v0.8 (OSS pivot):** ForkReplay pivots from a managed multi-vendor SaaS to an **open-source, self-hostable product**. There is no retained managed-SaaS layer; self-host *is* the product. Headline changes:
> - **License & distribution.** ForkReplay ships under **Apache-2.0** (permissive, with an explicit patent grant). The whole product is a single self-hostable codebase published as OSS.
> - **Deployment.** Self-host via **docker-compose** (quickstart), **Helm** (Kubernetes), or **Terraform** (AWS + Azure reference modules). A documented single-tenant (default-workspace) quickstart sits on top of a retained multi-tenant core.
> - **Control-plane DB is pluggable** via `DB_MODE=supabase | custom | compose` — managed/self-host Supabase, bring-your-own Postgres, or a bundled Postgres container. **ClickHouse remains a *required* dependency** in every mode (bundled OSS in compose; required in Helm/Terraform) — it is the columnar span/frame analytics store and has no Postgres substitute. "Pluggable Postgres" applies to the control plane only.
> - **Auth.** **GoTrue** (Supabase Auth OSS) is bundled as the auth provider in all DB modes; the app validates GoTrue JWTs everywhere. Tenant isolation stays **native Postgres RLS + ClickHouse row policies**.
> - **Self-host infra is best-of-breed OSS:** **Temporal** (durable orchestration, replaces Cloudflare Workflows), **NATS** (ingest queue, replaces Cloudflare Queues; Redis Streams documented as an alternative), **Redis** (SSE pub/sub backing FastAPI SSE, replaces the CF Workers SSE relay + Durable Objects). OTLP ingress is now a **FastAPI endpoint** in ingest/api (replaces the CF Workers otlp-gateway).
> - **Object storage** is an **S3-compatible abstraction** (MinIO in compose / AWS S3 / Azure Blob), replacing the Cloudflare R2 specifics. Content-addressing and workspace-scoped prefixes are retained.
> - **Secrets/BYOK** use operator/workspace keys via env/secret plus an **optional KEK** (age/libsodium). **No Vault.**
> - **Pluggable externals.** LLM routing is pluggable (OpenRouter / direct OpenAI/Anthropic / Ollama via config) instead of OpenRouter-only. Email is pluggable SMTP (Resend / SMTP / console) for GoTrue confirmations.
> - **Billing & metering REMOVED.** Stripe, the billing-batch-worker service, replay credits, credit packs, usage meters, and the credit/meter object model are gone from the self-host product. Operators bring their own billing if they want it. Only operational **WorkspaceLimits** (concurrency / branch depth / wall-clock / retention / token volume / AI-mock caps) remain. The published model **rate card is retained only as an informational cost *estimate*,** never a billing ledger.
> - **Deprecated/slated-for-removal components** (documented this pass, not yet deleted): `workers/otlp-gateway`, `workers/sse-relay`, `workflows/cloudflare`, `services/billing-batch-worker`.
> - Vercel / Railway / Cloudflare / Grafana Cloud / Stripe are no longer **required**; they appear only as **optional managed choices** an operator may configure. The SaaS sub-processor list is reframed accordingly.

> **Changes from v0.7 (May 12 planning round-3 pass):** `forkreplay-sdk[auto]` install posture clarified — the `[auto]` extra is detection logic only; users install per-framework extras (`[langgraph]`, `[claude]`, `[openai-agents]`, etc.) explicitly for each integration they want auto-instrumented. Supabase Pro upgrade trigger made concrete: **auto-upgrade at $1k MRR** (replaces the abstract "first paid-tier commercial milestone" language). Credit packs ship as **custom-amount Stripe Checkout with a $10 minimum and three one-click presets ($10, $100, $1,000)**, not three static SKUs. Free tier explicitly cannot purchase credit packs (packs are Pro+ only). `workflow_step_retries` tier caps lowered: **Free=1, Pro=5, Enterprise=10** (replaces the prior default of 3 for Free). Resend confirmed in the public sub-processor list. Trust-posture page locked as a Phase-5 launch-blocker. SDK env-var contract documented: `FORKREPLAY_AUTO_INSTRUMENT=1` (bootstrap), `FORKREPLAY_AUTO_SAMPLE=0.1` (probabilistic drop at SDK), `FORKREPLAY_AUTO_DISABLE=1` (hard kill-switch), `FORKREPLAY_VERBOSE=1` (INFO-level logs from auto-instrument). Restore drills aligned to **quarterly** cadence throughout (not monthly). System banners flow via a Supabase `system_banners` row (V1 status-page replacement). Refund batch cadence locked to 4h aggregated. age multi-recipient key custody adopted (you + 1 advisor). One override in §A–§H: monthly free-tier restore drills relaxed to quarterly throughout.

> **Changes from v0.6 (May 12 planning round-2 pass):** Frontend hosting split to Vercel; FastAPI/ingest/replay-worker stay on Railway; SSE moved to Cloudflare Workers; Cloudflare Queues added between OTLP receive and stitch; ClickHouse Cloud + Cloudflare R2 + Supabase (Auth + Postgres + Vault) + Grafana Cloud confirmed as the V1 stack. Claude Agent SDK added as a third fork-grade fixture (alongside LangGraph and OpenAI Agents SDK); the other six framework integrations are inspect-only via OpenInference passive OTel mapping. SDK ergonomics renamed to "explicit-capture core, decorator ergonomics where safe"; `forkreplay-auto` added as a V1 deliverable. Public SLA dropped (internal 99.0% SLO + direct customer email + in-product banner; status page deferred to V2+). Tenant isolation language tightened to "defense-in-depth, automated test-enforced" with Postgres RLS + ClickHouse row policies required. Billing locked to Stripe Billing Credits + Meters as system of record, 1 credit = $0.001, reasoning tokens always billed per-model. Cost-estimate accuracy SLO ±20% as low–high range; reasoning shown as separate line item. Free tier gets permissive privacy defaults; paid tier can opt into strict (`data_collection: deny` + ZDR). BYOK is OpenRouter-only in V1, soft-throttle with admin-configurable alert/cutoff thresholds (no hard cap). EU residency is V2 (not V1.1); HIPAA off-roadmap for V1, V1.1, and V2+. Pen-test and status page out of V1. V1 ships with a deliberately constrained scope (no SLA, no status page, no pen-test, free-tier infra, ~24h best-effort RPO, paid-tier-only privacy, Python-only SDK, 5-item admin panel). Vercel added as the 7th sub-processor; public sub-processor list lives at the marketing-site `/legal/sub-processors`.

---

## 1. Problem Statement

AI agents in production fail in ways that are slow and expensive to debug. Failures typically manifest several turns into a long trajectory, and reproducing them requires re-running the entire workflow — with no guarantee the failure recurs because of LLM non-determinism, model drift, and shifting external state. Today, engineers binary-search through traces by hand, build ad-hoc harnesses to re-run workflows from scratch with tweaked prompts, and rarely get to ask the most useful question: *"if I had changed X at step N, would the rest of the trajectory have succeeded?"*

Existing platforms (Langfuse, LangSmith, Phoenix) capture traces well and offer per-LLM-call playgrounds or span replay. None publicly document a real interactive multi-step fork-and-resume against captured production traces with managed tool side effects, persistent branch-tree comparison, and post-training-tuned dataset export from forked branches. Laminar and LangGraph Studio are the closest direct competitors: Laminar publicly ships rerun-from-step and dataset workflows, while LangGraph Studio ships true checkpoint fork semantics for LangGraph apps. Public docs do not show either product combining framework-agnostic production trace ingest, per-tool side-effect policy, persistent branch trees, and forked-trajectory dataset export.

This service ingests OpenTelemetry traces from agent workflows, captures the state needed to resume execution from any step, and lets users intervene (edit prompts, swap tools, force tool calls, alter context) and play the rest of the workflow forward. Branched trajectories form a persistent tree against the original trace, with comparison views and provenance-tracked dataset export.

### Lessons applied to ForkReplay's design

Production research on agent debuggers and intervention-driven trajectory tools has settled on a small number of principles that shape ForkReplay's V1 design:

- **State-checkpoint-at-step-boundary is the right primitive.** The highest-leverage capture point is just before each agent decision — full agent state at the boundary, not span-level event capture. Without checkpointed state, "rerun from here" devolves into "rerun from scratch with hope." ForkReplay treats frames (per-step normalized state) as a first-class storage layer alongside spans precisely because rerunning from a checkpoint is the only honest fork semantics for nondeterministic agents.
- **Intervention requires a diff overlay, not just a re-execution.** "Did my edit actually change anything?" is the first question users ask; "what did it change?" is the second. Effect attribution — first divergent step, first divergent tool call, structural similarity — is more valuable than the raw branch trajectory by itself. ForkReplay's branch comparison view is the surface that answers these questions.
- **Cheap, repeated forks are how users learn.** Single-shot debugging on a nondeterministic system gives misleading signal. The product loop that builds confidence is: fork → see result → fork again with a different intervention → compare. Persistent branch trees and forks-of-forks are not exotic features; they're the basic workflow once users understand what the fork affordance actually buys them.
- **Validation by replay, not by hypothesis.** Failure analysis on agent traces typically generates LLM-judged hypotheses about what went wrong. Hypotheses without experimental validation are unreliable; the practical step is to translate each hypothesis into a concrete intervention (edit a message, swap a tool result, change a model) and run it forward. The intervention manifest is the operationalized form of this insight.
- **The right granularity for fork is a logical step, not a span.** Spans are a measurement granularity, not a semantic one. Users want to intervene at the level of "the LLM decision," "the tool call," "the sub-agent invocation" — not at "the HTTP call." Stitching spans into logical steps is what makes the fork affordance comprehensible.

## 2. Goals & Non-Goals

### Goals
- Preserve framework agnosticism as a product moat: ForkReplay captures and normalizes traces from existing agent runtimes rather than prescribing a runtime or becoming a new agent framework.
- Ingest OTLP traces with supported GenAI/framework mappings plus a first-party adapter SDK for fork-grade capture.
- Capture complete state needed to fork and resume execution from any step.
- Allow users to fork from any point with a rich set of interventions: edit prompts, change tool definitions, force tool calls/results, edit prior messages, swap models, override sampling.
- Re-execute branches against live LLM APIs with explicit per-tool execution policies (V1: mock-only with AI-generated first-pass mocks; V2: live-tool execution).
- Maintain persistent **branch history** for each trace — multiple branches from the same point, branches off branches, all comparable.
- Visualize divergence and effect attribution between original and branched trajectories with overlay/highlight comparison.
- Export labeled trajectories as explicit SFT/preference/custom/HuggingFace dataset dialects, with provenance.
- Convert any trace or branch into an evaluation test case ("trace → test case in CI").

### Non-Goals (V1)
- **No built-in billing or metering.** ForkReplay self-host ships no payment, invoicing, usage-meter, or credit system. Operators who want to charge for access bring their own billing layer in front of the product. Only operational quotas (`WorkspaceLimits`) ship.
- **ClickHouse is a required dependency, not an optional add-on and not Postgres-substitutable.** The columnar span/frame analytics store is mandatory in every deployment mode. Operators cannot run ForkReplay on Postgres alone. (Control-plane Postgres is pluggable via `DB_MODE`; the *analytics plane* is not.)
- Replacing general-purpose observability platforms (Datadog, Honeycomb, etc.).
- Being a prompt engineering / prompt versioning tool.
- Being a full evaluation framework. Branches are *inputs* to evals; we don't ship judges, scorers, or assertion DSLs in V1.
- Being the agent runtime itself.
- Being a browser session replay product. Browser screen recording, DOM/action timelines, and user-interaction playback are out of scope; we care about the agent trajectory itself.
- Live tool execution from forks (deferred to V1.1 / V2).
- TypeScript adapter SDK (V2+; not on the V1.1 roadmap).
- A hosted/managed multi-vendor SaaS offering operated by the ForkReplay team. (A managed offering may be reconsidered later, but it is *not* the V1 product — V1 is the self-hostable OSS distribution.)
- Built-in judges/scorers/assertion DSLs.

## 3. Personas

- **Anika, ML Platform Engineer.** Owns the agent stack at a SaaS company. Debugging customer-reported failures eats her week. Wants to grab a trace, fork at the broken turn, prove the fix works, ship it.
- **Marcus, Applied Research Engineer.** Curating data for a custom-trained tool-using model. Today writes one-off scripts to mine production logs. Wants traceable, well-labeled trajectories.
- **Priya, QA / Eval Engineer.** Reproduces issues for engineering. Needs deterministic-as-possible re-execution from a known good state with a single variable changed.

## 4. Key Concepts & Terminology

We deliberately avoid the word "replay" in product surface because LLM execution is non-deterministic and tool side effects don't unhappen. Instead:

- **Trace** — the original captured execution. Immutable.
- **Step** — a logical unit of agent work (one LLM call, one tool execution, one sub-agent invocation). Reconstructed from the OTel span tree.
- **Fork point** — the step at which a user intervenes.
- **Intervention** — the change applied at the fork point: edited prompt, modified tools, forced tool call/result, swapped model, etc.
- **Branch** — the new trajectory produced by execution after the fork point. Branches are first-class objects with their own ID, parent pointer, and intervention manifest.
- **Branch tree** — the directed graph of original trace + all forks + forks-of-forks. A core UX primitive; branch comparison is the default debugging workflow.
- **Frame** — the captured state at a step boundary that's sufficient to fork from there: message history, tool catalog, model + sampling config, system prompt, and any external context (RAG hits, memory).
- **Tenant / Workspace** — the unit of multi-tenant isolation. Owns its own data, LLM provider configuration, operational quotas, user/role membership, and audit log. The multi-tenant core is retained; a self-hoster who only needs one tenant runs the documented single-tenant (default-workspace) quickstart, which is the same code path with one workspace.
- **Operator** — whoever deploys and runs a ForkReplay instance (the self-hoster). The operator configures the deployment mode, the LLM routing backend, object storage, email transport, secret/KEK handling, and the default `WorkspaceLimits`.
- **Operator quotas (`WorkspaceLimits`)** — operational limits enforced per workspace: concurrency, branch depth, branch wall-clock time, per-branch token volume, AI-mock generation count, retention. These replace the old "replay credits" concept entirely — there is no usage currency, no billing meter, and no credit ledger in self-host. Quotas exist to bound resource consumption, not to bill for it.
- **Informational cost estimate** — a best-effort pre-fork projection of LLM spend, computed from an operator-maintainable model rate card. It is *informational only*: ForkReplay does not invoice, meter, or settle against it. The operator's own LLM-provider invoice is authoritative.

### Three-layer data model

To support both fidelity and convenient operation, we maintain three layers:

- **Spans** — the OTel data, immutable, source of truth. Direct passthrough from ingest.
- **Frames** — denormalized step-boundary projections suitable for resume. Recomputable from spans.
- **Messages** — the chat-format abstraction the UI works with for prompt edits.

The UI works on messages, the engine resumes from frames, the storage of record is spans. This is the AGDebugger paper pattern with explicit `save_state`/`load_state` semantics borrowed conceptually but framed for OTel-instrumented production traces rather than a runtime debugger.

## 5. Core Use Cases

1. **Failure root-cause analysis.** "The agent looped on tool X at turn 12. If I make the tool description clearer, does it stop looping?" — fork at turn 12, edit the tool description, run forward, observe.
2. **Counterfactual prompt edits.** "Would a different system prompt have prevented this hallucination?" — fork at turn 1, swap system prompt, compare branch to original.
3. **Forced-correction trajectories.** "What does success look like from here?" — fork at the bad step, manually inject the correct tool call, let the agent finish, save as a positive example.
4. **Model A/B at a known state.** Fork at turn N twice with two different models, compare resulting trajectories on identical preceding context.
5. **Multi-branch exploration.** Fork the same step five different ways with different interventions, view them all on the tree, identify which intervention produced the desired outcome.
6. **Dataset curation.** Mark branches as "preferred" / "rejected" relative to the original. Export as preference pairs or supervised trajectories.
7. **Trace-to-test conversion.** Take a trace (or a forked branch), convert into a test case that re-runs in CI with assertions.

## 6. Critical Design Questions & Answers

### Q1. What does a fork actually execute against — real tools or stubs?

**V1: mocks only, with AI-generated first-pass mocks.** Each tool registered with the service is tagged with an **execution policy**:

- `mock` — return a static or parameterized mock response. (V1 default for unmarked tools.)
- `ai_mock` — generated mock built by an LLM call from the original tool I/O captured in the trace; user can edit. (V1 headline feature.)
- `block` — refuse to execute; the branch errors at this step.

**V2 adds:**
- `live` — run against the real implementation (HTTP, executable code).
- Side-effect classification on tool definitions:
  - `read_only`
  - `idempotent_write`
  - `compensatable_write`
  - `irreversible_write`
- Optional idempotency keys, compensation handler metadata, branch-level side-effect ledger, and human approval gates for irreversible live actions.

**Why mocks-only in V1:** keeps the surface area tractable, avoids the auth/credential management problem for live tools, and the AI-generated mock is genuinely useful UX. Limitations to communicate clearly:

- **Stateful tool sequences** — if tool A returns `order_id=42` and tool B uses it, mocks need to be parameterized (function of input) to handle behavior divergence in branches. The V1 AI-generated mock will attempt parameterization but will need user refinement for non-trivial tools.
- **Schema fidelity** — the mock must return data the LLM accepts as plausibly real. Auto-generated mocks should preserve schema even when content varies.

### Q2. Which OTel conventions are supported, and what about non-conformant SDKs?

V1 targets OpenTelemetry GenAI semantic conventions (`gen_ai.*`) as the public interoperability surface, but not as our internal contract. As of May 6, 2026, OTel GenAI conventions are still marked Development, and current instrumentation may emit older or experimental convention versions. V1 therefore stores an internal normalized trajectory schema and version-tags every imported convention/source mapping.

**Two ingest tracks:**

1. **Passive track.** Any valid OTLP trace can be ingested for read-only viewing — trace browser, span inspector, search. GenAI-aware UI requires current OTel GenAI attributes, older supported GenAI mappings, OpenInference-compatible mappings, a known framework integration, or our adapter. Supported integrations must be documented by support level: native OTel, framework OTel integration, third-party instrumentor, custom processor, or generic OTLP only.
2. **Active track.** Fork-and-resume requires the **first-party adapter SDK** (Python in V1) at capture time. The adapter emits standardized step-boundary annotations, captures tool schemas at the time of the call, and (optionally) emits state checkpoints for stateful agents. Without the adapter, fork-and-resume is best-effort and fragile for non-trivial agents.

This split is honest about the tradeoff: passive viewing for any trace, full forking for traces captured with our cooperation. It also gives us a clear value prop for our SDK over generic OTel exporters.

### Q3. How are logical agent steps reconstructed from a flat span tree?

A **stitching pipeline** runs on ingest:

1. Group spans by `gen_ai.conversation.id` if present, falling back to inferred session via parent-child + temporal heuristics.
2. Identify step boundaries: every `gen_ai.operation.name` chat/model span, every `execute_tool` span, every nested agent or workflow invocation.
3. Build a directed acyclic graph of steps with dependency edges from message history (a tool result span is a dependency of the next chat span that includes it).
4. Persist the original span tree alongside the reconstructed step DAG. Both are addressable.

**Framework-specific stitchers** are pluggable compatibility layers. They must map into ForkReplay's canonical trace/frame/message/tool contracts rather than making any framework's state model the product's internal model. Reference stitchers ship for LangGraph, LlamaIndex, Pydantic AI, smolagents, Strands Agents, AutoGen, CrewAI, and OpenAI Agents SDK where processor/instrumentor support makes the trace shape reliable. Users can register their own.

For active-track captures, the adapter SDK emits explicit step-boundary spans, which makes reconstruction trivial and high-fidelity.

### Q4. What's the deployment model?

**Self-hostable open source.** ForkReplay is a single Apache-2.0 codebase the operator runs on their own infrastructure. There is no managed-SaaS dependency; every external service is either bundled OSS or pluggable.

**Three deployment paths:**
- **docker-compose** — the quickstart. One command brings up the FastAPI services, the Next.js workbench container, GoTrue, a bundled Postgres, a bundled ClickHouse, Temporal, NATS, Redis, and MinIO. Intended for evaluation, single-node, and small-team self-host.
- **Helm** — the Kubernetes path for operators running a cluster. ClickHouse, Temporal, NATS, and Redis are required chart dependencies (or pointed at managed equivalents the operator already runs); Postgres is selected by `DB_MODE`.
- **Terraform** — reference modules for **AWS** and **Azure** that stand up the same topology on managed primitives (e.g., managed Postgres, S3/Azure Blob, a ClickHouse deployment) where available.

**Control-plane database is pluggable** via `DB_MODE`:
- `DB_MODE=supabase` — point at a managed or self-hosted Supabase (Postgres + GoTrue).
- `DB_MODE=custom` — bring your own Postgres; GoTrue is run as a bundled container against it.
- `DB_MODE=compose` — a fully bundled Postgres container, zero external dependencies.

In **all** modes, GoTrue is the auth provider and the app validates GoTrue JWTs, and **ClickHouse is required** — it is the columnar span/frame store and is not interchangeable with the control-plane Postgres. The pluggability is deliberately scoped to the control plane so operators are not surprised by the ClickHouse requirement.

**Why OSS self-host:** debugging agent traces is most valuable where the traces actually live, and those traces frequently contain sensitive prompts, tool I/O, and customer data that teams will not send to a third-party SaaS. Shipping the product as self-hostable OSS removes the data-residency and trust barriers that block adoption, and lets operators run it inside their own VPC, air-gapped network, or regulated environment. The multi-tenant core is retained so a single deployment can serve multiple teams; the single-tenant quickstart covers the common "one team, one instance" case without extra ceremony.

### Q5. How are quotas, LLM keys, and cost visibility handled?

**There is no built-in billing, no subscription, no replay credits, and no usage meter.** ForkReplay self-host does not charge anyone for anything. Resource consumption is bounded by **operator-configured quotas**, not by a currency. Operators who want to bill their own users do so in a layer of their own outside ForkReplay.

**Operator quotas (`WorkspaceLimits`):**
- Every workspace has operator-settable limits: concurrent branches, branch wall-clock time, branch depth, max steps per branch, per-branch token volume, AI-mock generations, retention window, and seats.
- Quotas are operational guardrails against runaway forks and storage blowups — not a sales lever. There is no overage charge; exceeding a limit blocks or pauses the run.
- The operator sets defaults globally and can override per workspace via the admin panel.

**LLM routing (pluggable):**
- ForkReplay has an internal model-provider interface with **multiple pluggable backends selected by config**:
  - **OpenRouter** — single key, broad model catalog, provider routing.
  - **Direct OpenAI / Anthropic** — operator points the router at a first-party provider key.
  - **Ollama** — fully local/self-hosted models, no external provider at all (the natural fit for air-gapped deployments).
- The routing backend is an operator/workspace setting. A workspace can override the operator default (e.g., one team on Ollama, another on a direct Anthropic key).
- The fork executor reads the effective routing config per branch and records the requested model, resolved model, routing/fallback policy, and execution provenance in branch metadata.

**Keys & BYOK (operator/workspace-configured):**
- LLM provider keys are supplied as **operator or workspace keys via env/secret**. There is no Vault.
- For at-rest protection beyond the secret store, ForkReplay supports an **optional KEK** (age/libsodium): provider keys can be envelope-encrypted with an operator-held key-encryption key so that the control-plane DB never stores plaintext provider credentials.
- Decrypted keys live in process memory only for the duration of one outbound model call and are never logged. A `Bearer **redacted**` log filter is mandatory.
- Because the operator owns the keys and the LLM-provider account, the **provider invoice is authoritative**. ForkReplay never settles spend.

**Cost visibility (informational only):**
- ForkReplay can show a **pre-fork informational cost estimate** computed from an operator-maintainable model rate card (per-model input/cached/output/reasoning rates). This is a convenience for the operator's own awareness; it is **not** a meter, not a charge, and not reconciled against anything.
- When a model has no separate reasoning rate, the reasoning line is labeled "Reasoning (billed at output rate)" purely for estimate display.

**Privacy posture:**
- The operator chooses the privacy posture for routed providers. With OpenRouter, the workspace can set `provider.data_collection` and `provider.zdr`; with Ollama the data never leaves the operator's infrastructure at all. The substitution dialog explains when a stricter posture would shrink the routable-provider set.

### Q6. How are streaming completions captured and forked?

Three modes, in priority order:
1. **Post-stream span finalization** (preferred): instrumented SDKs emit a single span when the stream closes, with the full assembled message in span attributes/events.
2. **Streaming span events**: SDKs that emit per-chunk events get reassembled at ingest.
3. **Out-of-band capture**: the adapter SDK supports `capture_stream(stream)` that wraps a stream iterator and emits a finalization span.

For the UI streaming layer, V1 uses an internal branch-event stream suitable for Server-Sent Events between the backend and the product UI. **AG-UI Protocol** is deferred until after V1 as a clean agent-facing interface for iterative branching and debugging workflows; it is not required for the initial human-operated product loop.

For forking, the service operates only on finalized messages. Mid-stream forks are out of scope — fork granularity is at step boundaries.

### Q7. Multi-agent and parallel spans at fork points?

The forked branch follows the original framework's parallelism model. If the captured trajectory had two parallel sub-agents at step N, the fork at step N runs both in parallel using the same orchestration the original used.

A fork point is always a single step in the parent's view. For multi-agent systems with concurrent sub-agent spans, the user can either:
- Fork at the parent step and re-execute all sub-agents, or
- Fork at one specific sub-agent's step, in which case the other sub-agents' outcomes are taken from the original trace as fixed.

The intervention manifest records which sub-agents are "real" vs "fixed-from-original" so divergence visualization is honest.

**Framework-specific parallelism handlers** are pluggable. Different frameworks (LangGraph Send, AutoGen GroupChat, CrewAI crews) implement parallelism differently; we ship handlers for each supported framework.

### Q8. Three-layer model — is it really worth the complexity?

Yes, and it should be committed to from V1 to avoid retrofitting. Concrete example: a user wants to "edit the system prompt at step 3."
- The UI shows them the system prompt as an editable message (messages layer).
- They edit and click "fork from here."
- The engine constructs a new frame with the edited system prompt + original conversation up to step 3 (frames layer).
- Execution proceeds from the new frame, producing new spans (spans layer) tagged with the branch ID.
- The original spans for step 3 onward in the parent trace are untouched.

### Q9. How is divergence visualized?

The trace view defaults to a **DAG of the agent workflow**:
- Nodes = agent queries or responses (each clickable for full details: tools passed in, prompts, tool calls with parameters, model, etc.).
- Edges = tool calls (including spawning sub-agents), labeled with tool name and a brief input/output preview.
- The full original trace shows as a primary path; branches appear as additional paths off their fork points.

A branch selector switches focus between the original and any specific branch. A **comparison mode** overlays multiple branches:
- Selected branches render in full color.
- Non-focused branches dim to a muted color.
- Hovering over a node or edge brightens the entire branch that node/edge belongs to, making lineage clear.
- Up to three branches comparable simultaneously in V1.

A side-by-side step-diff view is available on click, showing per-step differences in messages, tool calls, and tool results between the original and the branch.

Comparison must also answer the practical debugging question: **did my intervention materially change the run?** V1 should include a branch effect summary:
- First divergent LLM decision.
- First divergent tool call or tool result.
- Whether final outcome changed.
- Similarity score between original and branch continuation.
- "No material divergence detected after N steps" warning.
- Token/cost/latency delta between compared trajectories.

Because LLM execution is nondeterministic, users can run repeated trials for the same intervention. A repeated-trial group records the same intervention manifest executed K times, then summarizes success rate, failure modes, variance, token/cost, and representative trajectories.

### Q10. Export formats for post-training datasets?

V1 GA ships three bundled exporters, hard-coded on top of a thin internal mapping interface. The full schema configuration engine ships in V1.1; the additional dialects below are V1.1 work behind feature flags (no preview surface in V1).

**V1 GA (hard-coded):**
- **Generic trajectory JSONL** — our canonical trajectory schema for customers who want full branch/step/tool fidelity.
- **Generic JSON test case** — the trace-to-test default output.
- **Promptfoo test case** — first CI-friendly target.

**V1.1 (behind `exporters.v1_1` feature flag; not preview-runnable in V1):**
- OpenAI-compatible SFT JSONL
- TRL/HuggingFace SFT
- OpenAI/Together-style preference JSONL
- TRL DPO
- HuggingFace dataset package
- Inspect, Braintrust, LangSmith test-case mappings

V1 must preserve enough provider-specific structure to avoid lossy exports:
- OpenAI-style `tools` / `tool_calls` / `tool` role messages.
- Anthropic-style content blocks, `tool_use`, and `tool_result`.
- Gemini-style `systemInstruction`, `contents`, `parts`, and function declarations.
- MCP-style tool descriptors where present.

The **schema configuration engine** is V1.1. At V1 GA, the three exporters above are bundled mappings on top of a thin internal interface; V1.1 replaces that interface with the full user-configurable engine without re-authoring the exporters.

Every exported example carries a `provenance` field linking back to workspace, trace, branch, step, label, source query, exporter version, and redaction policy version. Non-negotiable for reproducibility and auditability.

### Q11. Model version drift between capture and fork?

Captured frames record the exact model identifier (`claude-opus-4-7`, `gpt-4.1-2025-04-14`, etc.). Forks default to the captured model. The user can override at fork time — useful for "how would model X have handled this?" experiments.

The fork engine surfaces the model-substitution dialog on any of the following triggers, and we never silently substitute:

- **Full unavailability** — the captured model is no longer routable on the configured routing backend (OpenRouter catalog, the direct provider's available models, or the operator's local Ollama model set).
- **Dated-version supersession** — the captured trace pinned a dated version and that dated version has been superseded by a rolling alias. Rolling aliases are allowed by default per workspace, but the user must explicitly accept the substitution.
- **Provider mismatch** — the captured provider slug is not available for the resolved model on the configured backend.
- **Capability gap** — requiring exact parameters would shrink the routable provider set to zero (e.g., we need `tool_choice: required` and the captured provider's endpoint for this model doesn't expose it).
- **Workspace policy elimination** — the workspace's `data_collection`/ZDR posture eliminates the captured provider's endpoint (applies to routing backends that expose multiple provider endpoints, e.g., OpenRouter).

The substitution dialog records the resolution in the branch's intervention manifest. Cross-provider model swaps (e.g., Anthropic-original → OpenAI) drop `reasoning_details` with a warning (V1). Lossy re-translation of reasoning blocks is deferred to V1.1+.

### Q12. Where's the line between this and an evals platform?

This **is** an evals platform — but evals are downstream, not the front door. The product entry point is debugging: fork a failed trace, find what fixes it. The same data that enables debugging produces evaluation cases, datasets, and test conversions. We ship "convert this trace/branch into a test case" as a V1 feature.

We do not ship judges, scorers, or assertion DSLs in V1. These are well-served by the eval ecosystem (Promptfoo, Inspect, custom scorers). Our hooks for branches → eval harnesses are webhooks and a Python SDK for inline eval functions.

## 7. Functional Requirements

### 7.1 Ingestion
- OTLP/HTTP and OTLP/gRPC receivers exposed as a **FastAPI OTLP endpoint** in the ingest/api service that authenticates workspace API keys and publishes raw batches onto **NATS**.
- **NATS** sits between OTLP receive and stitch/redact/write (Phase 1) as the back-pressure buffer; the ingest worker consumes from it. (Redis Streams is documented as an alternative queue backend for operators who already run Redis and would rather not add NATS.)
- First-party adapter SDK (Python only in V1; TypeScript SDK is V2+).
- `forkreplay-auto` one-line bootstrap (`import forkreplay.auto`) auto-detects already-installed framework instrumentors via `importlib.metadata` and calls each adapter's `.instrument()`. **Install posture:** the `forkreplay-sdk[auto]` extra pulls in only the auto-detection module; users must install per-framework extras (`[langgraph]`, `[claude]`, `[openai-agents]`, etc.) explicitly for each integration they want auto-instrumented. `[auto]` does not transitively pull all nine framework instrumentors.
- Auto-instrument behavior is controlled by three env vars (silent no-op when unset): `FORKREPLAY_AUTO_INSTRUMENT=1` (opt-in bootstrap via `.pth`, no application-code edit required), `FORKREPLAY_AUTO_SAMPLE=0.1` (probabilistic drop at the SDK before OTLP gateway), `FORKREPLAY_AUTO_DISABLE=1` (hard kill-switch for security-sensitive BYOK customers), `FORKREPLAY_VERBOSE=1` (INFO-level logs from the auto-instrument path; silent by default).
- Batch import from JSON/Protobuf trace files.
- Configurable retention per workspace (default 90 days).
- PII redaction policies applied at ingest (regex-based + pluggable).
- Store semantic convention version/source per span and normalize into ForkReplay's internal trajectory schema.
- Content capture is explicit opt-in. Prompts, outputs, tool arguments, and tool results may contain sensitive data and must pass ingest-time redaction.
- Active-track adapter capture must include normalized messages, tool schemas, tool call IDs, tool arguments/results, model/sampling config, framework state/checkpoints, and checkpoint fidelity metadata.
- Checkpoint fidelity metadata records: fidelity level (`exact`, `schema_equivalent`, `approximate`, `unrestorable`), captured state fields, missing external state, restore confidence, and user-visible caveats.

### 7.2 Storage & Indexing
- Spans stored in columnar format in **ClickHouse** (required dependency in every deployment mode; bundled OSS in compose).
- Frames live in **S3-compatible object storage** (MinIO in compose / AWS S3 / Azure Blob) as content-addressed blobs (JCS canonicalization + SHA-256, workspace-scoped key prefix); the control-plane Postgres holds pointer rows. **Messages are embedded inside frame blobs** (not first-class storage). 5 MB hard cap per frame, 1 MB soft warning. Externalize per-item blobs above 256 KB.
- ClickHouse holds a separate denormalized search projection for messages and tool I/O; the message search projection itself ships in V1.1 (V1 reads frames from object storage directly).
- Frame content-addressing scope is **per workspace** (no cross-tenant blob sharing).
- Tenant isolation follows **defense-in-depth policy isolation, automated test-enforced**: workspace scoping on every query, native Postgres Row-Level Security (RLS) policies, ClickHouse row policies on the workspace_id column, object-storage key-prefix isolation, and a CI-enforced tenant-isolation conformance test that fails the build if any policy is missing or misconfigured.
- Vector index over messages (optional, opt-in) for similarity search across traces in the same workspace — V1.1.

### 7.3 Trace UI
- Trace list with filtering on session, user, model, error, latency, cost, custom tags.
- Trace detail: DAG visualization (nodes = agent queries/responses, edges = tool calls), span tree fallback, message timeline, tool call inspector. DAG renderer is interactive at **≤2k step-DAG nodes**; larger traces use progressive disclosure / lazy expansion / collapsing.
- Per-step inspector: full request/response, token counts, latency, and an informational cost estimate (token-derived). Per-step fidelity badge (`exact` / `schema_equivalent` / `approximate`) rendered at every forkable step.
- Branch-tree-first navigation: every trace shows its tree of forks alongside the trace itself.
- Sessions view: traces sharing the same `gen_ai.conversation.id` (or framework-equivalent attribute) are grouped chronologically; each trace remains independently forkable. Cross-trace step continuation is V1.1+.

### 7.4 Fork & Intervention
- "Fork from here" action on any step.
- Intervention editor:
  - Edit message history (insert, delete, modify any prior message).
  - Edit system prompt.
  - Edit tool catalog (add, remove, modify schemas).
  - Force a specific tool call (skip the LLM decision for this step).
  - Force a specific tool result (skip live execution).
  - Override sampling parameters (temperature, top_p, max_tokens).
  - Swap model.
- Guided intervention templates:
  - Make instruction more specific.
  - Simplify into one subtask.
  - Change plan / route / tool strategy.
  - Correct tool result.
  - Inject missing fact/context.
- Adapter-supplied agent capability contracts are displayed in the editor where available: agent role, accepted message shapes, tool affordances, max task granularity, known constraints, and examples.
- Intervention manifest is human-readable JSON, persisted, and versioned.
- Forks are first-class objects: they have IDs, parents, names, tags, owners.
- **Forks of forks are supported recursively.**

### 7.5 Fork Execution Engine
- Execute branches asynchronously through **Temporal** (workflow + activity model) for **every step including the first**; stream progress to the workbench via **FastAPI SSE backed by Redis pub/sub**, with `Last-Event-ID` reconnect.
- Per-tool execution policy (Q1): V1 = mock / ai_mock / block.
- AI-generated mock workflow: when a fork includes a tool that previously executed, the engine offers a one-click mock built by analyzing the original tool I/O from the captured trace. AI-mock generation uses the operator-configured AI-mock model via the routing backend (configurable in the admin panel; a small/fast model is the sensible default — e.g., a Flash/Haiku-class model, or a local Ollama model in air-gapped deployments).
- Resolves the effective LLM-routing config (operator default → workspace override) per branch and dispatches accordingly. For multi-endpoint backends (e.g., OpenRouter) every request pins `provider.allow_fallbacks: false`, `provider.order: [<captured-provider>]`, and `provider.require_parameters: true` by default; workspace admins may opt INTO controlled fallback with an explicit allowed-providers list. Single-endpoint backends (direct provider, Ollama) ignore the provider-envelope knobs.
- Hard timeouts per branch (default 10 min, configurable). 25-minute hard cap on a single model call (Temporal `await`-on-signal pattern for very long waits is V1.1, conditional on demand signal).
- Activity retry policy: operator-configured `workflow_step_retries` per-step max (operational quota; default within `WorkspaceLimits`, user-configurable in the fork editor up to the configured max).
- Resumable execution if a branch fails partway (Temporal durable execution).
- Branches can be forked again — full tree.
- Repeated-trial execution: run the same intervention K times, subject to workspace limits, and group results under one trial set.
- Branch effect summary generated after completion: first changed decision, first changed tool call/result, final-outcome change, similarity score, token/cost/latency delta, and no-material-divergence warning.
- Cancellation: in-flight model calls aborted within 3s p95 of user-initiated cancel via AbortSignal propagation to the routing backend (Temporal activity cancellation).

### 7.6 Multi-tenancy & Workspace Isolation
- Workspaces are the tenant primitive. Every trace, branch, dataset, and audit log entry is owned by exactly one workspace.
- Per-workspace LLM-routing config: the operator default applies unless the workspace registers an override (different backend or key).
- Per-workspace user/role membership (admin, editor, viewer).
- Per-workspace audit log: every fork execution, dataset export, configuration change, and access event is logged.
- Tenant isolation is **defense-in-depth, automated test-enforced**: native Postgres RLS on every tenant-scoped table, ClickHouse row policies on the workspace_id column, workspace-prefixed S3-compatible object storage, and a CI-enforced tenant-isolation conformance test that runs on every PR. Cross-workspace data leak is a P0 incident.
- Per-workspace API keys for SDK ingest and programmatic access. API key scopes follow the verb-on-resource taxonomy (`traces:read`, `traces:write`, `branches:read`, `branches:write`, `exports:read`, `exports:write`, `mocks:write`, `mocks:approve`, `workspace:admin`).

### 7.7 Resource Quotas & Cost Visibility
There is no billing in self-host; this section is about bounding resource use and giving the operator visibility, not charging anyone.
- Per-workspace operator quotas (`WorkspaceLimits`): concurrent branches, branch wall-clock time, branch depth, max steps per branch, per-branch token volume, max tool invocations, max stored artifacts/log volume, AI-mock generations, and retention.
- Threshold alerts on token-volume quotas at 50%, 75%, 90%, 100% of the configured limit, configurable per workspace, delivered via email (operator SMTP) and webhook.
- Hard per-fork token/step caps (admin-configurable per workspace) — branches that would exceed the cap are blocked at start. Hard cap default = estimate upper_bound × 1.5.
- Pre-fork **informational cost estimate** displayed in the intervention editor before the user clicks "run." Estimate based on captured trajectory's token volume + intervention type, computed from the operator's model rate card. **Estimate-accuracy SLO: ±20%**, displayed as a low–high range (e.g., "100–150 (est.)"), not a single number. The estimate is informational only — nothing is metered or charged against it.
- Reasoning-token cost is shown as a **separate line item** in the pre-fork estimate, with sub-totals (reasoning + output) and a grand total (input + output + reasoning). When a model has no separate `reasoning_rate` in the rate card, the line is labeled "Reasoning (estimated at output rate)."
- Tool-catalog edits invalidate the first-turn prompt cache. The estimator shows the cache-bust delta side-by-side with the unedited estimate.
- Auto-pause on quota exhaustion: forks are blocked until the admin manually re-enables or raises the limit.
- Pre-run estimates are non-binding. If actual execution approaches a hard cap, execution stops at deterministic boundaries before the next model or tool call.
- LLM token usage is tracked per workspace on a rolling 30-day window for visibility. Admins can configure alert and cutoff thresholds (default off). When the cutoff threshold is hit, the workspace is soft-throttled (branches refuse to start) until the admin acks or raises it. Usage is surfaced on the operator's analytics dashboards. (The actual provider invoice — if any — comes from the operator's own LLM-provider account.)
- All quotas and rate-card values are configurable per workspace via the V1 admin panel (the 5-item admin panel scope: per-workspace limits, auth-policy, member management, LLM-routing/key config, retention/redaction).
- AI-mock generation cap: a per-workspace limit on model calls for ai_mock creation, configured as an operator quota (default 200/month, raisable per workspace; unlimited if the operator chooses).
- `workflow_step_retries` is an operator quota (per-step activity retry max), defaulted in `WorkspaceLimits` and admin-overridable per workspace.
- Anomaly detection on token consumption (sudden spike = alert) — V1.1.

### 7.8 Dataset Curation
- Dataset and post-training export are secondary V1 workflows behind trace-to-test/eval-case export, but the schema configuration engine is V1-critical.
- Per-trajectory and per-step labels (free-form tags + structured `quality: good|bad|preferred`).
- Pair builder: select two branches, label as chosen/rejected → preference pair.
- Dataset = saved query over labeled trajectories within a workspace.
- Dataset snapshots are deterministic and versioned; saved queries produce immutable export snapshots with source query, schema version, exporter version, redaction policy version, and validation report.
- Schema configuration engine: user-defined mappings over standardized internal data keys; built-in formats are bundled mappings on top of the same engine.
- Built-in export formats: OpenAI-compatible SFT JSONL, TRL/HuggingFace SFT, OpenAI/Together preference JSONL, TRL DPO, HuggingFace dataset package, generic trajectory JSONL.
- Export configuration includes loss-mask policy: all assistant turns, final assistant only, tool-call turns only, or custom per-message weights where supported by the target format.
- Preference export configuration defines whether chosen/rejected comparisons cover final response only, selected step continuation, or full downstream trajectory.
- Export jobs produce accepted-row and rejected-row reports with reasons.
- Export jobs run async; deliver to S3, ADLS Gen2, GCS, or signed download URL.

### 7.9 Trace-to-Test Conversion
- "Convert to test case" action on any trace or branch.
- Generates a structured test definition with the trace inputs, expected outputs, and step-level assertions (configurable).
- Target formats: generic JSON, Braintrust-style dataset row, Promptfoo test case, Inspect `Sample`, and LangSmith example.
- Assertion taxonomy:
  - final-output assertions
  - step-level assertions
  - tool-call assertions
  - tool-result assertions
  - ordering assertions
  - latency/cost assertions
  - side-effect assertions
- Webhook + Python SDK hooks for sending tests to user-defined eval harnesses or CI systems.

### 7.10 Access Control
- Workspace roles: admin, editor, viewer.
- Per-trace ACLs for sensitive captures within a workspace.
- Audit log of all fork executions, exports, and configuration changes (see 7.6). Audit retention: **13 months hot in Postgres** (monthly partitions, write-once GRANTs), then **7 years cold** in immutable object-storage Parquet + JSONL archive (operator-configured retention/object-lock policy).
- V1 auth baseline: **GoTrue** (Supabase Auth OSS), bundled in all DB modes, with email + password registration and federated login using GoTrue-supported OAuth/OIDC identity providers. The app validates GoTrue JWTs everywhere; authorization is ForkReplay workspace/role based.
- Enterprise SSO/provisioning (SAML/SCIM) is V1.1+.

## 8. Non-Functional Requirements

- **Ingestion throughput (launch goal subject to Phase-0 spike validation):** sustained 10k spans/sec per node.
- **Trace open latency:** p95 < 1.5s for traces up to 10k spans.
- **Fork start latency (launch goal subject to Phase-0 spike validation):** p95 < 3s from "fork" click to first LLM call dispatched, validated against the Phase-0 fork-start spike. The plan accepts up to 4s p95 if the Phase-0 spike shows that Temporal workflow bootstrap (Temporal orchestrates every step including the first) pushes us there. Any slip beyond 4s comes back for discussion. (Measured on the reference compose topology; actual latency depends on the operator's hardware.)
- **Cancellation latency:** p95 < 3s from user cancel click to in-flight model call abort.
- **Storage:** content-addressed deduplication target ≥ 5x reduction on real workloads.
- **Availability:** Availability is the **operator's responsibility** — there is no SLA from the ForkReplay project because the project does not run the service. ForkReplay ships health/readiness endpoints and an optional self-hosted OTel collector + Grafana/Prometheus stack so operators can run their own uptime probes and dashboards. Operational status is surfaced in-product via the `system_banners` mechanism (FastAPI/Redis-backed banner channel) for the operator to broadcast maintenance/incident notices to active workbench sessions.
- **Security:** at-rest encryption and TLS in transit are the operator's deployment responsibility (the Helm/Terraform references configure them). LLM provider keys are supplied via env/secret and may be envelope-encrypted with an **optional operator-held KEK** (age/libsodium) so the control-plane DB never stores plaintext. Decrypted keys live in process memory only for the duration of one outbound call and are never logged (`Bearer **redacted**` filter is mandatory and CI-enforced). There is no Vault dependency.
- **Compliance posture:** Self-host puts data residency and compliance posture in the **operator's** hands — they choose where the instance runs and which LLM backend (including fully local Ollama) it routes to. The ForkReplay project does not pursue SOC 2 / HIPAA attestations for a service it does not operate; operators may seek their own attestations for their deployment. ForkReplay aims to make GDPR-compliant data handling *achievable* (redaction at ingest, retention/deletion controls, audit trail) but does not certify it.
- **Tenant isolation:** **defense-in-depth policy isolation, automated test-enforced.** Native Postgres RLS and ClickHouse row policies are required layers, not optional. CI fails the build if any policy is missing or misconfigured. Cross-workspace data leak is a P0 incident.
- **RPO/RTO:** backup cadence and recovery objectives are **operator-configured** and depend on the chosen `DB_MODE` and infrastructure. The reference Helm/Terraform setups document a sensible default (daily control-plane and ClickHouse backups; PITR available when the operator runs a Postgres that supports it). Cross-region replication is an operator choice. The project recommends **quarterly restore drills** as a baseline.

## 9. High-Level Architecture

ForkReplay is a single self-hostable OSS stack. Everything below runs inside the operator's environment; every external service is either bundled OSS (compose) or pluggable. Detailed sequencing lives in `implementation-plan.md`; this section records the product-level architecture contract.

```
   ┌─────────────────────────────────────────────────────────────────────────┐
   │ Operator's agent application                                            │
   │   ForkReplay Python SDK (decorators + explicit checkpoint)               │
   │   LangGraph / OpenAI Agents SDK / Claude Agent SDK (fork-grade)          │
   │   LlamaIndex / Pydantic AI / smolagents / Strands / AutoGen / CrewAI     │
   │   (inspect-only via OpenInference passive OTel mapping)                  │
   └─────────────────────────────────────┬───────────────────────────────────┘
                                         │ OTLP/HTTP + gRPC, workspace API key
                                         ▼
   ┌─────────────────────────────────────────────────────────────────────────┐
   │ ForkReplay self-hosted deployment (compose / Helm / Terraform)          │
   │                                                                         │
   │   ┌───────────────────────┐      ┌──────────────────────────────────┐   │
   │   │ Next.js Workbench      │◀────▶│ FastAPI services (Python 3.12)   │   │
   │   │ (standalone container) │ REST │  • api (public REST + OTLP recv) │   │
   │   │ App Router + RSC       │ JWT  │  • ingest-worker (stitch/redact) │   │
   │   │ React Flow + ELK       │      │  • replay-worker (dispatch)      │   │
   │   │ FastAPI SSE (Redis)    │◀─SSE─│  • mock-gen-worker               │   │
   │   └───────────────────────┘      │  • export-worker                 │   │
   │           ▲  GoTrue JWT           │  • (optional slim scheduler:     │   │
   │           │                       │     partition/retention cron)    │   │
   │   ┌───────────────┐               └───┬───────────┬───────────┬──────┘   │
   │   │ GoTrue (auth) │                   │           │           │          │
   │   └───────┬───────┘                   ▼           ▼           ▼          │
   │           │              ┌──────────────┐ ┌────────────┐ ┌──────────┐    │
   │           ▼              │ NATS         │ │ Temporal   │ │ Redis    │    │
   │   ┌──────────────┐       │ (ingest queue)│ │ (durable   │ │ (SSE     │    │
   │   │ Postgres      │      │ Redis Streams │ │  branch    │ │  pub/sub)│    │
   │   │ (DB_MODE:     │      │  alt.)        │ │  orchestr.)│ └──────────┘    │
   │   │  supabase /   │      └──────────────┘ └────────────┘                 │
   │   │  custom /     │                                                      │
   │   │  compose)     │      ┌──────────────┐ ┌──────────────────────────┐  │
   │   │ RLS isolation │      │ ClickHouse    │ │ S3-compatible storage    │  │
   │   └──────────────┘       │ (REQUIRED;    │ │ MinIO / AWS S3 / Azure   │  │
   │                          │  spans/steps/ │ │ Blob — content-addressed │  │
   │                          │  messages/    │ │ frames + exports +       │  │
   │                          │  tool calls)  │ │ audit archive            │  │
   │                          └──────────────┘ └──────────────────────────┘  │
   └─────────────────────────────────────────────────────────────────────────┘
                 │                              │
                 ▼ (pluggable LLM routing)      ▼ (optional, operator-run)
   ┌─────────────────────────────────────┐  ┌──────────────────────────────┐
   │ LLM backend (config-selected):      │  │ Observability (optional):    │
   │  • OpenRouter                       │  │  self-hosted OTel collector  │
   │  • direct OpenAI / Anthropic        │  │  + Grafana / Prometheus      │
   │  • Ollama (local; air-gap-friendly) │  └──────────────────────────────┘
   └─────────────────────────────────────┘
   Email (GoTrue confirmations): pluggable SMTP — Resend / SMTP / console.
```

Stack commitment (all self-hostable OSS unless noted):
- **Frontend:** Next.js workbench as a **standalone container**, deployable anywhere (App Router + RSC). Vercel is one optional place an operator could host it, not a requirement.
- **Backend:** Python 3.12, FastAPI, async throughout — `api`, `ingest-worker`, `replay-worker`, `mock-gen-worker`, `export-worker`, plus an optional slim scheduler for partition/retention cron. These are the five Python services minus the (removed) billing-batch-worker.
- **Auth:** **GoTrue** (Supabase Auth OSS), bundled in all DB modes. The app validates GoTrue JWTs everywhere.
- **Control-plane DB:** pluggable **Postgres** via `DB_MODE=supabase | custom | compose`. Native RLS for tenant isolation.
- **Analytics store:** **ClickHouse — required in every mode** (bundled OSS in compose; a required Helm/Terraform dependency). Columnar spans/steps/messages/tool calls. No Postgres substitute.
- **Durable orchestration:** **Temporal** (self-hosted) orchestrates every branch step including the first. Workflow bootstrap is part of the fork-start budget.
- **Streaming transport:** **FastAPI SSE backed by Redis pub/sub**, with `Last-Event-ID` resume.
- **Ingest queue:** **NATS** between the FastAPI OTLP endpoint and the ingest worker (Redis Streams documented as an alternative).
- **Object storage:** **S3-compatible abstraction** — MinIO (compose) / AWS S3 / Azure Blob. Content-addressed, workspace-scoped key prefix.
- **Secrets/BYOK:** operator/workspace keys via env/secret, with an **optional KEK** (age/libsodium) for envelope encryption. No Vault.
- **LLM routing:** pluggable — OpenRouter / direct OpenAI/Anthropic / Ollama, selected by config.
- **Email:** pluggable SMTP — Resend / SMTP / console — needed for GoTrue confirmations.
- **Observability:** optional self-hosted OTel collector + Grafana/Prometheus. Grafana Cloud is one optional managed sink, not required.
- **CI/CD:** GitHub Actions builds and publishes the container images and Helm chart; operators deploy with their own pipeline.
- **No billing:** there is no Stripe, no credit/meter ledger, and no billing-batch-worker. Operational quotas (`WorkspaceLimits`) are the only resource controls.
- **Post-V1 agent-facing streaming/control:** AG-UI evaluation and integration.

**Optional third-party services an operator may configure** (none are required; all have OSS/self-hosted alternatives): OpenRouter or a direct provider for LLM routing (or fully local Ollama); Resend or any SMTP server for email; managed Supabase (when `DB_MODE=supabase`); managed S3/Azure Blob for object storage; Grafana Cloud for observability; a managed Kubernetes/host for the deployment itself. Because the operator runs everything, there is no ForkReplay sub-processor list — data goes only where the operator points it.

## 9.A License & Deployment Options

**License.** ForkReplay is released under **Apache-2.0**. Apache-2.0 is preferred over MIT specifically for its explicit patent grant, which matters for a product that bundles and integrates several upstream OSS projects and that operators will run in commercial environments. The entire product — services, workbench, SDK, contracts, deployment artifacts — is one Apache-2.0 codebase.

**Deployment options.**
- **docker-compose (quickstart):** a single `docker compose up` brings up the full topology with bundled OSS for every dependency (Postgres, ClickHouse, Temporal, NATS, Redis, MinIO, GoTrue) plus the FastAPI services and the Next.js workbench container. This is the recommended path for evaluation and single-node self-host, and it is the default for the single-tenant quickstart.
- **Helm (Kubernetes):** charts for cluster operators. ClickHouse, Temporal, NATS, and Redis are required chart dependencies (or pointed at managed equivalents); the control-plane Postgres is selected by `DB_MODE`.
- **Terraform (AWS + Azure):** reference modules that provision the same topology on each cloud's managed primitives where available (managed Postgres, S3/Azure Blob object storage, a ClickHouse deployment).

**Deployment modes (`DB_MODE`).** The control-plane Postgres is pluggable: `supabase` (managed or self-hosted Supabase), `custom` (bring-your-own Postgres with bundled GoTrue), or `compose` (fully bundled Postgres container). In every mode GoTrue is the auth provider and **ClickHouse is required** — the analytics plane is not pluggable.

**Single-tenant vs. multi-tenant.** The multi-tenant core (workspaces + RLS) is retained. Operators who only need one team run the documented single-tenant (default-workspace) quickstart, which is the same code with one workspace pre-created.

## 10. V1 Scope vs. Out of Scope

**V1 ships:**
- OTLP ingest (passive track) for valid traces; GenAI-aware views require supported convention/framework mappings.
- Adapter SDK (Python) for active-track capture, plus `forkreplay-auto` one-line bootstrap.
- **Fork-grade framework integrations: LangGraph + OpenAI Agents SDK + Claude Agent SDK** (alongside the framework-neutral Python adapter).
- **Inspect-only with OpenInference passive OTel mapping: LlamaIndex, Pydantic AI, smolagents, Strands Agents, AutoGen, CrewAI** (six frameworks).
- Trace browse + step inspector + DAG visualization (≤2k step-DAG nodes interactive).
- Fork engine with all intervention types in 7.4, guided intervention templates, checkpoint fidelity warnings, and adapter-supplied capability contracts.
- Tool execution policies: mock, ai_mock, block.
- Branch comparison as central UX, with persistent branch trees, forks of forks, effect attribution, and repeated-trial summaries.
- **Three hard-coded exporters: generic trajectory JSONL, generic JSON test case, Promptfoo.**
- Trace-to-test-case conversion with webhook/SDK hooks.
- **Apache-2.0 self-hostable distribution** with docker-compose / Helm / Terraform (AWS+Azure) deployment options.
- **Pluggable control-plane DB** (`DB_MODE=supabase | custom | compose`) with **required ClickHouse** analytics store in every mode.
- Multi-tenant workspace isolation (defense-in-depth, native RLS + ClickHouse row policies), plus a documented single-tenant (default-workspace) quickstart.
- **GoTrue auth** bundled in all DB modes (email/password + federated OAuth/OIDC); app validates GoTrue JWTs everywhere.
- **Pluggable LLM routing** (OpenRouter / direct OpenAI/Anthropic / Ollama) and **pluggable SMTP email** (Resend / SMTP / console).
- Operator quotas (`WorkspaceLimits`: concurrency / depth / wall-clock / token volume / AI-mock caps / retention) with informational pre-fork cost estimates. No billing, no credits, no meters.
- Operator/workspace LLM keys via env/secret with an optional KEK (age/libsodium) for envelope encryption. No Vault.
- V1 admin panel with 5 surfaces: per-workspace limits, auth-policy, member management, LLM-routing/key config, retention/redaction.

**V1 does NOT ship:**
- A hosted/managed SaaS run by the ForkReplay team (self-host is the product; a managed offering is out of scope).
- Built-in billing, metering, payments, or a credit/usage ledger (operators bring their own; removed, not deferred).
- Live tool execution (HTTP / executable code) — V1.1 / V2.
- TypeScript adapter SDK — V2+.
- Schema configuration engine — V1.1 (V1 ships 3 hard-coded exporters on a thin internal mapping interface).
- The 8 additional exporter mappings (OpenAI SFT, TRL SFT, OpenAI preference, TRL DPO, HuggingFace package, Inspect, Braintrust, LangSmith) — V1.1 behind the `exporters.v1_1` feature flag, no preview surface in V1.
- A Postgres-only mode that drops ClickHouse — ClickHouse is required, full stop.
- Anomaly detection on token consumption — V1.1.
- ClickHouse full-text/vector message search projection — V1.1.
- Cross-trace step continuation in the same session — V1.1+.
- `llm_synthesize` execution-time mock mode — V1.1.
- Enterprise SSO/provisioning (SAML/SCIM) — V1.1+.
- Built-in evaluators or judges.
- Mid-stream forks.
- Browser-agent screen/action replay: browser screen recording, DOM/action timelines, and user-interaction playback synced to spans. Agent interaction traces remain in scope; browser session replay does not.
- Automatic intervention suggestions ("AI suggests editing this prompt").
- Analytics dashboards beyond per-trace cost/latency.

## 11. Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Laminar adds branch trees + tool execution policies before we ship | Medium | High | Move fast; ship branch trees and AI-generated mocks as headline features. Customer interviews to validate that branch trees are felt-needed, not nice-to-have. |
| Langfuse upgrades playground to multi-step trajectory fork | Medium | Medium | Maintain depth advantage in tool execution policies and intervention surface. They have mindshare; we have depth. |
| LangGraph Studio satisfies LangGraph-native customers before we reach them | High | Medium | Do not compete on LangGraph runtime semantics alone. Lead with framework-agnostic production traces, explicit tool side-effect controls, branch comparison, and export from forked branches. |
| OTel GenAI conventions change before V1 ships | High | Medium | Build adapter SDK with our own schema (superset of GenAI); treat OTel conformance as ingestion path, not internal model. |
| OTel-compatible traces lack prompt/tool content needed for useful replay because content capture is off by default | High | High | Make passive/active capability differences explicit. Require opt-in content capture and adapter checkpoints for fork-grade traces. |
| AI-generated mocks don't work well enough in practice | Medium | High | Validate with prototype on real customer traces before committing. Static-mock fallback always available. Document explicitly that ai_mock is a starting point users will refine. |
| A user runs a runaway fork (recursion, infinite loop) and burns the operator's LLM budget | Medium | High | Operator quotas: hard per-fork token/step caps; pre-fork informational cost preview; stop at deterministic boundaries before the next model/tool call; auto-pause on quota exhaustion; per-branch wall-clock timeout. Anomaly detection in V1.1 closes the remaining gap. |
| A workspace becomes "unlimited execution on the operator's infrastructure" | Medium | Medium | Apply `WorkspaceLimits` everywhere: runs, concurrency, wall-clock time, branch depth, token volume, tool invocations, stored artifacts, and AI-mock usage. The operator can run fully-local Ollama to remove external spend entirely. |
| LLM cost surprises the operator | Medium | Medium | Pre-fork informational estimates, rolling-30-day token tracking, alert/cutoff thresholds, and quota auto-pause surface usage before the provider invoice arrives. The provider invoice (operator's own account) is authoritative. |
| Multi-tenant data leak | Low | Critical | Workspace scoping at every layer; native RLS + ClickHouse row policies required; CI-enforced isolation conformance test; treat any cross-workspace read as P0. |
| LangGraph runtime time-travel exposed as Studio feature for any framework | Low | High | Watch closely. If they generalize beyond LangGraph, our framework-agnostic pitch weakens. |
| Capture data exceeds storage budget | High | Medium | Content-addressed dedup; configurable per-workspace retention; tiered storage (hot ClickHouse, cold object store). |
| Multi-agent traces from emerging frameworks don't fit our DAG model | Medium | Medium | Pluggable stitcher architecture; document the adapter API. |
| "Branch tree" doesn't resonate with users — they want simple rerun and comparison | Medium | Medium | Ship branch tree but expose simple "rerun" and side-by-side comparison first; treat forks-of-forks as a validated power-user workflow, not the only headline. |
| DPO/post-training export is less urgent than trace-to-test workflows | Medium | Medium | Keep export architecture but message "debug fix becomes eval/test case" first. Track actual weekly fine-tuning exports separately from generic dataset exports. |
| Low-star OSS tools converge on the same messaging before launch | Medium | Low | Watch Rewind, Tracewire, TraceOps, and similar projects. Use hands-on validation to distinguish real capability from positioning. |
| Self-host operability burden (Temporal/NATS/Redis/ClickHouse) deters small operators | Medium | Medium | docker-compose quickstart bundles every dependency as OSS with sane defaults; single-tenant default-workspace path needs no extra config; Helm/Terraform references for larger operators. |
| Operators are surprised that ClickHouse is mandatory | Medium | Medium | Document the ClickHouse requirement prominently (Non-Goals, deployment docs, quickstart); bundle it in compose so the requirement is invisible in the happy path. |
| Temporal hits an unanticipated limit (history size, task-queue throughput, retry behavior) | Medium | Medium | Workflow returns only pointers; object storage holds frames; keep workflow history compact; canaries on history size and activity attempts. |
| Temporal-orchestrates-every-step cold-start adds latency on top of fork-start budget | Medium | Medium | Pre-warm worker pool; Phase-0 spike validates the 3s p95 launch goal; 4s slip accepted; >5s comes back for discussion. |
| Cross-provider model swap loses `reasoning_details` | Medium | Medium | V1: drop with warning at envelope construction time; manifest records the diff. V1.1+: optional lossy re-translation. |
| Claude Agent SDK hook API churn during V1 development | Medium | Medium | Pin to verified-tested minor version; weekly CI run against latest `claude-agent-sdk`; abstract instrumentor behind an internal interface to enable swap when Anthropic ships native OTel. |
| Availability/backup posture varies wildly across operators | Medium | Medium | Project responsibility ends at shipping health endpoints, the optional OTel/Grafana stack, and documented backup/restore defaults. Availability and RPO/RTO are operator-owned; the docs recommend daily backups + quarterly restore drills as a baseline. |

## 12. Success Metrics

Because ForkReplay is self-hosted OSS, success is measured by adoption and engagement of the project, not by revenue. Hard install counts are not directly observable; metrics rely on opt-in anonymous telemetry, GitHub signals, and design-partner instances.

**Leading (V1 launch + 90 days):**
- ≥ 50 active self-host instances reporting via opt-in telemetry (or ≥ 50 design-partner / community deployments confirmed).
- ≥ 200 forks executed per active instance per week.
- p50 time-from-trace-open to fork-execution < 5 minutes.
- ≥ 60% of completed forks are compared against the original or another branch.
- ≥ 30% of active instances run repeated trials for at least one intervention.
- ≥ 15% of forks are forks-of-forks (validates recursive branch tree as a real-use UX, not just marketing).
- LLM-routing-backend mix tracked (OpenRouter vs. direct provider vs. local Ollama) for directional signal on the air-gapped/local use case.

**Lagging (V1 launch + 6 months):**
- ≥ 5 case studies of agent failures debugged via fork that operators confirm could not have been debugged otherwise in reasonable time.
- ≥ 3 operators exporting datasets weekly for eval/test or training workflows.
- ≥ 1 operator exporting forked trajectories into an actual fine-tuning or preference-optimization workflow.
- ≥ 5 operators with trace-to-test workflows running in CI.
- Healthy OSS project signals: external contributors, GitHub stars/forks trend, community issues/PRs, and at least one third-party deployment write-up.
- Zero confirmed P0 multi-tenant data leak vulnerabilities (in the shipped code, not any single instance the project does not operate).

## 13. Resolved Owner Decisions

These decisions were clarified after the May 6 research pass and re-confirmed during the May 12 planning rounds 1 and 2:

1. **Primary V1 wedge:** lead with "debug failed traces into regression tests." Branch-tree exploration remains a core product mechanic, not the first external message.
2. **Dataset priority:** post-training/DPO export is secondary in V1. Trace-to-test and eval-case export are the primary downstream workflows.
3. **Browser-agent scope:** browser screen recording, DOM/action replay, and user-interaction playback are out of scope. ForkReplay focuses on the agent interaction trajectory.
4. **Repeated trials:** repeated-trial execution and aggregate comparison are V1 requirements.
5. **Export dialects:** V1 ships **3 hard-coded exporters** (generic trajectory JSONL, generic JSON test case, Promptfoo). The schema configuration engine and the additional 8 dialects ship in V1.1 (no preview surface in V1).
6. **License & distribution:** ForkReplay is **Apache-2.0** OSS, self-hostable as a single codebase. No managed-SaaS layer. (Supersedes the prior SaaS framing.)
7. **No built-in billing:** there are **no replay credits, no usage meters, no payments, and no credit/meter object model.** Resource use is bounded by operator quotas (`WorkspaceLimits`) only. A published model rate card survives **only** as an informational cost *estimate*, never a billing ledger. Operators bring their own billing if they want it. (Supersedes the prior "replay credits, 1 credit = $0.001" decision.)
8. **Launch auth posture:** V1 bundles **GoTrue** (Supabase Auth OSS) in **all** DB modes, with email/password registration and federated OAuth/OIDC providers. The app validates GoTrue JWTs everywhere; tenant isolation is native Postgres RLS. Enterprise SSO/provisioning with SAML/SCIM is V1.1+.
9. **Self-host stack:** Next.js workbench (standalone container) + FastAPI services (`api` with the OTLP receive endpoint, `ingest-worker`, `replay-worker`, `mock-gen-worker`, `export-worker`, optional slim scheduler) + GoTrue + pluggable Postgres (`DB_MODE`) + **required ClickHouse** + **Temporal** (durable orchestration) + **NATS** (ingest queue; Redis Streams alternative) + **Redis** (SSE pub/sub) + **S3-compatible object storage** (MinIO / AWS S3 / Azure Blob). Vercel / Railway / Cloudflare / Grafana Cloud are optional managed choices, not requirements.
10. **LLM routing (pluggable):** the model-provider interface supports **OpenRouter / direct OpenAI/Anthropic / Ollama**, selected by config per operator and overridable per workspace. Keys are operator/workspace env/secret values with an optional KEK (age/libsodium); no Vault. The provider invoice (operator's own account) is authoritative; ForkReplay never settles spend.
11. **SDK ergonomics:** V1 uses an **explicit-capture core API** (`checkpoint()` and supporting primitives) with **decorator ergonomics layered on top where the boundary maps cleanly to a Python function call**. Decorators (`@capture`, `@step`, `@tool`, `@model_call`) are sugar over the core; explicit calls remain available for non-function-shaped boundaries. `forkreplay-auto` (one-line bootstrap, `import forkreplay.auto`) is the canonical V1 onboarding path. **Install posture:** `forkreplay-sdk[auto]` pulls in the auto-detection module only; users install per-framework extras (`[langgraph]`, `[claude]`, `[openai-agents]`) explicitly. **Env-var contract:** `FORKREPLAY_AUTO_INSTRUMENT=1` (opt-in `.pth` bootstrap), `FORKREPLAY_AUTO_SAMPLE=0.1` (probabilistic SDK-side drop), `FORKREPLAY_AUTO_DISABLE=1` (kill-switch), `FORKREPLAY_VERBOSE=1` (INFO-level logs; silent default).
12. **UI/streaming posture:** V1 ships the Next.js workbench container with **FastAPI SSE backed by Redis pub/sub** (Last-Event-ID resume) backing branch progress. AG-UI is a post-V1 addition for agent-driven branching/debugging interfaces.
13. **Cancellation guarantee.** In-flight model calls aborted within 3s p95 of user-initiated cancel via AbortSignal propagation to the routing backend (Temporal activity cancellation). No billing involved (no billing exists).
14. **Durable orchestration coverage.** **Temporal** orchestrates every branch step including the first (no first-call bypass). Workflow bootstrap is part of the fork-start budget.

### 13.A V1 deliberately-constrained scope

The following constraints in V1 are intentional design choices, not oversights. Surfaced to contributors, operators, and prospects upfront.

- **No built-in billing/metering.** Self-host ships no payments, invoicing, usage meters, or credit ledger. Operators bring their own billing if they want it. Only operational quotas ship. (Removed, not deferred.)
- **ClickHouse is a required dependency.** The columnar analytics store is mandatory in every deployment mode (bundled OSS in compose; required in Helm/Terraform). "Pluggable Postgres" applies to the control plane only — there is no Postgres-only mode.
- **Availability, backups, and RPO/RTO are operator-owned.** The project ships health endpoints, an optional self-hosted OTel collector + Grafana/Prometheus stack, and documented backup/restore defaults (daily backups; quarterly restore drills recommended). It makes no SLA, because it does not run the service.
- **No project-run status page or pen-test attestation.** Operational status is surfaced via the `system_banners` mechanism (FastAPI/Redis-backed banner channel) the operator controls. The shipped attack surface is small (no live tool execution, no public mutation API, keys siloed and optionally KEK-wrapped); defense-in-depth controls (RLS, ClickHouse row policies, CI-enforced isolation conformance test) carry the security load. Operators may commission their own pen-test for their deployment.
- **Single self-hostable codebase, no managed SaaS.** Apache-2.0. A hosted offering operated by the ForkReplay team is out of scope for V1.
- **Privacy posture is operator-chosen.** The operator picks the routing backend (including fully local Ollama, which keeps data on-prem) and, on multi-endpoint backends, the per-workspace `data_collection`/`zdr` posture.
- **Python-only SDK.** TypeScript SDK is V2+, not V1.1.
- **Admin panel scope locked at 5 surfaces:** per-workspace limit overrides, auth-policy, member management, LLM-routing/key config, retention/redaction. Anything else is V1.1+.

Implementation planning should use `implementation-readiness-spec.md` as the detailed product contract. Its Section 11 records the resolved planning decisions that determine initial sequencing.

## 14. Open Questions for V1.1+

- Schema configuration engine vs. additional pre-built mappings — what's the right shape for V1.1 mapping authorship UX?
- Live tool execution model: how do we manage credentials safely, and what's the per-tool side-effect tagging UX?
- `llm_synthesize` runtime mock execution mode (deferred from V1).
- Cross-provider lossy re-translation of `reasoning_details` (deferred from V1).
- `redacted_thinking` export opt-in for customers with downstream signature-verifying consumers (revisit at V1.1 launch).
- Inline AI assistance in the intervention editor (suggest prompt edits based on failure mode) — useful, or feature-creep?
- Time-travel for state outside the trace (DB snapshots, vector store snapshots at capture time) — necessary for "true" fidelity, or scope-creep?
- Native eval harness integration — first-party scorer DSL, or stay agnostic?
- Cross-trace step continuation (fork from the latest state of a session, not a specific trace).
- ClickHouse message search projection + vector similarity over messages (V1.1).
- TypeScript adapter SDK (V2+).
- Optional managed/hosted offering on top of the OSS core — is there demand, and on what terms?
- Optional billing/metering add-on (or integration guide) for operators who want to charge their own users — first-party, or leave entirely to the operator?
- An OSS-only ClickHouse operability story (sizing, retention, backups) hardened enough that small operators never have to think about it.

---

*This is a working PRD. The risks section is the most volatile — Laminar and Langfuse are both moving fast, and the V1 scope should be revisited monthly against their changelogs.*

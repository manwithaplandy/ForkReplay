# ForkReplay — Abstraction-Layer Interfaces

The interfaces that keep ForkReplay's backends pluggable. Each one is a stable seam the rest
of the codebase programs against; the concrete backend behind it is chosen at runtime by an
environment variable / config value, never hard-coded.

> **Phase-6 design outline only.** Per [implementation-plan.md](../../../implementation-plan.md)
> §9.1 and §11, the productionized implementations of these interfaces are authored in a
> future implementation phase. This page sketches method signatures, responsibilities, the
> backends each interface abstracts, and the selection mechanism — it authors no production
> code. The companion [deploy-outline.md](./deploy-outline.md) covers the `deploy/` tree and
> variable surfaces.

> **Principle: no single vendor is hard-coded.** Every interface below has at least two
> concrete backends, and the choice is made by configuration. Application code depends only on
> the interface, so swapping a backend (MinIO → AWS S3, NATS → Redis Streams, OpenRouter →
> Ollama) is a config change, not a code change. Pseudocode is Python-ish for illustration;
> the SDK and services are Python.

---

## Selection mechanism (common pattern)

Each interface is constructed by a small **factory** that reads one environment variable and
returns the matching implementation. The variable is the single point of selection; nothing
else in the codebase knows which backend is live.

```python
def build_object_store(env) -> ObjectStore:
    # S3-compatible everywhere; the endpoint/credentials select the concrete target.
    return S3ObjectStore(
        endpoint=env["S3_ENDPOINT"],          # MinIO / AWS S3 / Azure-Blob-via-gateway
        region=env.get("S3_REGION", "us-east-1"),
        access_key=env["S3_ACCESS_KEY_ID"],
        secret_key=env["S3_SECRET_ACCESS_KEY"],
    )

def build_queue_consumer(env) -> QueueConsumer:
    backend = env.get("QUEUE_BACKEND", "nats")  # selection mechanism
    if backend == "nats":
        return NatsQueueConsumer(url=env["NATS_URL"], creds=env.get("NATS_CREDS"))
    if backend == "redis":
        return RedisStreamsConsumer(url=env["REDIS_URL"])
    raise ConfigError(f"unknown QUEUE_BACKEND={backend!r}")
```

The selection variable for each interface is named in its section below. The full variable
reference is [configuration.md](../../deployment/configuration.md); names match
[`.env.example`](../../../.env.example). All example values are `${PLACEHOLDER}` markers.

---

## `AuthProvider` — GoTrue everywhere; JWT validation

**Backends abstracted:** GoTrue in all three `DB_MODE` values — a GoTrue container in
`compose`/`custom`, the Supabase-managed Auth service in `supabase`. The validation surface is
identical regardless of mode, so web, API, ingest, and workers share one client.

**Selection mechanism:** GoTrue is the auth backend in *every* mode; it is configured (not
chosen between vendors) via `GOTRUE_*` — `GOTRUE_JWT_SECRET` (signing/JWKS material),
`GOTRUE_API_EXTERNAL_URL` (issuer), `GOTRUE_JWT_AUD` (audience). The interface stays stable so
a future alternative IdP could be slotted in without touching callers.

**Method sketch:**

```python
class AuthProvider(Protocol):
    def validate_jwt(self, token: str) -> Claims: ...
        # verify signature/issuer/audience/expiry against GOTRUE_JWT_SECRET; raise on failure
    def get_claims(self, token: str) -> Claims: ...     # workspace_id, user_id, role
    def authenticate(self, request) -> Principal: ...   # FastAPI dependency entry point
```

Responsibility: uniform JWT validation across web, API, ingest, and workers; it never issues
tokens (GoTrue does) — it only verifies them and surfaces the workspace/tenant claims used for
isolation.

---

## `ObjectStore` — S3-compatible (MinIO / S3 / Azure Blob)

**Backends abstracted:** one **S3-compatible** interface over **MinIO** (compose), **AWS S3**
(Terraform AWS), and **Azure Blob** fronted by an S3-compatible gateway/config (Terraform
Azure). Stores frames, export bundles, and the audit cold archive under workspace-scoped key
prefixes.

**Selection mechanism:** `S3_ENDPOINT` selects the concrete target; the rest of the `S3_*`
surface (`S3_REGION`, `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY`, `S3_BUCKET_FRAMES`,
`S3_BUCKET_BLOBS`) configures it. No provider SDK is hard-coded — everything speaks S3.

**Method sketch:**

```python
class ObjectStore(Protocol):
    def put_object(self, bucket: str, key: str, body: bytes, *, content_type: str) -> None: ...
    def get_object(self, bucket: str, key: str) -> bytes: ...
    def presign_get(self, bucket: str, key: str, ttl_s: int) -> str: ...   # signed download URL
    def list_prefix(self, bucket: str, prefix: str) -> Iterator[ObjectMeta]: ...
    def set_retention(self, bucket: str, key: str, until: datetime) -> None: ...  # WORM/object-lock
```

Responsibility: content-addressed `<workspace_id>/...` key prefixes for tenant isolation, and
object-lock / WORM retention on the `committed=true/` prefix for the audit archive.

---

## `QueueConsumer` — NATS or Redis Streams

**Backends abstracted:** **NATS** (primary) and **Redis Streams** (lighter alternative)
behind one interface. Carries raw OTLP span batches from `api` to `ingest`.

**Selection mechanism:** `QUEUE_BACKEND=nats|redis`. NATS reads `NATS_URL` / `NATS_CREDS`; the
Redis Streams path reads `REDIS_URL`.

**Method sketch:**

```python
class QueueConsumer(Protocol):
    def publish(self, subject: str, payload: bytes) -> None: ...
    def consume(self, subject: str, group: str) -> Iterator[Message]: ...  # durable consumer group
    def ack(self, message: Message) -> None: ...
    def nack(self, message: Message, *, requeue: bool = True) -> None: ...
```

Responsibility: at-least-once delivery with consumer groups so `ingest` can scale
horizontally; ack/nack semantics map onto NATS JetStream and Redis Streams consumer groups
alike.

---

## Temporal workers — worker-pool attachment / config

**Backends abstracted:** Temporal is the single durable-orchestration engine (self-hosted in
compose/Helm, or an external cluster on Terraform). The abstraction is the **worker-pool
attachment** — how each service process registers its workflows/activities onto a task queue.

**Selection mechanism:** `TEMPORAL_*` — `TEMPORAL_HOST` (frontend), `TEMPORAL_NAMESPACE`,
optional `TEMPORAL_TLS_CERT` / `TEMPORAL_TLS_KEY` for mTLS. Each worker pool binds to a named
**task queue** (`replay-worker`, `mock-gen-worker`, `export-worker`), so pools scale
independently.

**Method sketch:**

```python
def build_worker(env, task_queue: str, *, workflows, activities) -> Worker:
    client = Client.connect(
        env["TEMPORAL_HOST"],
        namespace=env.get("TEMPORAL_NAMESPACE", "default"),
        tls=load_tls(env),                       # only if TEMPORAL_TLS_* set
    )
    return Worker(client, task_queue=task_queue, workflows=workflows, activities=activities)

# replay-worker / mock-gen-worker / export-worker each call build_worker() with their queue
```

Responsibility: register workflows/activities, attach to the right task queue, and apply the
retry/timeout policies bounded by `WorkspaceLimits` (detailed in
[../orchestration/temporal-workflows.md](../orchestration/temporal-workflows.md)).

---

## Redis SSE relay — FastAPI SSE + Redis pub/sub (`Last-Event-ID` resume)

**Backends abstracted:** the live-progress fan-out is **FastAPI SSE backed by Redis pub/sub**.
This is the self-hosted OSS replacement for the deprecated Cloudflare Workers SSE relay
(retained only as a transition reference, slated for removal).

**Selection mechanism:** Redis is configured via `REDIS_URL`; the same Redis also serves the
alternative ingest queue when `QUEUE_BACKEND=redis`. The relay is part of `services/api`, so
there is no separate vendor to pick — pointing `REDIS_URL` at managed or in-cluster Redis is
the only choice to make.

**Method sketch:**

```python
class SseRelay:
    def publish(self, channel: str, event: ProgressEvent) -> None: ...   # workspace-scoped channel
    async def stream(self, channel: str, last_event_id: str | None) -> AsyncIterator[bytes]:
        # on connect: if Last-Event-ID present, replay buffered events after it, then tail
        # subscribe to the Redis pub/sub channel and yield SSE-framed bytes to the client
        ...
```

Responsibility: workspace-scoped channels for tenant isolation, `Last-Event-ID`-based resume
on reconnect, and connection-lifecycle management (heartbeats, unbuffered responses).

---

## Pluggable LLM — OpenRouter / direct provider / Ollama

**Backends abstracted:** an `LLMProvider` interface over **OpenRouter**, direct providers
(OpenAI / Anthropic), and **Ollama** (keyless, local). Used by `replay-worker` for live branch
steps and by `mock-gen-worker` for AI-mock generation.

**Selection mechanism:** `LLM_PROVIDER=openrouter|openai|anthropic|ollama`, with `LLM_API_BASE`
(override base URL, e.g. a local Ollama endpoint) and `LLM_API_KEY` (operator default;
omitted for keyless local Ollama). Workspace-scoped BYOK keys layer on top.

**Method sketch:**

```python
class LLMProvider(Protocol):
    def complete(self, request: ChatRequest) -> ChatResponse: ...   # one model call
    def chat(self, messages, *, model, tools=None) -> ChatResponse: ...
    def stream(self, request: ChatRequest) -> Iterator[ChatChunk]: ...

def build_llm_provider(env) -> LLMProvider:
    provider = env.get("LLM_PROVIDER", "openrouter")   # selection mechanism
    return PROVIDERS[provider](base=env.get("LLM_API_BASE"), key=env.get("LLM_API_KEY"))
```

Responsibility: one call surface across providers so branch execution is provider-agnostic; no
single LLM vendor is hard-coded.

---

## Pluggable email — SMTP / Resend / console

**Backends abstracted:** an `EmailSender` interface over **SMTP**, **Resend**, and **console**
(prints links to logs — fine for local dev). Required for GoTrue confirmation emails.

**Selection mechanism:** `EMAIL_BACKEND=smtp|resend|console`. SMTP reads `SMTP_HOST` /
`SMTP_PORT` / `SMTP_USERNAME` / `SMTP_PASSWORD`; all backends share `EMAIL_FROM`.

**Method sketch:**

```python
class EmailSender(Protocol):
    def send_email(self, to: str, subject: str, body_html: str, *, from_addr: str) -> None: ...

def build_email_sender(env) -> EmailSender:
    backend = env.get("EMAIL_BACKEND", "console")   # selection mechanism
    return {"smtp": SmtpSender, "resend": ResendSender, "console": ConsoleSender}[backend](env)
```

Responsibility: deliver transactional email through the operator's chosen channel; `console`
keeps local dev dependency-free.

---

## Summary — interface ⇄ selection variable

| Interface | Backends | Selected / configured by |
|-----------|----------|---------------------------|
| `AuthProvider` | GoTrue (all `DB_MODE` values) | `GOTRUE_*` (GoTrue everywhere) |
| `ObjectStore` | MinIO / AWS S3 / Azure Blob | `S3_ENDPOINT` + `S3_*` |
| `QueueConsumer` | NATS / Redis Streams | `QUEUE_BACKEND` |
| Temporal workers | Temporal (task-queue pools) | `TEMPORAL_*` |
| Redis SSE relay | FastAPI SSE + Redis pub/sub | `REDIS_URL` |
| LLM provider | OpenRouter / OpenAI / Anthropic / Ollama | `LLM_PROVIDER` |
| Email sender | SMTP / Resend / console | `EMAIL_BACKEND` |

In every row the env var / config value selects the backend; application code depends only on
the interface, so no single vendor is hard-coded.

See [deploy-outline.md](./deploy-outline.md) for the `deploy/` tree and the full variable
surfaces, and [docs/deployment/configuration.md](../../deployment/configuration.md) for the
authoritative variable reference.

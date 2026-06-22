# workers/otlp-gateway — DEPRECATED (slated for removal)

> **Deprecated in the OSS pivot.** OTLP ingress is replaced by a **FastAPI OTLP endpoint**
> in `services/api` / `services/ingest`, which enqueues onto **NATS** (or Redis Streams).
> This Cloudflare Worker is retained, secret-scrubbed, only as a transition reference;
> deletion is an implementation-phase task. Do not build new functionality here.

Original role (for reference): Cloudflare Worker (TypeScript) that terminated OTLP/HTTP
requests from the `forkreplay-sdk` and enqueued raw batches. `account_id` and queue IDs must
never be hard-coded in `wrangler.toml`; supply them via the `CLOUDFLARE_ACCOUNT_ID` env var.

See ../../AGENTS.md or root AGENTS.md for project-wide context.

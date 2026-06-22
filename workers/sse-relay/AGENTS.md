# workers/sse-relay — DEPRECATED (slated for removal)

> **Deprecated in the OSS pivot.** Live streaming is replaced by a **FastAPI SSE endpoint
> backed by Redis pub/sub** (branch progress + the `system_banners` channel) in
> `services/api`. This Cloudflare Worker + Durable Object pair is retained, secret-scrubbed,
> only as a transition reference; deletion is an implementation-phase task. Do not build new
> functionality here.

Original role (for reference): fanned out branch-progress events and the `system_banners`
channel to subscribed browsers; the Durable Object held the per-branch/topic subscriber
list. `account_id` must never be hard-coded in `wrangler.toml`.

See ../../AGENTS.md or root AGENTS.md for project-wide context.

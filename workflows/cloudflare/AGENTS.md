# workflows/cloudflare — DEPRECATED (slated for removal)

> **Deprecated in the OSS pivot.** Durable orchestration is replaced by **Temporal**
> (self-hosted), with `services/replay-worker` running the Temporal workers/activities. This
> Cloudflare Workflows project is retained, secret-scrubbed, only as a transition reference;
> deletion is an implementation-phase task. Do not build new functionality here.

Original role (for reference): Cloudflare Workflows (TypeScript) hosting the durable
orchestration steps that drove a branch replay across replay-worker, mock-gen-worker, and
export-worker.

See ../../AGENTS.md or root AGENTS.md for project-wide context.

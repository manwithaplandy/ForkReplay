# services/billing-batch-worker — REMOVED FROM CORE (deprecated)

> **This service is removed from the ForkReplay core in the OSS pivot.** Billing and
> metering (Stripe, replay credits, credit packs, refund batches, MRR rollup) are no longer
> part of the self-hostable product. Only operational `WorkspaceLimits` (concurrency, depth,
> wall-clock, retention, token volume) remain, and those are enforced in `services/api` /
> `services/replay-worker`.
>
> Do **not** build new functionality here. The directory is retained, secret-scrubbed, only
> as a transition reference; its deletion is an implementation-phase task. Low-frequency
> platform crons (partition/retention) move to the optional `services/scheduler`.

See ../../AGENTS.md or root AGENTS.md for project-wide context.

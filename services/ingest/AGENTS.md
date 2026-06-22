# services/ingest — OTel → frame projection

Consumes the **NATS** ingest queue (populated by the FastAPI OTLP endpoint in
`services/api`; `QUEUE_BACKEND=nats`, with Redis Streams as the documented alternative).
Each batch is parsed as OTLP/protobuf spans, projected into the ForkReplay frame model, and
written to ClickHouse (the required analytical store) + Postgres (control-plane index rows).
Large blobs land in the **S3-compatible object store** (MinIO / AWS S3 / Azure Blob).

- Runtime: container (Python 3.12)
- Inputs: NATS subject `forkreplay.otlp.ingest` (or Redis Streams alt)
- Outputs: ClickHouse frames tables, Postgres frame index, S3 blob objects

See ../../AGENTS.md or root AGENTS.md for project-wide context.

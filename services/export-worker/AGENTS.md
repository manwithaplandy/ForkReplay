# services/export-worker — test-case export

Materializes captured frames as promptfoo test cases and pytest fixtures so users can turn
a real trace (or a forked replay) into a deterministic regression test. Output artifacts are
uploaded to the **S3-compatible object store** (MinIO / AWS S3 / Azure Blob) and surfaced
through the API as signed-URL downloads.

- Runtime: container (Python 3.12)
- Output formats: promptfoo YAML, pytest fixture modules, generic trajectory JSONL
- Storage: S3-compatible (`S3_BUCKET_BLOBS`)

See ../../AGENTS.md or root AGENTS.md for project-wide context.

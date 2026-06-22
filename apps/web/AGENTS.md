# apps/web — ForkReplay workbench

Next.js 16 App Router application packaged as a **standalone container** (deployable
anywhere — compose, Kubernetes, or any container host; no Vercel dependency). This is the
workbench UI where users browse captured agent traces, fork them, and inspect replay
results. Authenticates against **GoTrue** and subscribes to branch progress via the
**FastAPI SSE endpoint** (Redis-backed) in `services/api`.

- Runtime: Next.js standalone container (Node 20)
- Stack: Next.js 16, React 19, TypeScript 5 (strict)
- Auth: GoTrue (`NEXT_PUBLIC_GOTRUE_URL`); API base `NEXT_PUBLIC_API_BASE_URL`

See ../AGENTS.md or root AGENTS.md for project-wide context.

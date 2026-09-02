# Loose Thread

Loose Thread is a personal cognitive continuity system: capture thoughts with almost no friction, organize them invisibly, and resurface only a few useful things when the user has capacity to engage.

## Thursday demo objective
The current sprint is a production-shaped end-to-end vertical slice centered on AI agents, durable orchestration, backend reliability, deterministic retrieval, and a thin Expo client.

Start here:
- [`AGENTS.md`](./AGENTS.md) — instructions for Codex.
- [`docs/exec-plans/active/THURSDAY-DEMO.md`](./docs/exec-plans/active/THURSDAY-DEMO.md) — exact sprint plan and done criteria.
- [`docs/product-specs/PRD-v1.md`](./docs/product-specs/PRD-v1.md) — build-ready PRD.
- [`ARCHITECTURE.md`](./ARCHITECTURE.md) — implementation boundaries.
- [`THURSDAY_STATUS.md`](./THURSDAY_STATUS.md) — live progress ledger.

## Repository layout
```text
apps/mobile/                  Expo application
services/api/                 FastAPI + Agents SDK + worker + retrieval
supabase/migrations/          schema, RLS, pgvector
scripts/                      smoke/developer scripts
docs/product-specs/           product source of truth
docs/design-docs/             architecture/decision docs
docs/exec-plans/active/       active implementation plan
.github/workflows/            CI
```

## Backend quick start
```powershell
Copy-Item .env.example .env
make backend-install
make backend-dev
```

Health endpoint: `GET /health`

Run the durable worker in a second terminal:

```powershell
uv run --directory services/api python -m loose_thread_api.orchestration
```

## Checks
```bash
make check
```

Real-service validation requires the demo environment described in
[`docs/DEMO_RUNBOOK.md`](./docs/DEMO_RUNBOOK.md):

```powershell
make eval
make demo-seed
make demo-reset
make demo-smoke
```

The zero-cost demo deployment uses [`render.yaml`](./render.yaml) for the free Render API. Run
`make hosted-worker` locally against hosted Supabase while demonstrating the app. The API and worker
still use the same backend package and durable Postgres queue, so queued work survives either
process restarting.

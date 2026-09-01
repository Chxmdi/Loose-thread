# Loose Thread Architecture

## Thursday vertical slice

```text
Expo app
  -> local durable capture
  -> authenticated sync
  -> FastAPI
  -> Supabase/Postgres
  -> jobs table
  -> worker/orchestrator
       -> transcription when needed
       -> Thought Interpreter Agent
       -> persist thoughts
       -> embeddings
       -> candidate semantic search
       -> Continuity Agent
       -> persist relationships
  -> deterministic retrieval service
  -> <= 3 recommendations
  -> Resumption Agent when context is useful
  -> session/outcome
  -> feedback/calibration events
```

## Boundary principle
Agents perform semantic judgment. Deterministic code performs workflow control, authorization, persistence, retries, ranking, state transitions, and validation.

## Components

### `apps/mobile`
Expo client. Must persist a capture locally before network work, use anonymous Supabase auth for the demo, synchronize queued captures, request retrieval by capacity, display at most three cards, and record session outcomes.

### `services/api`
FastAPI service containing HTTP contracts, agents, durable worker/orchestrator, retrieval engine, data access, and debug/trace endpoints.

### `supabase`
SQL migrations, RLS policies, pgvector configuration, storage metadata, database functions/indexes, and seed/demo data utilities when safe.

### `docs`
System of record for product requirements, architecture decisions, and active execution plans.

## Backend module boundaries
- `agents/`: agent definitions, instructions, structured outputs, run wrappers.
- `orchestration/`: jobs state machine, worker claiming, retry/backoff, idempotency.
- `retrieval/`: eligibility, scoring, diversity, explanation/debug components.
- `db/`: database/session/repository abstractions.
- `models/`: Pydantic/domain models and enums.
- `routes/`: FastAPI HTTP endpoints only; keep business logic out.

## Required durable states
Recommended job states: `queued`, `running`, `succeeded`, `retry_wait`, `dead_letter`.
A worker claims jobs atomically with an owner/lease and increments attempts. Every handler must be idempotent.

## AI agents
1. **Thought Interpreter** — capture -> one or many validated thought interpretations.
2. **Continuity Agent** — new thought + deterministic nearest-neighbor candidates -> typed relationships or no relationship.
3. **Resumption Agent** — selected thought + grounded linked history -> concise cognitive context restoration.

Do not add an agent whose only purpose is to dispatch the other agents. Dispatch is deterministic orchestration code.

## Security
- user JWT for user-scoped API requests;
- Supabase RLS on every user-owned table;
- service-role credentials server-only;
- no service keys in Expo bundle;
- user ID comes from verified auth context, never request body trust;
- audio retention follows PRD policy and must be deletable.

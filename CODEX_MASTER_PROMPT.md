# Codex Master Execution Prompt — Loose Thread Thursday Demo

You are the primary implementation engineer for this repository. Your deadline is **Thursday, September 3, 2026**, with **feature freeze Wednesday night, September 2**.

Your job is not to create another plan. Your job is to implement, test, integrate, and harden the real end-to-end demo vertical slice.

## Start by reading
1. `AGENTS.md`
2. `CODEX_START_HERE.md`
3. `THURSDAY_STATUS.md`
4. `ARCHITECTURE.md`
5. `docs/exec-plans/active/THURSDAY-DEMO.md`
6. GitHub issue #13 and the P0 issues it links
7. Only the relevant PRD sections through `docs/product-specs/PRD-v1.md`

## Mission
Deliver this real path against real services:

```text
capture
→ local durable save
→ authenticated sync
→ durable Postgres job
→ Thought Interpreter Agent
→ one-or-many persisted thoughts
→ embeddings
→ Continuity Agent / persisted relationships
→ deterministic capacity-based retrieval
→ <=3 cards
→ selected open loop
→ grounded Resumption Agent
→ session
→ outcome / spawned thought
→ feedback persisted
```

## Architecture constraints
- React Native + Expo + TypeScript for mobile.
- Python 3.12+, FastAPI, Pydantic v2 and OpenAI Agents SDK for backend/agents.
- Supabase Auth/Postgres/Storage/pgvector for data/auth.
- Postgres-backed jobs state machine owns orchestration.
- Do **not** create an LLM dispatcher agent.
- Agents perform semantic judgment only.
- Deterministic code performs authorization, persistence, retries, state transitions, eligibility and final ranking.
- Final retrieval result is never selected by an LLM.
- All agent output is schema validated.
- Every meaningful agent run records inspectable metadata and a trace/correlation ID where available.

## Product invariants
- Never lose a capture because AI/network/backend/transcription/embedding failed.
- Keep raw user evidence distinct from model interpretation.
- Never invent commitment, urgency, deadlines, people or facts.
- Preserve explicit temporal language exactly when stated.
- One capture may produce multiple thoughts.
- Return at most three retrieval cards.
- Never replace the product with a backlog/dashboard/generic AI chat experience.
- RLS/user isolation is mandatory.

## Execution order
Use GitHub issue #13 as the command center and execute dependencies in this order:

1. #1 Supabase schema / pgvector / auth / RLS
2. #3 Durable jobs worker/orchestration
3. #5 Capture API + Thought Interpreter Agent
4. #6 Embeddings + Continuity Agent
5. #7 Deterministic retrieval engine
6. #9 Resumption Agent + sessions/outcomes
7. #10 Expo vertical slice
8. #11 Observability/evals throughout the above work
9. #12 Deployment + real smoke test + demo runbook

Mobile shell/local persistence may proceed in parallel when it does not conflict with backend contracts.

## Working rules
- Inspect code before editing.
- Make real implementations on the critical path; do not leave TODO placeholders.
- Keep routes thin and business logic testable.
- Add tests with each milestone rather than in one late batch.
- Run relevant tests after every meaningful change.
- Update `THURSDAY_STATUS.md` after each completed milestone with what changed, tests run, blockers and exact next action.
- Close/update the corresponding GitHub issue only when its acceptance criteria are actually satisfied.
- If credentials are missing, implement all real integration boundaries and tests that do not require them, document the exact environment variable/blocker, then immediately continue with unblocked work. Do not substitute fake production behavior.
- Prefer a complete hardened vertical slice over extra UI/features.

## Required gates
Before claiming the demo is ready:

```bash
make backend-check
make check
make demo-smoke
```

`make demo-smoke` must exercise the real deployed or real configured service path, not mocks.

Run the full smoke path **twice consecutively** before feature freeze.

## Demo observability
The Thursday demo should be able to prove the architecture, not merely show UI. Provide a safe debug surface/API that can show, for the current demo user:
- capture persisted,
- job transitions,
- interpreter run,
- thought split/metadata,
- embedding/continuity run,
- persisted relationship,
- retrieval score components and ranking version,
- resumption run/trace,
- session/outcome persistence.

Do not expose service-role credentials or unrelated user content.

## Final completion definition
Do not stop because scaffolding compiles, a single agent works, or screens render.

The task is complete only when the complete capture → orchestration → agents → retrieval → resumption → outcome path works end to end, the no-loss failure path is demonstrated, RLS isolation tests pass, eval gates pass, deployment is healthy, `make demo-smoke` passes twice, and `THURSDAY_STATUS.md` truthfully records that state.

Begin implementation immediately. Do not respond with another planning document unless a concrete implementation blocker requires one.

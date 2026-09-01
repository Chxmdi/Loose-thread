# Loose Thread — Codex Repository Guide

## Mission
Build the Thursday demo vertical slice described in `docs/exec-plans/active/THURSDAY-DEMO.md` without weakening the product rules in `docs/product-specs/PRD-v1.md`.

## Read first
1. `docs/exec-plans/active/THURSDAY-DEMO.md` — current deadline, scope, and done criteria.
2. `docs/product-specs/PRD-v1.md` — product truth and behavioral constraints.
3. `ARCHITECTURE.md` — system boundaries and implementation decisions.
4. `THURSDAY_STATUS.md` — living execution ledger. Update it as work progresses.

Do not re-read the entire PRD for every small task. Use the indexes/headings and inspect only relevant sections.

## Core product invariants
- Capture must never be lost because AI, network, transcription, embeddings, or enrichment failed.
- Raw user text/transcript is immutable source evidence and must remain distinct from AI-generated interpretations.
- One capture may produce zero, one, or many structured thoughts.
- Never strengthen user commitment or invent urgency, deadlines, people, facts, or temporal constraints.
- Preserve explicit temporal language when the user actually states it.
- Retrieval is code-driven and deterministic. An LLM may enrich/resume context but must not choose the final three items.
- Return at most three retrieval cards.
- All agent outputs are structured and schema validated.
- Background jobs are idempotent, retryable, observable, and safe to run more than once.
- All user-owned database data is protected by RLS/user isolation.
- Never commit secrets, service-role keys, tokens, private audio, or user data.

## Architecture rules
- Mobile: React Native + Expo + TypeScript.
- Backend/AI: Python 3.12+, FastAPI, OpenAI Agents SDK, Pydantic v2.
- Data/Auth: Supabase Postgres/Auth/Storage/pgvector.
- Durable orchestration: Postgres-backed `jobs` state machine; do not make the LLM the workflow engine.
- Prefer small specialist agents only where semantic judgment is needed.
- Keep business rules in ordinary testable Python functions/services.
- Every agent invocation must create an inspectable `agent_runs` record and preserve a trace identifier when available.

## Thursday priority order
P0 backend foundation -> durable jobs -> interpreter agent -> persistence/embeddings -> relationship agent -> deterministic retrieval -> resumption agent -> sessions/feedback -> mobile wiring -> failure handling -> evals -> deployment/demo polish.

If time is constrained, finish and harden the vertical slice before adding extra screens or speculative features.

## Working method
- Inspect existing code before editing.
- Make the smallest coherent change that advances the active execution plan.
- Add/update tests with behavior changes.
- Run relevant checks before committing.
- Keep commits narrow and descriptive.
- Update `THURSDAY_STATUS.md` after each meaningful milestone with: completed, tests run, blockers, next action.
- Do not leave placeholder TODO implementations on the critical demo path.
- If an external credential is missing, implement the real integration boundary, add a clear environment check, test everything possible locally, and record the blocker in `THURSDAY_STATUS.md` rather than replacing it with fake production behavior.

## Required validation
Backend:
`make backend-check`

Whole repository quick validation:
`make check`

Demo readiness once implemented:
`make demo-smoke`

Do not declare the Thursday vertical slice complete until the real end-to-end smoke path succeeds or an external-service blocker is documented precisely.

## Definition of done for code changes
- relevant tests pass;
- formatting/lint passes;
- no secrets or generated junk are added;
- product invariants remain true;
- failure/retry behavior is considered for backend work;
- `THURSDAY_STATUS.md` accurately reflects repository state.

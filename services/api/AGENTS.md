# Backend-specific Codex instructions

The backend is the Thursday demo priority.

- Use Python 3.12+, async FastAPI patterns, Pydantic v2, and OpenAI Agents SDK.
- Keep routes thin. Put business logic in services/modules.
- Use structured agent outputs; parse/validate before persistence.
- The jobs table is the orchestration authority. Do not create an LLM dispatcher/orchestrator agent.
- All job handlers must tolerate duplicate execution.
- Persist agent run metadata and trace IDs.
- Retrieval ranking must be ordinary deterministic Python with unit tests for every score component and eligibility rule.
- Never trust a user_id sent in JSON. Resolve identity from verified auth context.
- Add tests for success, malformed agent output, retries, idempotency, cross-user isolation, and no-loss capture behavior.
- `GET /health` must remain cheap and must not require OpenAI.

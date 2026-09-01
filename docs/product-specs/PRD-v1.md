# Loose Thread — PRD v1.0

This build-ready PRD is split into implementation-friendly sections so Codex can load only the product context relevant to the task at hand.

**Status:** Approved source of truth for the Thursday demo and MVP implementation.

## Read by area

1. [`PRD-v1-01-foundations.md`](./PRD-v1-01-foundations.md) — executive summary, problem, thesis, users, principles, core loop, concepts, meaning model, temporal model.
2. [`PRD-v1-02-capture-retrieval.md`](./PRD-v1-02-capture-retrieval.md) — duration/context/energy, lifecycle, capture, interpretation, provenance, background intelligence, retrieval.
3. [`PRD-v1-03-resumption-platform.md`](./PRD-v1-03-resumption-platform.md) — feedback, resumption, personalization, identity, sync, privacy, UX, failure states, copy, accessibility, architecture.
4. [`PRD-v1-04-data-evals-scope.md`](./PRD-v1-04-data-evals-scope.md) — data model, service contracts, analytics, metrics, AI eval suite, experimentation, MVP scope.
5. [`PRD-v1-05-acceptance-launch.md`](./PRD-v1-05-acceptance-launch.md) — MVP acceptance criteria, edge cases, implementation epics, launch, risks, resolved decisions, product questions, north star.

## Non-negotiable product rules

- Capture must never be lost because AI, network, transcription, embeddings, or enrichment failed.
- Raw user evidence stays distinct from AI inference.
- One capture may produce zero, one, or many thoughts.
- Never invent commitment, urgency, deadlines, people, facts, or temporal constraints.
- Preserve explicit temporal language the user actually stated.
- Retrieval is deterministic code and returns at most three cards.
- The product restores cognitive continuity rather than becoming a conventional backlog/task manager.
- All AI output is structured, validated, traceable, and recoverable.
- User-owned data is isolated with RLS and privacy behavior must match product promises.

For the current deadline, also read [`../exec-plans/active/THURSDAY-DEMO.md`](../exec-plans/active/THURSDAY-DEMO.md) before implementing.

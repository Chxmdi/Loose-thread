# Loose Thread — Engineering Decisions

This log records decisions Codex should preserve unless implementation evidence requires a change. If a decision changes, append a dated replacement rather than silently rewriting history.

## 2026-09-01 — Thursday vertical slice over broad MVP completion
The September 3 demo targets a complete production-shaped vertical slice rather than every long-term PRD feature. Backend correctness, AI agents, durable orchestration, retrieval, observability, and the end-to-end demo path outrank secondary UI/features.

## 2026-09-01 — Deterministic orchestration, specialist semantic agents
Workflow sequencing, retries, authorization, persistence, job state, idempotency, and side effects are ordinary code backed by a durable Postgres jobs table. Do not create a manager LLM to dispatch the workflow. Agents are used only where semantic judgment is valuable.

## 2026-09-01 — Three AI specialists
The Thursday architecture has three semantic specialists:
1. Thought Interpreter Agent
2. Continuity / Relationship Agent
3. Resumption Agent

All outputs are structured, schema-validated, observable, and recoverable.

## 2026-09-01 — Retrieval is not an agent
The final retrieval set is selected by deterministic eligibility + scoring + bounded diversity code and returns at most three cards. AI may enrich thought metadata and relationships, but it does not choose the final three recommendations.

## 2026-09-01 — Supabase as the demo platform foundation
Use Supabase Postgres/Auth/Storage/pgvector. Invisible anonymous auth provides a real authenticated user identity for the demo while preserving the account-light first-run product experience. Service-role credentials remain server-only.

## 2026-09-01 — Explicit Supabase grants and owner columns
Every user-owned public table carries a non-null user ID, including relationship and join tables,
so RLS and cross-owner foreign keys are simple and auditable. Data API auto-exposure is disabled;
authenticated access is granted explicitly, and internal worker/vector functions live in a private
schema. This is more verbose than parent-only ownership but reduces authorization ambiguity under
the Thursday deadline.

## 2026-09-01 — Fixed 1536-dimension demo embeddings
The Thursday schema uses 1536-dimension vectors and an HNSW cosine index, matching the intended
small embedding model. Supporting a different embedding dimension requires a migration rather
than silently mixing incompatible vectors.

## 2026-09-01 — Postgres-backed jobs before Redis/Temporal
For the deadline, use a Postgres durable queue with atomic claiming, leases, attempts, retry/backoff, dead-letter state, and idempotency keys. This minimizes infrastructure while preserving production-shaped behavior.

## 2026-09-01 — Raw evidence and inference are separate
Raw capture text/transcript is immutable user evidence. AI-refined text and metadata are derived/versioned inference. AI failure must never destroy or block the raw capture.

## 2026-09-01 — PRD split for Codex context efficiency
`docs/product-specs/PRD-v1.md` is the index into five implementation-focused PRD sections. The split is organizational only; together they are the product source of truth.

## How to add a decision
Append:
- date
- decision
- alternatives considered
- reason
- consequences/migration notes

Keep this file concise; detailed designs belong under `docs/design-docs/`.

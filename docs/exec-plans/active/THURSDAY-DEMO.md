# Loose Thread — Codex Thursday Demo Build Brief

**Deadline:** Thursday, September 3, 2026  
**Code-complete target:** Wednesday night, September 2, 2026  
**Primary goal:** A real end-to-end Loose Thread demo with the AI agents, durable task orchestration, backend, data model, retrieval engine, and mobile client working together.

---

## 1. Build target

Do not attempt to ship every long-term PRD feature. Build the smallest production-shaped vertical slice that proves the complete product loop:

```text
CAPTURE
  -> local save
  -> sync
  -> durable background job
  -> transcription
  -> interpretation agent
  -> one-or-many Thoughts
  -> embeddings
  -> relationship agent
  -> persisted graph/context
  -> user declares capacity
  -> deterministic retrieval engine
  -> <=3 recommendations
  -> user selects one
  -> resumption agent restores context when appropriate
  -> session
  -> feedback/outcome
  -> calibration event stored
```

The Thursday demo is successful only if this path runs against real services and a real database, not hard-coded mock data.

### Non-negotiables

1. Capture must survive AI/backend failure.
2. Raw user text/transcript must remain distinct from AI inference.
3. One capture may create multiple thoughts.
4. Agent outputs must be structured and schema-validated.
5. Explicit temporal language must be preserved; agents must never invent deadlines or commitments.
6. Retrieval must be deterministic/code-driven, not chosen by an LLM.
7. No more than three retrieval cards.
8. Agent and workflow execution must be inspectable.
9. Every background task must be idempotent and retryable.
10. RLS/user isolation must be tested.
11. No secrets committed.
12. Thursday morning is for demo validation, not feature building.

---

## 2. Recommended implementation stack

### Mobile
- React Native + Expo + TypeScript
- Expo Router
- expo-av / current supported Expo audio recording package
- SQLite for local-first capture queue
- Supabase JS for Auth/Data
- TanStack Query for server state if useful
- Zod for client contracts

### Backend / AI
- Python 3.12+
- FastAPI
- OpenAI Agents SDK for Python
- Pydantic v2 structured outputs/contracts
- Supabase Postgres
- pgvector
- Supabase Storage for temporary audio
- async worker process using Postgres-backed durable jobs

### Why this split
The mobile client stays idiomatic Expo/TypeScript. Python is used for the AI runtime because the Agents SDK and eval workflow are excellent there and it keeps agent code concise. Supabase provides Auth, RLS, Postgres, vector storage, and object storage in one place.

### Identity simplification for the demo
Use Supabase anonymous sign-in invisibly on first launch so every record has a real authenticated user ID while the product still feels account-free. Later, link the anonymous account to email/OAuth. Do not build a bespoke anonymous migration system for Thursday unless it already exists.

---

## 3. Architecture

```text
┌───────────────────────────────┐
│ Expo Mobile App               │
│                               │
│ Audio/Text Capture            │
│ Local SQLite                  │
│ Sync Queue                    │
│ Capacity / Retrieval UI       │
│ Session / Feedback UI         │
└──────────────┬────────────────┘
               │
               ▼
┌───────────────────────────────┐
│ Supabase                      │
│ Auth                          │
│ Postgres + RLS                │
│ pgvector                      │
│ Storage                       │
│ jobs / agent_runs / events    │
└──────────────┬────────────────┘
               │
               ▼
┌───────────────────────────────┐
│ FastAPI AI Service            │
│                               │
│ /health                       │
│ /captures                     │
│ /retrievals                   │
│ /sessions                     │
│ /feedback                     │
│ /debug/agent-runs             │
└──────────────┬────────────────┘
               │
               ▼
┌───────────────────────────────┐
│ Durable Worker / Orchestrator │
│                               │
│ Job claiming                  │
│ retries/backoff               │
│ idempotency                   │
│ dead-letter state             │
└───────┬─────────┬─────────────┘
        │         │
        ▼         ▼
┌─────────────┐  ┌────────────────┐
│ OpenAI      │  │ Deterministic  │
│ Agents      │  │ Retrieval      │
│ SDK         │  │ Engine         │
└─────────────┘  └────────────────┘
```

---

## 4. Agent design

Do not create agents merely to make the architecture look agentic. Use agents only for semantic judgment.

### Agent A — Thought Interpreter

**Purpose:** Turn a transcript/text capture into one or more structured thoughts while preserving user meaning.

**Input:**
- capture_id
- raw_text/transcript
- capture timestamp/timezone

**Output:** validated `InterpretationResult` containing `thoughts[]`:
- refined_text
- kind
- commitment_strength
- duration_bucket
- energy
- contexts
- entities
- temporal literal/type/resolved_at
- open_loop state/type
- surface_policy
- field-level confidence

**Hard rules:**
- never strengthen a commitment
- never invent a temporal constraint
- preserve ambiguous language
- never answer a question instead of storing it
- do not turn feelings into advice
- may split multiple independent thoughts

No external tools are required for the first version other than deterministic date parsing if needed.

### Agent B — Continuity / Relationship Agent

**Purpose:** Decide whether a newly created thought meaningfully relates to nearby historical thoughts.

**Deterministic pre-step:**
1. Generate embedding for new thought.
2. Retrieve nearest same-user candidates from pgvector.
3. Exclude the source thought and obvious duplicates.

**Agent input:**
- new thought
- top candidate thoughts with IDs, timestamps and relevant metadata

**Output:** zero or more validated relationships:
- from_thought_id
- to_thought_id
- relation_type
- confidence
- rationale for internal debugging only

Allowed relations:
- continues
- elaborates
- answers
- contradicts
- references
- spawned_from
- same_topic
- same_person
- same_project

The model must never create relationships to IDs that were not provided in the candidate set.

### Agent C — Resumption Agent

**Purpose:** Restore cognitive context when a selected thought is unfinished/open-loop and has sufficient supporting history.

**Tools:**
- `load_related_thoughts(thought_id)`
- `load_thread_context(thought_id)` if threads are implemented

**Output:**
- short `where_you_got_to` summary
- supporting thought IDs
- unresolved question/loop if supported
- optional suggested continuation prompt

**Hard rule:** Every factual assertion in the resumption summary must be traceable to supplied thought IDs. No invented conclusion.

### Retrieval is NOT an agent

Implement retrieval as code using eligibility filters and interpretable scoring. This is critical for reliability and for the demo: the UI should be able to show internal score components on a debug screen.

### Orchestration is code-first

Use a workflow function/task runner, not a general “manager agent,” for the ingestion pipeline. Agents do semantic work; code decides sequencing, retries, state transitions and side effects.

---

## 5. Durable task orchestration

Implement a Postgres-backed `jobs` queue to avoid adding Redis/Temporal infrastructure under the deadline.

### `jobs`

```sql
id uuid primary key
user_id uuid not null
job_type text not null
entity_type text not null
entity_id uuid not null
status text not null -- queued|running|succeeded|failed|dead
priority int not null default 100
attempts int not null default 0
max_attempts int not null default 5
run_after timestamptz not null default now()
locked_at timestamptz
locked_by text
idempotency_key text unique not null
payload jsonb not null default '{}'
last_error text
created_at timestamptz not null default now()
updated_at timestamptz not null default now()
```

Worker claims with `FOR UPDATE SKIP LOCKED` through a SQL function/RPC.

### Required job types

```text
transcribe_capture
interpret_capture
embed_thought
link_thought
build_resumption_context (on-demand or cached)
apply_feedback_calibration
cleanup_expired_audio
```

### Ingestion DAG

```text
capture_received
  |
  +--> if audio: transcribe_capture
  |       |
  |       +--> interpret_capture
  |
  +--> if text: interpret_capture
          |
          +--> thought_1 -> embed_thought -> link_thought
          +--> thought_2 -> embed_thought -> link_thought
          +--> thought_n -> embed_thought -> link_thought
```

Each downstream job is created idempotently.

### Retry policy

- attempts 1–2: 5–15 seconds with jitter
- attempt 3: 1 minute
- attempt 4: 5 minutes
- attempt 5: dead-letter

Model/schema validation errors may retry after a repair path; permission/ownership errors should fail permanently.

### Agent run observability

Create `agent_runs`:

```sql
id uuid primary key
user_id uuid not null
job_id uuid
agent_name text not null
model text not null
status text not null
input_entity_ids jsonb
output_entity_ids jsonb
openai_trace_id text
started_at timestamptz
completed_at timestamptz
latency_ms integer
usage jsonb
error_code text
error_message text
created_at timestamptz default now()
```

Create `agent_run_steps` only if easy. Otherwise rely on OpenAI Agents SDK tracing for detailed tool/handoff traces and keep `agent_runs` as the application-level ledger.

Never store raw thought content in ordinary logs.

---

## 6. Minimum database model

Required tables for Thursday:

- captures
- thoughts
- thought_relationships
- retrievals
- retrieval_impressions
- sessions
- feedback_events (or general events)
- user_calibration
- jobs
- agent_runs

Optional if time allows:
- threads
- thread_memberships
- agent_run_steps

### `captures`
Must preserve original source and processing states.

### `thoughts`
Must include at least:
- id
- user_id
- capture_id
- raw_fragment/ref to source
- refined_text
- kind
- commitment_strength
- duration_bucket
- energy
- contexts jsonb
- entities jsonb
- temporal jsonb
- open_loop jsonb
- surface_policy
- confidence jsonb
- status
- embedding vector
- enrichment_version
- created_at/updated_at

### RLS
Every user-owned table must restrict SELECT/INSERT/UPDATE/DELETE to `auth.uid() = user_id` or ownership through a parent record.

Create SQL tests proving user A cannot read or mutate user B data.

---

## 7. API contracts

### `POST /v1/captures`
Registers a synced capture and schedules processing.

Returns immediately:
```json
{
  "capture_id": "uuid",
  "processing_status": "queued"
}
```

### `GET /v1/captures/{id}`
Returns capture processing state and generated thoughts.

### `POST /v1/retrievals`
Input:
```json
{
  "window": "5|15|30|60|a_while",
  "contexts": {
    "phone_only": false,
    "out": false,
    "home": false,
    "low_energy": false
  },
  "reshuffle_of": null
}
```

Returns <= 3 cards plus retrieval ID.

### `POST /v1/retrievals/{id}/action`
Actions:
- start
- not_now
- done_with_this
- none_of_these

### `POST /v1/sessions`
Start a session from a retrieval result.

### `POST /v1/sessions/{id}/complete`
Input:
- outcome: done|partial|stopped|spawned_new
- fit: shorter|right|longer
- actual_minutes optional

### `GET /v1/thoughts/{id}/resumption`
Invokes/returns cached Resumption Agent output when appropriate.

### `GET /health`
Must not call external AI. Return backend/db readiness.

### Debug endpoints
Behind development/admin guard only:
- `GET /debug/jobs`
- `GET /debug/agent-runs`
- `GET /debug/retrievals/{id}`

These are important for the Thursday demo.

---

## 8. Retrieval engine

### Hard eligibility
Exclude:
- deleted/done/archived/dormant
- surface_policy not eligible for ordinary retrieval
- snoozed until future
- clearly incompatible hard context
- recently surfaced fatigue window

Do not hard-filter from low-confidence inferred context.

### Initial score

```text
0.22 rediscovery_value
0.20 capacity_fit
0.14 context_fit
0.14 open_loop_value
0.10 thread_momentum
0.08 personal_kind_affinity
0.07 explicit_temporal_relevance
0.05 novelty
- fatigue_penalty
- rejection_penalty
```

Put weights in config, not code constants scattered across files.

### Selection
- sort by score
- deduplicate semantically near-identical options
- bounded diversity when scores are close
- return 1–3 good results; never pad to three
- one reshuffle maximum

Persist all candidate/selected score components for debugging/evals.

---

## 9. Mobile screens required for the demo

Only implement these deeply:

1. **Capture/Home**
   - mic
   - text fallback
   - local saved state
   - latest processing status

2. **Capture Confirmation**
   - raw/refined text
   - multiple thoughts if split
   - inferred duration chip

3. **Capacity Picker**
   - 5 / 15 / 30 / 60 / a while
   - low-energy and phone-only optional toggles

4. **Three Options**
   - max 3
   - Start/Pick this back up
   - Not now
   - Done with this
   - None of these, then one reshuffle

5. **Resumption/Session**
   - selected thought
   - original context
   - AI resumption summary if available
   - capture continuation

6. **Wrap**
   - shorter/right/longer
   - done/partial/stopped/spawned new

7. **Dev Diagnostics**
   - current capture/job status
   - agent run status
   - trace ID
   - retrieval score components

Do not spend Tuesday on visual polish beyond clean, usable UI.

---

## 10. Evals and tests that must exist

### Interpreter agent eval cases
At minimum:
1. one clean task
2. pure idea
3. question
4. unfinished sentence
5. two unrelated thoughts in one capture
6. “maybe” speculative language
7. explicit commitment
8. quoted commitment belonging to someone else
9. explicit deadline
10. ambiguous date
11. feeling
12. self-correction
13. slang/transcription noise
14. “don’t remind me to…” negative instruction

Grade:
- JSON/schema validity
- semantic preservation
- no invented commitment
- no invented deadline
- correct splitting
- reasonable open-loop detection

### Retrieval tests
- 0 eligible results
- 1 eligible result
- >3 results
- near duplicates
- low-confidence context
- temporal relevance
- not-now fatigue
- one reshuffle limit
- deterministic result for fixed fixtures/ranking version

### Integration smoke
Create `scripts/demo_smoke.py` or equivalent that:
1. creates/uses a test user
2. posts text capture
3. waits for processing
4. verifies thoughts created
5. posts a second related capture
6. verifies relationship agent output
7. requests 15-minute retrieval
8. selects result
9. requests resumption
10. completes session
11. verifies feedback event

The script exits non-zero on any failure.

---

## 11. Repository structure

```text
loose-thread/
  apps/
    mobile/
      app/
      src/
      package.json
    api/
      app/
        main.py
        api/
        auth/
        db/
        models/
        services/
        config.py
      pyproject.toml
  packages/
    agents/
      interpreter.py
      relationship.py
      resumption.py
      schemas.py
      prompts/
    orchestration/
      jobs.py
      worker.py
      workflows/
        ingest_capture.py
        process_thought.py
        feedback.py
    retrieval/
      eligibility.py
      scoring.py
      diversity.py
      config.py
  supabase/
    migrations/
    seed.sql
    tests/
  evals/
    interpreter/
    retrieval/
    fixtures/
  scripts/
    demo_seed.py
    demo_smoke.py
  docs/
    ARCHITECTURE.md
    AGENTS.md
    DEMO_RUNBOOK.md
    DECISIONS.md
  .env.example
  Makefile
  README.md
```

Adapt to the existing repo instead of blindly replacing structure if a project already exists.

---

## 12. Tuesday, September 1 — Backend and agent day

### Morning — Foundation
- inspect existing repo and PRD
- establish monorepo boundaries
- create Supabase migrations
- enable pgvector
- create RLS policies/tests
- implement anonymous auth flow
- create FastAPI skeleton and auth middleware
- implement jobs table + claim/complete/fail RPCs
- create worker process

**Checkpoint:** Can insert a capture and observe a durable job get claimed and completed without OpenAI.

### Midday — AI interpretation
- add Agents SDK
- create Pydantic schemas
- implement Thought Interpreter Agent
- structured output validation/retry/fallback
- persist thoughts
- build interpreter eval cases

**Checkpoint:** Real text captures become real structured thoughts; multiple thought split works.

### Afternoon — Embedding, graph, orchestration
- embedding service
- pgvector similarity query
- Relationship Agent
- persist thought relationships
- `agent_runs` ledger
- Agents SDK trace IDs
- idempotency/retry behavior

**Checkpoint:** Two semantically related captures become linked through real agent execution.

### Evening — Retrieval backend
- eligibility filters
- scoring
- diversity/dedup
- retrieval logging
- retrieval API
- session API
- feedback events
- preliminary calibration aggregates

**Tuesday exit condition:** Backend vertical slice works through API/smoke script with real models.

---

## 13. Wednesday, September 2 — Mobile integration and resumption day

### Morning — Mobile
- capture UI
- text capture first; voice immediately after
- local SQLite write
- anonymous Supabase session
- upload/sync path
- capture processing status
- confirmation UI

### Midday — Retrieval flow
- capacity picker
- retrieval cards
- action buttons
- session creation
- wrap flow

### Afternoon — Resumption agent
- implement Resumption Agent
- load related thoughts tool
- evidence IDs in output
- resumption endpoint
- resumption UI
- spawned-thought linkage

### Late afternoon — Failure behavior
- network-off capture
- AI failure fallback
- malformed structured output
- job retry/dead-letter display
- insufficient retrieval result handling

### Evening — Demo hardening
- seed script with 20–40 compelling sample thoughts
- full demo smoke
- fix all blockers
- deploy backend if credentials/environment available
- configure mobile API endpoint
- create `DEMO_RUNBOOK.md`
- freeze feature work

**Wednesday exit condition:** Complete demo works from a fresh app install against real backend/services.

---

## 14. Thursday, September 3 — No core feature work

Run the demo script and manual demo several times.

Demo sequence:

1. Open app directly to capture.
2. Record: “Ask Maya if the launch deck is ready, and maybe figure out why the recommendation model treats ‘not now’ like dislike.”
3. Show that the capture is saved immediately.
4. Open diagnostics briefly: transcription -> interpreter agent -> two thoughts -> embedding -> relationship jobs.
5. Show the structured result, emphasizing commitment preservation.
6. Capture a related fragment: “Actually, timing might need to be its own feature because not now can mean interested later.”
7. Show the Relationship Agent linking the thoughts.
8. Tap “I have 15 minutes.”
9. Show at most three results from deterministic ranking.
10. Pick the recommendation-model open loop.
11. Show the Resumption Agent reconstructing where the user got to, with evidence from the linked captures.
12. Continue with a new capture.
13. End session and record “about right / partial” feedback.
14. Show the feedback event and retrieval score/trace in diagnostics.
15. Optionally disable network/model access and show capture still saving locally.

This demo communicates the entire product moat in under ten minutes.

---

## 15. Definition of done

### Backend
- [ ] FastAPI `/health`
- [ ] authenticated user context
- [ ] Supabase schema and migrations
- [ ] RLS ownership tests
- [ ] durable jobs queue
- [ ] retry/backoff/dead-letter handling
- [ ] idempotent capture processing
- [ ] pgvector embeddings
- [ ] retrieval engine
- [ ] sessions/feedback
- [ ] agent run ledger

### Agents
- [ ] Interpreter Agent real OpenAI run
- [ ] structured output validation
- [ ] Relationship Agent real OpenAI run
- [ ] Resumption Agent real OpenAI run
- [ ] Agent SDK tracing enabled in server runtime
- [ ] prompt files versioned
- [ ] eval fixture set

### Mobile
- [ ] text capture
- [ ] voice capture
- [ ] local-first persistence
- [ ] automatic sync
- [ ] confirmation
- [ ] capacity picker
- [ ] <=3 retrieval cards
- [ ] resumption/session
- [ ] feedback wrap
- [ ] minimal diagnostics

### Demo/reliability
- [ ] `.env.example`
- [ ] no secrets in git
- [ ] demo seed
- [ ] demo smoke script
- [ ] demo runbook
- [ ] offline capture test
- [ ] model failure fallback test
- [ ] README run commands
- [ ] Dockerfile/backend deployment configuration

---

## 16. What to cut first if behind

Cut in this order:

1. polished library/search screen
2. visible thread UI
3. user-facing auth conversion screen
4. duration personalization beyond storing feedback
5. background thread summary caching
6. sophisticated energy/context inference
7. advanced dormancy
8. export/delete UI (keep backend primitives if possible)

Do NOT cut:
- durable orchestration
- Interpreter Agent
- Relationship Agent
- Resumption Agent
- structured outputs
- raw-vs-inferred provenance
- retrieval engine
- RLS
- agent/job diagnostics
- end-to-end smoke path

---

## 17. Codex operating instructions

Codex should work autonomously through milestones and should not stop after scaffolding.

Rules:

1. Inspect the entire existing repo before editing.
2. Treat the PRD as authoritative unless this build brief explicitly narrows Thursday scope.
3. Reuse existing architecture where sound.
4. Do not rewrite working code merely for style.
5. Maintain `docs/DECISIONS.md` with important tradeoffs.
6. After each milestone, run tests and smoke commands before continuing.
7. Fix failures rather than commenting them out.
8. Use real implementations in the primary path; mocks are allowed only in tests.
9. Never expose service-role keys to the Expo client.
10. Keep OpenAI calls server-side.
11. Validate all agent outputs before persistence/action.
12. Keep deterministic actions in code/tools, not model prose.
13. Every job must be safe to retry.
14. Every external side effect must have an idempotency key.
15. Record agent run metadata and trace IDs.
16. Add useful logs, but never raw private thought content to ordinary logs.
17. Do not ask for product clarification unless truly blocked by a missing credential or inaccessible external service; choose the simplest PRD-consistent implementation and document the decision.
18. Commit in coherent milestones when git is available.
19. Do not declare completion until `scripts/demo_smoke.py` and the documented manual demo path pass.
20. If deployment credentials are unavailable, finish a deployable Dockerized backend and prove the complete flow locally.

---

## 18. Master prompt to give Codex

You are the lead engineer responsible for getting Loose Thread to a fully working Thursday demo. Read the complete `loose-thread-prd-v1-build-ready.md` and this `CODEX_THURSDAY_BUILD_BRIEF.md` before changing code.

The deadline is Thursday, September 3, 2026. Wednesday night is code freeze. Build a production-shaped vertical slice, not a fake prototype. The centerpiece of the demo must be the backend, AI agents, durable tasks/orchestration, retrieval engine, and the complete end-to-end loop.

Implement the system described in this build brief. Use a React Native/Expo mobile client, Supabase for Auth/Postgres/pgvector/Storage/RLS, and a Python FastAPI AI backend using the OpenAI Agents SDK. Use code-driven durable orchestration with a Postgres-backed jobs queue. Agents should handle semantic judgment, while workflow sequencing, retries, persistence, filtering, ranking and side effects remain deterministic code.

Implement three real agents:

1. Thought Interpreter Agent — structured multi-thought interpretation that preserves intent, commitment strength, temporal language, open loops, effort/context metadata and confidence.
2. Continuity/Relationship Agent — receives pgvector-selected candidate neighbours and returns validated relationships only among supplied thought IDs.
3. Resumption Agent — reconstructs “where you got to” from persisted related thoughts and returns evidence thought IDs; it must never invent unsupported conclusions.

Do NOT make retrieval an LLM agent. Implement deterministic eligibility/scoring/diversity and persist score components so the result is explainable internally.

Build durable jobs for transcription, interpretation, embeddings, relationship linking, resumption context where appropriate, feedback calibration and audio cleanup. Jobs must be idempotent, retryable and observable. Add `agent_runs` and capture OpenAI trace IDs.

Use invisible Supabase anonymous authentication for the Thursday build so the first-run experience remains account-free while records still receive a stable authenticated user ID and RLS applies. Keep the architecture compatible with later identity linking.

Build the mobile path: local-first voice/text capture, sync, confirmation, capacity picker, <=3 retrieval cards, resumption/session, wrap feedback and a minimal dev diagnostics screen showing job/agent status and retrieval score components.

Create database migrations, RLS policies and tests. Never expose service-role or OpenAI keys in the mobile bundle. Keep raw thought content out of normal logs. Preserve raw source separately from model inference.

Create interpreter/retrieval eval fixtures and a real `scripts/demo_smoke.py` that exercises capture -> processing -> thoughts -> relationship -> retrieval -> session -> resumption -> feedback. It must exit non-zero on failure.

Create/update:
- README.md with exact run commands
- `.env.example`
- `docs/ARCHITECTURE.md`
- `docs/AGENTS.md`
- `docs/DECISIONS.md`
- `docs/DEMO_RUNBOOK.md`

Run tests continuously. Do not stop at TODOs or scaffolds. Do not declare success until the real vertical slice works locally from a fresh environment and the demo smoke path passes. If deployment credentials are already available, deploy the backend and point the Expo client to it. If credentials are missing, leave the backend Dockerized and immediately runnable, document the blocker, and continue finishing every local capability.

When tradeoffs are required, prioritize in this order:
1. backend correctness and durable orchestration
2. AI agent correctness and observability
3. end-to-end demo path
4. retrieval/resumption quality
5. offline/failure reliability
6. mobile UI polish
7. non-demo secondary features

Begin by inspecting the repo and writing a short implementation checklist into `docs/THURSDAY_STATUS.md`. Then execute it immediately, updating that file as milestones pass. Do not wait for further instructions unless an external credential is truly required.

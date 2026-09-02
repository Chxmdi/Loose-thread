# Thursday Demo Status

**Deadline:** Thursday, September 3, 2026  
**Feature freeze:** Wednesday night, September 2, 2026

## Overall
- [x] GitHub repository created and populated
- [x] Repository execution scaffold
- [x] Build-ready PRD included and indexed for Codex
- [x] Thursday build plan included
- [x] Codex instructions included
- [x] FastAPI health skeleton + tests + CI baseline
- [x] Supabase schema + RLS
- [x] FastAPI capture API
- [x] Durable jobs worker
- [x] Thought Interpreter Agent
- [x] Embeddings + vector search
- [x] Continuity Agent + graph persistence
- [x] Deterministic retrieval engine
- [x] Resumption Agent
- [x] Session + feedback APIs
- [x] Durable feedback calibration consumed by retrieval
- [x] Expo web demo vertical slice
- [x] Agent/debug trace endpoint
- [x] In-app architecture inspector with jobs, traces, ranking, feedback, and calibration
- [x] Ordered end-to-end process trace with every agent input, decision, and output handoff
- [x] Local/e2e eval harness
- [x] Deployment
- [x] Real demo smoke test passing

## Current blockers
None for the owner-selected Expo web demo target. Native packaging remains unverified and is outside
the Thursday web-demo scope.

## Next action
On Thursday, start `make hosted-worker`, start Expo web with the documented public hosted values,
and run the rehearsed demo without editing code. The browser demo, free Render API, hosted Supabase,
and two-pass hybrid smoke gate are frozen and ready.

## Milestone log
### End-to-end agent process trace — September 2, 2026
Expanded the architecture inspector with a correlation-aware, 20-step trace assembled from persisted
jobs, agent runs, retrieval impressions, feedback events, and calibration state. The trace shows each
agent as three distinct stages: evidence loaded, model decision made under a versioned prompt, and
validated outputs persisted. It also shows the durable worker, embedding, retrieval, session, and
calibration handoffs around those agents. Agent-run rows now display concrete input and output entity
IDs alongside model, latency, prompt version, run ID, and OpenAI trace ID.

Verification:
- The populated browser rehearsal displays all 20 real steps from capture commit through learned
  preferences becoming available to the next ranking; no placeholder steps are rendered.
- The trace is unit-tested for ordering, all three agents, entity handoffs, outcome feedback, and
  calibration, and the empty state is verified not to invent evidence.
- Repository checks pass with 22 backend tests and 5 mobile unit tests; Playwright passes all three
  web flows and horizontal-overflow checks at phone and desktop widths.
- Two fresh consecutive hybrid smoke runs pass all nine stages against the deployed Render API,
  hosted Supabase, and real OpenAI agents after this inspector change.

### Visible agentic architecture — September 2, 2026
Replaced the generic diagnostics list with a complete in-app architecture inspector. The web demo
now exposes local capture durability, job attempts and correlation IDs, agent model/latency/prompt
and OpenAI trace IDs, persisted deterministic retrieval scores and every ranking component,
feedback-event calibration status, and all learned kind/duration/context values. Capture confirmation
shows the Thought Interpreter's structured fields, and the session view shows the Resumption Agent's
cited supporting thoughts, relationship types, unresolved loop, and suggested prompt. Selecting a
card now records the missing `start` feedback action before calibration.

Verification:
- Two fresh consecutive hosted smoke runs pass with authenticated feedback diagnostics included in
  the contract.
- Real browser rehearsal passes Interpreter -> Continuity -> retrieval -> cited Resumption -> start
  feedback -> session completion -> durable calibration.
- The final live inspector shows all three agent types with trace IDs, three ranked candidates with
  persisted components, five calibrated events, task affinity `0.74`, snack adjustment `+0.15`, and
  home context affinity `0.54`.
- Playwright passes the no-capture path, failure persistence, all inspector sections, and horizontal
  overflow checks at `390x844` and `1440x900`.

### Feedback calibration demo gate — September 2, 2026
Implemented the complete feedback loop behind the web demo. Retrieval starts and session outcomes now
enqueue idempotent `apply_feedback_calibration` jobs in the same transaction as their immutable
feedback events. The worker atomically updates bounded per-user kind, duration, and context
preferences and marks each event applied, so retries cannot double-count it. Retrieval consumes all
three preference maps, and authenticated diagnostics expose the safe aggregate state.

Verification:
- Repository checks pass: 21 backend tests, strict MyPy, Ruff, script checks, TypeScript, and 3
  mobile tests; 25 environment-gated tests remain skipped by the default local command.
- Hosted Postgres integration tests pass the real migration and prove durable enqueue, preference
  updates, and replay-safe application.
- Two consecutive hosted smoke runs pass the full real OpenAI/Supabase/Render flow. The second run
  produced 10 succeeded jobs, 6 inspectable agent runs, 2 calibration jobs, 2 applied observations,
  and a subsequent retrieval with learned kind affinity `0.56` (baseline `0.50`).

### Direct retrieval entry — September 2, 2026
Added a `See what fits` action on the capture screen so the owner-selected web demo can open the
capacity picker and retrieve existing thoughts without recording or saving a new capture. The
targeted Playwright navigation test and the live hosted browser flow pass. Follow-up testing in the
owner's Edge session exposed and fixed transient Render request handling, permanent suppression from
cumulative surface fatigue, and a `0.419` versus `0.420` threshold edge for fresh unknown-duration
thoughts. The recovered capture synced and `Finish learning RAG` then appeared as a fitting card.

### Web demo freeze — September 2, 2026
The owner selected Expo web as the Thursday presentation target. Fixed and regression-tested the
Render CORS preflight for `localhost:8081` and `127.0.0.1:8081`, then verified the real browser path
against Render and hosted Supabase: queued-capture recovery, anonymous authentication, multi-thought
interpretation, deterministic two-card retrieval, grounded resumption, session completion, and
succeeded job/agent diagnostics. Two additional consecutive hosted smoke runs passed after the fix.
Feature work is frozen; the Thursday flow requires startup commands only and no code edits.

### Hosted Supabase ready — September 1, 2026
Enabled anonymous sign-ins and applied `20260901164219_initial_schema.sql` to the configured hosted
project. The hosted database passes all 13 pgTAP RLS assertions. A real anonymous Auth session
queried the migrated `captures` Data API endpoint successfully with zero cross-user rows visible;
the temporary verification user was removed afterward.

### GitHub bootstrap — September 1, 2026
Repository is live at `Chxmdi/Loose-thread`. Added Codex-native source-of-truth docs, Thursday execution plan, indexed build-ready PRD, backend health service, CI checks, environment template, issue/PR templates, smoke-test gate, and active execution ledger.

### Product specification packaging
The build-ready PRD is split into five implementation-friendly documents behind `docs/product-specs/PRD-v1.md`, allowing Codex to load only the relevant product context for a task while preserving the complete specification.

### Issue #1 Supabase foundation — September 1, 2026
Added the complete Thursday schema for captures, thoughts, graph relationships, threads,
retrievals/impressions, sessions, feedback/calibration, durable jobs, and agent runs. Added
pgvector with an HNSW cosine index, immutable raw-capture evidence, explicit Data API grants,
anonymous-auth configuration, private audio storage policies, retry-safe uniqueness constraints,
and owner-scoped RLS on all 12 user-owned tables.

Verification:
- Supabase local database reset passed against a fresh Postgres 17 stack.
- Supabase database tests passed 13 pgTAP assertions, including cross-user read/write isolation
  and capture idempotency.
- Supabase database advisors reported no security or performance warnings.

### Issue #3 durable orchestration — September 1, 2026
Added atomic Postgres claim/complete/fail/lease-renew transitions, bounded deterministic retry
backoff, dead-letter handling (including final-attempt worker crashes), idempotent enqueue helpers
for capture and thought processing, an async worker runtime, Supabase-token authentication support,
and a user-scoped job diagnostics endpoint.

Verification:
- Required backend check passed: Ruff, strict MyPy, and 10 tests.
- Real Postgres tests covered concurrent claimers, duplicate enqueue, retry/dead-letter,
  lease-expiry recovery, final-attempt crash recovery, and cross-user diagnostics.
- Fresh Supabase reset, 13 pgTAP RLS assertions, and database advisors all passed.

### Issue #5 capture and interpretation — September 1, 2026
Added an idempotent authenticated capture API that commits raw evidence and its durable job in one
transaction, a structured OpenAI Agents SDK Thought Interpreter, provenance checks for source
fragments and literal temporal language, transactional zero/one/many thought persistence, and
user-scoped job and agent-run diagnostics. Traces exclude sensitive capture content while retaining
trace/correlation IDs and token usage.

Verification:
- Required backend checks passed: Ruff, strict MyPy, and 15 tests.
- Integration tests cover duplicate API retries, multi-thought persistence, tentative commitment,
  literal date preservation, invented-source rejection, and retryable model/schema failure without
  raw capture loss.
- A real OpenAI call correctly split two thoughts, kept tentative language at `possible`, and
  preserved `tomorrow morning` literally.
- The real interpreter worker path passed against local Postgres and OpenAI: capture, job, two
  thoughts, and agent run all reached `succeeded`, with trace metadata persisted.

### Issue #6 embeddings and continuity — September 1, 2026
Added asynchronous OpenAI embeddings with 1,536-dimensional pgvector persistence, deterministic
owner-scoped nearest-neighbor selection, a bounded structured Continuity Agent, strict candidate ID
validation, idempotent relationship writes, durable retries, and continuity agent-run telemetry.

Verification:
- Required backend checks passed: Ruff, strict MyPy, and 20 tests; all 13 pgTAP RLS assertions pass.
- Integration tests use real pgvector columns and cover bounded same-user search, cross-user
  exclusion, relevant/no-relation outcomes, duplicate graph writes, unsupplied-ID rejection, and
  semantic provider failure without thought loss.
- A real OpenAI/Postgres worker run generated two embeddings and persisted grounded `elaborates`
  and `continues` relationships; both Continuity Agent calls succeeded with stored trace IDs.

### Issue #7 deterministic retrieval — September 1, 2026
Added a code-only capacity retrieval engine with configurable weights, status/surface/snooze/time and
confidence-aware context filters, interpretable feature scoring, vector-plus-lexical near-duplicate
suppression, bounded kind diversity, idempotent retrieval IDs, and a one-reshuffle cap. Every
eligible candidate's score components are persisted for the development diagnostics endpoint.

Verification:
- Required backend checks passed: Ruff, strict MyPy, and 26 tests; all 13 pgTAP RLS assertions pass.
- Fixed-corpus tests cover repeatability, capacity eligibility, low-confidence non-filtering,
  near-duplicate suppression, diversity, fewer-than-three/no-result behavior, and reshuffle limits.
- Real Postgres API tests verify `a while` normalization, at-most-three cards, all-candidate score
  persistence, retry-stable responses, user scoping, first-set exclusion, and reshuffle-chain denial.

### Issue #9 resumption and sessions — September 1, 2026
Added a structured on-demand Resumption Agent restricted to the selected thought and up to three
persisted linked evidence records, with citation-ID validation and original raw text in the response.
Added idempotent session start/completion, retrieval actions, feedback events, all four wrap outcomes,
and an atomic spawned-thought flow that creates raw evidence, a user-grounded thought, a
`spawned_from` relationship, and downstream embedding work.

Verification:
- Required backend checks passed: Ruff, strict MyPy, and 33 tests; all 13 pgTAP RLS assertions pass.
- Tests cover grounded evidence loading, unsupplied-ID rejection, no-context degradation without a
  model call, done/partial/stopped state transitions, completion replay, and idempotent spawn graph.
- A real OpenAI/Postgres resumption run generated a concise summary using exactly the linked
  evidence ID, preserved the raw fragment, and persisted a succeeded agent run with trace metadata.

### Issue #10 mobile implementation — September 1, 2026
Built the Expo 57 / React Native 0.86 TypeScript vertical slice: invisible anonymous Supabase auth,
native SQLite capture queue, persistent document-directory voice recording, text sync and retry,
raw/multi-thought confirmation, capacity/context picker, at-most-three cards, grounded resumption,
session wrap outcomes, spawned capture handoff, and local/cloud diagnostics. The UI is intentionally
capture-first and contains no backlog, streak, overdue, or generic chat surfaces.

Verification:
- Expo Doctor passes all 21 checks; TypeScript, 3 local queue tests, and production web export pass.
- Playwright verified the first screen at 390x844 and 1440x900 with no overlap or blank rendering.
- Playwright restart smoke proves a text capture remains locally inspectable after backend failure.
- Native device/simulator verification remains blocked because this host has no Android SDK,
  emulator, attached device, or iOS runtime; Issue #10 stays open for that final checkbox.

### Issue #11 observability and eval gate — September 1, 2026
Added a versioned JSONL adversarial corpus and a real-agent eval runner for the Thought Interpreter
and Resumption Agent. The runner emits telemetry-only machine-readable results, exits nonzero on
any gate failure, and is wired to `make eval` after all backend checks. Tightened the Interpreter
prompt after the gate caught quoted-obligation commitment inflation and incomplete-fragment drift.

Verification:
- Required backend checks pass: Ruff, strict MyPy, and 34 tests.
- The live OpenAI eval passes all 10 cases: multi-thought, tentative and quoted commitments,
  explicit and ambiguous time, incomplete fragment, feeling, transcription noise, malformed
  structured output, and grounded resumption faithfulness.
- Deterministic retrieval tests cover stable ranking, eligibility, context confidence, capacity,
  near-duplicate suppression, diversity, reshuffle limits, and persisted score diagnostics.
- Cross-user debug tests prove job/agent-run metadata is owner-scoped and omits raw failure text.

### Issue #12 deployment and real-service smoke (in progress) — September 1, 2026
Added strict production credential validation, configurable Expo-web CORS, a `PORT`-aware server
entry point, a verified Docker image, and a Render Blueprint for the API. The selected zero-cost
demo topology runs that API on Render's free plan and the durable worker locally against hosted
Supabase. Added real anonymous-auth demo seed/reset, a full smoke runner,
machine-readable redacted evidence, worker-pause retention/recovery proof, and an exact operator
runbook. The integrated run caught and fixed pgvector `Vector` normalization in duplicate
suppression, now covered by a real-Postgres regression test.
The hosted rehearsal also exposed a dropped database connection that terminated the local worker
and intermittent bare `404 Not Found` responses from Render's free router. The worker polling
boundary now reconnects after transient failures, and the idempotent smoke client applies bounded,
visible retries only to transport/gateway failures and Render's distinguishable bare router 404.

Verification:
- Backend checks pass with Ruff, strict MyPy, and 42 tests; the Docker image serves `/health` on
  nondefault `PORT=9123`.
- `make demo-seed` and `make demo-reset` pass against local Supabase Auth/Postgres.
- The real local smoke passes twice consecutively: capture -> jobs -> real OpenAI agents -> pgvector
  -> deterministic retrieval -> grounded resumption -> session -> spawned thought -> RLS-visible
  feedback.
- With the worker paused, raw capture evidence and its queued job remain intact; restarting the
  worker recovers that same capture through real processing.
- `https://loose-thread-api.onrender.com/health` passes on the free deployed API.
- Two fresh hybrid smoke runs pass consecutively against the Render API and hosted Supabase while
  the local durable worker executes the real OpenAI pipeline. Redacted transcripts are retained in
  `e2e/results/hosted-smoke-1.txt` and `e2e/results/hosted-smoke-2.txt`.

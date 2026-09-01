# 29. Data model

The original single `thread_id` field is replaced by many-to-many relationships to avoid locking the product into a tree when human thought is a graph.

## 29.1 `captures`

```sql
id                    uuid primary key
user_id               uuid nullable
anonymous_device_id   uuid nullable
device_id              uuid
capture_mode           text check (...)
raw_text               text nullable
audio_url              text nullable
created_at             timestamptz not null
updated_at             timestamptz not null
transcription_status   text not null
processing_status      text not null
sync_version            bigint default 1
is_deleted             boolean default false
```

## 29.2 `thoughts`

```sql
id                    uuid primary key
capture_id            uuid not null references captures(id)
user_id               uuid nullable
client_created_at     timestamptz not null
created_at            timestamptz not null
updated_at            timestamptz not null
raw_fragment          text not null
refined_text          text not null
refined_source        text not null -- model_inferred | user_edited | user_raw
kind                  text not null
commitment_strength   text not null
surface_policy        text not null
duration_bucket       text not null
energy                text not null
contexts              text[] default '{}'
entities              jsonb default '{}'
temporal              jsonb default '{}'
open_loop             jsonb default '{}'
status                text not null default 'active'
last_surfaced_at      timestamptz nullable
surface_count         integer default 0
snooze_until          timestamptz nullable
embedding             vector nullable
enrichment            jsonb default '{}'
sync_version           bigint default 1
is_deleted             boolean default false
```

## 29.3 `thought_relationships`

```sql
id                    uuid primary key
user_id               uuid not null
from_thought_id       uuid not null
to_thought_id         uuid not null
relation_type         text not null
confidence            numeric nullable
source                text not null -- user | model | system
created_at            timestamptz not null
model_version         text nullable
unique(from_thought_id, to_thought_id, relation_type)
```

## 29.4 `threads`

```sql
id                    uuid primary key
user_id               uuid not null
title                  text nullable
summary                text nullable
summary_version        integer default 0
last_activity_at       timestamptz not null
status                 text default 'active'
created_at             timestamptz not null
updated_at             timestamptz not null
```

## 29.5 `thread_memberships`

```sql
thread_id              uuid not null
thought_id             uuid not null
confidence             numeric nullable
source                 text not null
created_at             timestamptz not null
primary key(thread_id, thought_id)
```

## 29.6 `sessions`

```sql
id                    uuid primary key
user_id               uuid not null
thought_id            uuid not null
retrieval_id          uuid nullable
window_minutes        integer nullable
window_label          text not null
started_at            timestamptz not null
ended_at              timestamptz nullable
outcome               text nullable
fit_feedback          text nullable
actual_minutes        integer nullable
created_at            timestamptz not null
```

## 29.7 `retrievals`

```sql
id                    uuid primary key
user_id               uuid not null
requested_at          timestamptz not null
window_label          text not null
contexts              jsonb default '{}'
candidate_count       integer
result_thought_ids    uuid[]
ranking_version       text not null
reshuffle_of          uuid nullable
```

## 29.8 `retrieval_impressions`

```sql
retrieval_id          uuid not null
thought_id            uuid not null
rank_position         integer not null
score                  numeric nullable
score_components      jsonb nullable
selected              boolean default false
action                text nullable
created_at            timestamptz not null
primary key(retrieval_id, thought_id)
```

## 29.9 `user_calibration`

Stores aggregate personalization values only after enough observations.

```sql
user_id               uuid primary key
duration_calibration  jsonb default '{}'
kind_affinity         jsonb default '{}'
context_affinity      jsonb default '{}'
updated_at            timestamptz not null
```

---

# 30. API/service contracts

Exact transport may use Supabase RPC/Edge Functions or a separate API, but product behavior should map to these logical operations.

## Capture

```text
POST /captures
POST /captures/{id}/audio
POST /captures/{id}/interpret
PATCH /thoughts/{id}
DELETE /thoughts/{id}
```

## Retrieval

```text
POST /retrievals
POST /retrievals/{id}/reshuffle
POST /retrievals/{id}/feedback
```

## Session

```text
POST /sessions
PATCH /sessions/{id}
POST /sessions/{id}/spawn
```

## Library

```text
GET /thoughts/search
GET /thoughts/{id}
GET /threads/{id}   -- v1.5 visible UI
```

## Account/data

```text
POST /identity/claim-anonymous
GET /export
DELETE /account-data
```

Every mutation must be idempotent where mobile retries are expected.

---

# 31. Analytics taxonomy

Analytics must measure product behavior without turning private thought text into analytics payloads.

Required events:

```text
app_opened
capture_started
capture_saved_local
capture_transcribed
capture_interpreted
capture_split
capture_edited
capture_deleted
retrieval_requested
retrieval_returned
retrieval_empty
retrieval_reshuffled
retrieval_none_selected
thought_surfaced
thought_started
thought_not_now
thought_archived
session_started
session_ended
session_fit_submitted
spawned_thought_created
library_opened
library_search
search_result_opened
sync_failed
sync_recovered
account_created
anonymous_data_claimed
```

Properties should use IDs, enum metadata, latency, and model/ranking versions—not raw capture text.

---

# 32. Metrics

## 32.1 North star

**Valued resumptions per weekly active user.**

Operational MVP proxy:

> **Acted sessions per active user per week**, target ≥4 among retained active users.

Longer-term, distinguish sessions that were merely started from sessions users actually considered useful.

## 32.2 Core metrics

- p95 app-open → record-ready: <3 seconds.
- local capture success: >99.9% in supported conditions.
- retrieval acceptance: target >40% after first-week cold start.
- “none of these” rate: <20% after sufficient corpus size.
- capture → retrieval ratio: monitor by cohort; investigate sustained >30:1.
- selected-card session start rate.
- session completion/partial rate.
- spawned-thought rate for resumption cards.
- day-7 and day-30 retention.
- percentage of active users using retrieval weekly.
- correction rate on commitment strength / temporal interpretation.
- model enrichment failure rate.

## 32.3 Guardrail metrics

- user-reported “felt guilty/judged” feedback,
- accidental commitment conversion rate,
- temporal hallucination rate,
- low-confidence fields used as hard filters,
- duplicate capture rate after sync/account migration,
- privacy/security incidents,
- deletion/export completion reliability.

## 32.4 Qualitative success signal

In interviews, resurfacing should produce delight, recognition, relief, or curiosity more often than shame.

Core interview question:

> “How did it feel when this came back?”

---

# 33. AI evaluation suite

No prompt/model change ships without offline evaluation.

## 33.1 Stage-1 interpretation evals

Minimum dataset categories:

- clean single thoughts,
- transcription noise,
- incomplete fragments,
- multiple thoughts in one capture,
- speculative language,
- explicit commitments,
- quoted commitments belonging to another person,
- questions,
- feelings,
- sarcasm,
- self-correction,
- date/time references,
- ambiguous date/time references,
- context-heavy actions,
- sensitive/private content,
- very short utterances.

Metrics:

- semantic preservation,
- invented commitment rate,
- thought-split precision/recall,
- kind accuracy,
- duration bucket accuracy,
- temporal extraction precision,
- temporal hallucination rate,
- open-loop precision/recall,
- schema validity.

**Hard launch blockers:**

- invented commitment rate above agreed threshold,
- materially unsafe temporal hallucination rate,
- frequent meaning-changing rewrites.

## 33.2 Retrieval evals

Create synthetic and user-consented test corpora containing 50–500 thoughts.

Test:

- duration compatibility,
- context compatibility,
- resurfacing fatigue,
- near-duplicate suppression,
- explicit temporal relevance,
- open-loop preference,
- no-results behavior,
- bounded diversity,
- deterministic reproducibility for fixed ranking version.

Human raters answer:

> “Would seeing this now be useful?”

and

> “Would any omitted candidate have been clearly better?”

## 33.3 Thread/resumption evals

Evaluate:

- relation precision,
- thread contamination rate,
- summary faithfulness,
- contradiction preservation,
- unsupported conclusion rate,
- usefulness for cognitive resumption.

---

# 34. Product experimentation

MVP experimentation should focus on the retrieval loop rather than decorative UX.

Priority experiments:

1. time-only picker vs time + optional context,
2. reasons on cards vs no reasons,
3. strict age curve vs suitability-first ranking,
4. different “Not now” cooldowns,
5. resumption context length,
6. experiential onboarding vs explanatory onboarding.

Do not A/B test shame, urgency, dark patterns, or notification pressure as growth tactics.

---

# 35. MVP scope

## v1 — MVP

Target remains approximately 4–6 weeks for an experienced solo builder only if design scope is tightly controlled.

Included:

- voice capture,
- text capture,
- local-first storage,
- anonymous capture identity,
- account creation/claim flow,
- transcription,
- stage-1 interpretation,
- explicit temporal extraction,
- commitment strength,
- open-loop detection,
- embeddings,
- lightweight background relationships,
- capacity picker,
- optional basic context filters,
- heuristic ranking,
- up-to-three retrieval cards,
- one reshuffle,
- session,
- wrap feedback,
- spawned-thought relationship,
- search/library,
- archive/delete/restore,
- offline sync,
- privacy/delete/export baseline,
- analytics,
- AI eval suite,
- degraded-state handling.

Visible thread management is not included.

## v1.5

- visible thread surfaces,
- thread summaries,
- gardening,
- richer duration recalibration,
- lock-screen/widget capture,
- optional carefully designed notification experiment,
- user-visible relationship context,
- advanced dormancy logic.

## v2

- calendar read-only context,
- watch capture,
- shared threads where privacy model supports it,
- “ask my past self” corpus query,
- learned personalized retrieval model,
- richer continuity graph,
- opt-in ambient context signals.

## Deliberately never / strong default no

- auto-writing work blocks into calendar,
- guilt-based overdue treatment,
- public productivity scores,
- streak pressure,
- mandatory project taxonomy,
- autonomous commitments created from model inference.

---

# 9. Duration and effort model

The original duration buckets contain literal gaps. MVP uses semantic bands with compatibility rules rather than pretending that human effort naturally falls into non-overlapping exact intervals.

## 9.1 User-facing buckets

| Bucket | Working interpretation | Typical examples |
|---|---|---|
| Spark | Usually a few minutes | send a message, book something, one quick lookup |
| Snack | Short focused block | read something, sketch an outline, one call |
| Session | Meaningful work block | draft, investigate, implement a small feature |
| Deep | Sustained focus | complex building, writing, analysis, planning |

## 9.2 Internal initial priors

These are priors, not promises:

```text
spark:   1–5 min
snack:   5–25 min
session: 20–75 min
deep:    60+ min
```

Overlap is intentional.

## 9.3 Retrieval compatibility

A candidate may fit a capacity window even if its nominal bucket is adjacent.

Initial compatibility matrix:

| User window | Eligible by default |
|---|---|
| 5 min | Spark |
| 15 min | Spark, Snack |
| 30 min | Snack, Session |
| 60 min | Snack, Session, low-boundary Deep |
| A while | Session, Deep |

The scoring layer then ranks for best fit.

## 9.4 Personal calibration

Personal calibration must operate at the level of feature patterns, not merely shift one global bucket boundary.

Useful future signals:

- user historically underestimates writing,
- calls usually take longer than model prior,
- phone actions complete faster,
- research tasks tend to expand,
- certain project/topic combinations have characteristic effort.

MVP only records outcome and uses conservative per-user bucket adjustments after sufficient samples.

---

# 10. Context model

Initial context tags:

```text
laptop
phone_ok
anywhere
home
out
needs_quiet
needs_other_person
low_energy_ok
```

Contexts are inferred only when reasonably supported.

Example:

> “Send Maya the screenshot.”

May infer `phone_ok`.

> “Fix the Docker networking bug.”

May infer `laptop`.

The model must not overfit. `anywhere` is preferable to an unsupported specific context.

User-declared context at retrieval overrides inferred assumptions.

---

# 11. Energy model

Energy is useful but must not become another mandatory planning field.

MVP design:

- Every thought may have inferred effort energy: `low`, `medium`, `high`, or `unknown`.
- Retrieval UI exposes one optional toggle: **Low energy**.
- The default window-picking flow does not require an energy choice.

If “Low energy” is selected, hard-filter only clearly incompatible high-energy candidates when confidence is high; otherwise use energy as a ranking preference.

This keeps the feature helpful without forcing users to introspect before every retrieval.

---

# 12. Thought lifecycle and state machine

## 12.1 Status values

```text
active
in_progress
done
archived
dormant
deleted
```

## 12.2 State transitions

```text
capture → active
active → in_progress          when session starts
in_progress → active          partial / abandoned without archival
in_progress → done            user marks completed
active → archived             “Done with this” / explicit let-go
active → dormant              dormancy policy
inactive states → active      explicit restore or successful gardening keep
dormant → archived            let go
dormant → active              keep / relevant new relationship
any non-deleted → deleted     user deletion
```

`done` means the user says the underlying action is complete.

`archived` means the user no longer wants ordinary resurfacing; it does not necessarily imply completion.

`dormant` is system-managed suppression and is reversible.

## 12.3 Dormancy policy

MVP begins with a simple policy, but it must not be only `created_at > 60 days`.

A thought is eligible for dormancy when all are true:

- active,
- no explicit future temporal constraint still relevant,
- not part of a recently active thread,
- no active session,
- no recent spawned relationship,
- last meaningful interaction exceeds threshold.

Initial threshold: 60 days.

Repeated “Not now” behavior may accelerate dormancy only after several occurrences. One dismissal must not be interpreted as disinterest.

---

# 13. Capture system

## 13.1 Capture modes

MVP:

- voice,
- text.

Post-MVP:

- share sheet,
- widgets,
- watch capture.

## 13.2 Capture record

A `capture` is created immediately before enrichment.

Required fields:

```text
id
user_or_device_id
created_at
capture_mode
raw_text nullable
audio_local_ref nullable
audio_remote_ref nullable
transcription_status
processing_status
source_app nullable
```

## 13.3 Non-blocking behavior

The following failures must not prevent the capture from being retained:

- network unavailable,
- cloud transcription unavailable,
- enrichment model timeout,
- malformed model response,
- embedding service unavailable,
- backend unavailable,
- account not yet created.

Local persistence is the first success condition.

## 13.4 Multi-thought capture

A single capture can produce multiple thoughts.

Example:

> “Ask Lina about the venue, and also I should look up whether Expo supports background audio.”

Expected result:

```json
{
  "thoughts": [
    {
      "refined_text": "Ask Lina about the venue.",
      "kind": "task"
    },
    {
      "refined_text": "Look up whether Expo supports background audio.",
      "kind": "research"
    }
  ]
}
```

The UI may show the split compactly but must not require approval unless confidence is low.

---

# 14. Immediate interpretation pipeline

Stage 1 runs after local capture and should usually complete quickly enough to support a short confirmation card, but the UI may fall back to the raw capture if processing is slow.

## 14.1 Responsibilities

Stage 1 may:

- clean transcription artifacts,
- preserve user vocabulary,
- split independent thoughts,
- infer kind,
- estimate duration bucket,
- estimate energy,
- infer contexts,
- extract entities,
- detect explicit temporal constraints,
- infer commitment strength,
- detect open loops,
- assign surface policy,
- generate field-level confidence.

Stage 1 must not:

- create new obligations,
- answer the user's question,
- rewrite emotional content into advice,
- add a deadline not explicitly stated,
- infer sensitive traits,
- create a project structure,
- summarize away incompleteness.

## 14.2 Output contract

```json
{
  "schema_version": "1.0",
  "thoughts": [
    {
      "refined_text": "string",
      "kind": "task|idea|question|research|unfinished|reminder|observation|reference|feeling",
      "commitment_strength": "none|curiosity|possible|intended|committed",
      "duration_bucket": "spark|snack|session|deep",
      "energy": "low|medium|high|unknown",
      "contexts": ["string"],
      "entities": {
        "people": [],
        "projects": [],
        "urls": [],
        "places": [],
        "topics": []
      },
      "temporal": {
        "literal": null,
        "type": null,
        "resolved_at": null,
        "source": null
      },
      "open_loop": {
        "is_open": false,
        "type": null
      },
      "surface_policy": "normal|resumption_only|search_only|never_proactive",
      "confidence": {
        "boundary": 0.0,
        "kind": 0.0,
        "commitment": 0.0,
        "duration": 0.0,
        "energy": 0.0,
        "contexts": 0.0,
        "temporal": 0.0,
        "open_loop": 0.0
      }
    }
  ]
}
```

## 14.3 Prompt requirements

The prompt must include explicit adversarial examples for:

- trailing-off fragments,
- pure feelings,
- rhetorical questions,
- tentative musings,
- two thoughts in one capture,
- explicit deadlines,
- ambiguous temporal language,
- statements quoting another person's obligation,
- sarcasm,
- self-correction,
- “maybe” and “I should” distinctions,
- raw transcription errors.

Model/provider names are implementation details and may change without product behavior changing.

---

# 15. Provenance and trust

Every model-derived value must be distinguishable from user-authored content.

Required provenance categories:

```text
user_raw
user_edited
model_inferred
system_derived
```

Rules:

1. Raw transcript/text is immutable after initial storage except deletion.
2. User edits create a new canonical presentation value but do not mutate raw source.
3. Model enrichment is versioned.
4. Re-enrichment never destroys previous enrichment metadata until migration is validated.
5. UI must provide a path to original capture from an expanded thought.
6. A user correction should be treated as higher-confidence evidence than model inference.

---

# 16. Background intelligence

## 16.1 Thread linking

MVP may compute lightweight relationships in the background but does not require a full visible thread browser.

Process:

1. generate embedding,
2. retrieve candidate semantic neighbours,
3. inspect candidate metadata and recency,
4. model or deterministic logic confirms relation,
5. store relationship with confidence and source.

No thought is forced into exactly one thread.

## 16.2 Thread summaries

In v1.5, active threads may receive a concise resumption summary such as:

> “You were trying to work out whether rejected recommendations should count as negative feedback, but noted that ‘not now’ and ‘not relevant’ are different signals.”

Rules:

- summaries must cite only captured thought content internally,
- do not invent conclusions,
- indicate uncertainty when the thread contains conflicting thoughts,
- update summaries incrementally when possible,
- preserve prior summary versions for debugging.

## 16.3 Open-loop updates

A later thought may close an earlier loop.

Example:

```text
Thought A: “Need to figure out why auth fails after refresh.”
Thought B: “Auth bug was the expired refresh token path.”
```

System may store `Thought B answers Thought A` and reduce open-loop status confidence for A.

MVP does not auto-mark the action done solely from semantic inference.

---

# 17. Retrieval system

Retrieval is the primary value delivery mechanism.

## 17.1 Input

Required:

- capacity window: `5`, `15`, `30`, `60`, `a while`.

Optional:

- `phone only`,
- `out`,
- `home`,
- `low energy`.

Future context may include device capability, time of day, calendar occupancy, or location category only with explicit user permission and clear product value.

## 17.2 Candidate hard filters

A thought is excluded when:

- `deleted`, `done`, `archived`, or `dormant`, unless explicitly requested,
- snoozed until a future time,
- surface policy excludes ordinary retrieval,
- explicit context is clearly incompatible,
- explicit temporal logic indicates it should not be surfaced yet,
- recently surfaced and not engaged, subject to fatigue policy.

Do not hard-filter based on low-confidence inferred metadata when doing so could hide a useful thought.

## 17.3 MVP ranking model

MVP uses interpretable heuristic scoring. Coefficients are configuration values, not permanent product truth.

Candidate features:

```text
rediscovery_value
capacity_fit
context_fit
open_loop_value
thread_momentum
personal_kind_affinity
explicit_temporal_relevance
novelty
surface_fatigue
recent_rejection_penalty
```

Illustrative score:

```text
score =
    0.22 * rediscovery_value
  + 0.20 * capacity_fit
  + 0.14 * context_fit
  + 0.14 * open_loop_value
  + 0.10 * thread_momentum
  + 0.08 * personal_kind_affinity
  + 0.07 * explicit_temporal_relevance
  + 0.05 * novelty
  - fatigue_penalty
  - rejection_penalty
```

Exact coefficients must be remotely configurable.

## 17.4 Rediscovery value

Age is useful but must not dominate suitability.

The original “staleness curve” concept becomes one feature: `rediscovery_value`.

A reasonable initial curve favors thoughts old enough to have left working memory while avoiding aggressively surfacing ancient low-value captures.

However, a new thought may still rank highly when:

- it has an explicit near-term temporal constraint,
- it directly continues a currently active thread,
- it fits the declared context exceptionally well,
- it represents a committed intention.

## 17.5 Diversity

“Three different kinds” is not a hard requirement because it can reduce quality.

MVP uses bounded diversity:

- avoid three near-duplicate candidates,
- prefer at least two semantic/behavioral categories when scores are close,
- allow three actionable items when they are materially better fits,
- avoid diversity for its own sake.

The desired user experience remains conversational rather than backlog-like.

## 17.6 No-results behavior

If fewer than three high-quality compatible thoughts exist:

- show fewer than three rather than knowingly bad recommendations,
- explain gently when constraints are narrow,
- offer to broaden context or time window,
- never fabricate a recommendation.

## 17.7 “None of these” behavior

The user may request one reshuffle.

After the reshuffle:

- do not enter an infinite recommendation loop,
- offer a neutral exit,
- log set rejection,
- do not treat each card as individually rejected unless the user explicitly rejected it.

---

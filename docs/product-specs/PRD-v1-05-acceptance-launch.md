# 36. MVP acceptance criteria

## Capture

- [ ] Fresh install can begin a capture within 3 seconds p95 after necessary permission flow has been completed.
- [ ] Offline voice/text capture persists locally.
- [ ] App restart does not lose an unsynced capture.
- [ ] A model outage never prevents local save.
- [ ] One capture may create multiple thoughts.
- [ ] Original capture remains inspectable.

## Interpretation

- [ ] Output validates against versioned schema.
- [ ] User speculation is not silently converted into a stronger commitment.
- [ ] Explicit temporal language is preserved verbatim.
- [ ] Low-confidence enrichment can degrade gracefully.
- [ ] User edits override presentation inference.

## Retrieval

- [ ] User can request retrieval using time alone.
- [ ] No more than three cards appear in a retrieval set.
- [ ] Fewer than three may appear if quality is insufficient.
- [ ] Incompatible hard-context items are excluded.
- [ ] Low-confidence context inference does not incorrectly hard-filter candidates.
- [ ] One reshuffle maximum is enforced.
- [ ] Ranking version and component scores are internally observable.

## Resumption/session

- [ ] Selecting unfinished/open-loop thought can show original context.
- [ ] “Spawned something new” creates a linked thought.
- [ ] Session can end as done, partial, or stopped without negative copy.
- [ ] Fit feedback is stored.

## Sync/account

- [ ] Anonymous captures survive account creation.
- [ ] Migration retry does not duplicate records.
- [ ] Multi-device edits obey conflict policy.
- [ ] Tombstoned deletion is not resurrected by an offline device.

## Privacy

- [ ] RLS tests prove users cannot read/write another user's records.
- [ ] Raw thought text is absent from standard analytics logs.
- [ ] Export works.
- [ ] Delete-all workflow is tested end-to-end.
- [ ] Audio retention matches published behavior.

---

# 37. Edge-case checklist

Engineering and QA must explicitly test:

- user records one word,
- user records silence,
- audio stops mid-sentence,
- user swears or uses slang,
- user says two unrelated thoughts,
- user says “don't remind me to…”,
- user quotes someone else's task,
- user says “maybe” repeatedly,
- user names a date without a year near year boundary,
- timezone changes after capture,
- daylight-saving transition,
- user edits thought while enrichment retry is pending,
- user deletes thought while offline then another device edits it,
- sync retries after account migration,
- same capture upload is retried multiple times,
- no compatible retrieval candidates,
- exactly one candidate,
- three semantically identical candidates,
- resurfaced item has an expired explicit date,
- user taps “Not now” repeatedly,
- app is killed during recording,
- low storage,
- microphone permission denied,
- transcription permission/API unavailable,
- backend/model provider outage,
- corrupted model response,
- embedding missing,
- user requests data deletion with unsynced local records.

---

# 38. Implementation epics

## Epic 1 — Local capture foundation

- app shell,
- microphone/text capture,
- local database,
- local IDs,
- offline queue,
- basic confirmation.

## Epic 2 — Identity and sync

- anonymous identity,
- auth,
- claim migration,
- Supabase schema/RLS,
- idempotent sync,
- conflict/tombstone behavior.

## Epic 3 — AI interpretation

- transcription abstraction,
- stage-1 schema,
- validation,
- fallback,
- enrichment persistence,
- prompt/eval harness.

## Epic 4 — Retrieval engine

- eligibility filters,
- score features,
- remotely configurable weights,
- diversity/dedup,
- retrieval logging,
- three-card UX.

## Epic 5 — Sessions and feedback

- start/resume,
- optional timer,
- wrap screen,
- outcome events,
- spawn relation.

## Epic 6 — Library

- search,
- thought detail,
- edit,
- archive/delete/restore,
- original capture view.

## Epic 7 — Relationships and resumption

- embeddings,
- neighbour discovery,
- lightweight relation confirmation,
- open-loop context presentation.

## Epic 8 — Privacy and reliability

- retention jobs,
- export/delete,
- logging rules,
- provider controls,
- failure states,
- observability.

## Epic 9 — Analytics and launch readiness

- event taxonomy,
- dashboards,
- cohort metrics,
- AI eval gates,
- crash/performance monitoring,
- beta feedback instrumentation.

---

# 39. Launch plan

## Internal alpha

Goal: validate correctness and trust.

Test with seeded/adversarial thought corpora and a very small internal cohort.

Exit conditions:

- capture reliability acceptable,
- commitment-preservation eval passes,
- sync migration stable,
- retrieval can be debugged from feature scores,
- deletion/export verified.

## Closed beta

Goal: validate habit loop and emotional response.

Ideal cohort: 20–50 people matching primary user profile.

Primary research questions:

- Do they naturally capture without being prompted?
- Do they return to retrieval?
- Do surfaced thoughts feel useful or guilt-inducing?
- Are three options enough?
- Does time-only retrieval feel natural?
- Do resumption cards actually restore mental context?
- Which kinds should never surface?

## Wider beta

Goal: evaluate retention, ranking calibration, and scale economics.

Do not add major productivity features to compensate for weak retrieval. If retrieval does not land, fix retrieval.

---

# 40. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Transcription fails on fast/mumbled speech | Preserve source; local save; one-tap edit; cloud/on-device fallback strategy. |
| Model rewrites intent | Commitment field, hard prompt rules, provenance, regression evals. |
| Explicit dates are lost | Temporal extraction with literal preservation. |
| Duration estimates are poor | Semantic buckets, overlapping priors, outcome calibration. |
| Retrieval feels random | Interpretable ranking, feature logging, human eval, feedback semantics. |
| Retrieval becomes a disguised to-do list | Bounded diversity, open-loop/resumption support, copy discipline. |
| Backlog becomes graveyard | Dormancy + v1.5 gardening + no counts. |
| User captures but never retrieves | Cohort metrics and qualitative research; improve retrieval value before adding pressure. |
| Thread linking contaminates context | Many-to-many confidence, relation evals, summary faithfulness tests. |
| Anonymous→account migration loses data | Local IDs, idempotent claim process, retry-safe sync. |
| Offline conflicts resurrect deleted items | Tombstones and explicit state event policy. |
| Sensitive data leaks through logs | Content-free analytics, redacted observability, access controls. |
| Model provider policy conflicts with privacy promise | Provider abstraction and contractual/configuration review. |
| AI cost grows | Cheap interpretation path, deterministic retrieval, batch background work, usage telemetry. |
| Product expands into generic productivity app | Product principles treated as launch gates. |

---

# 41. Decisions resolved from v0.1

The following ambiguities are resolved in this version:

1. **Thread linking exists lightly in MVP; full visible thread UI moves to v1.5.**
2. **A capture may return multiple thought records.**
3. **Duration buckets use overlapping semantic priors rather than literal gap-filled ranges.**
4. **Explicit user-stated temporal constraints are preserved and may influence retrieval.**
5. **Raw transcript/text is retained; server audio defaults to temporary retention rather than contradictory permanent retention.**
6. **MVP retrieval is interpretable heuristic ranking, not a falsely precise permanent score formula.**
7. **Per-thought acceptance rate is removed as a core feature.**
8. **Rediscovery age and action suitability are separate ranking concepts.**
9. **Diversity is a bounded preference, not a rigid one-kind-each rule.**
10. **Anonymous-to-account migration is explicitly specified.**
11. **Local-first conflict behavior and tombstones are required.**
12. **Feelings default to search-only in MVP unless product logic explicitly promotes them.**
13. **AI and infrastructure failure states are defined.**
14. **Open loops are first-class product metadata.**
15. **Thought relationships are graph-like and many-to-many.**
16. **Commitment strength is explicitly modeled.**
17. **Retrieval learning signals distinguish “not now” from dislike.**

---

# 42. Remaining product questions

These questions do not block MVP engineering unless marked otherwise.

## High priority before closed beta

1. Should `5 / 15 / 30 / 60 / a while` remain the exact capacity choices after usability testing?
2. Should the user see the inferred bucket on every capture confirmation or only when it adds value?
3. What is the ideal default snooze for “Not now”: 24 hours, contextual, or adaptive?
4. Does first retrieval truly require account creation, or can local-only retrieval precede signup?
5. Should low-confidence thought splitting require confirmation?
6. What minimum linked context makes a resumption summary more useful than simply showing the original thought?

## Post-MVP research

7. Can calendar read-only context improve retrieval without changing the pull-based philosophy?
8. Is “something old” a useful explicit retrieval mode?
9. Is “surprise me” meaningfully different from ordinary retrieval?
10. Do users want manual relationship correction when thread linking is wrong?
11. Should dormant thoughts be discoverable by semantic search by default? Recommended: yes.
12. Can on-device models eventually handle enough interpretation to improve privacy and offline quality?

---

# 43. Launch success criteria

The MVP should not be considered successful merely because capture works.

A successful early product demonstrates all of the following:

1. Users capture without needing to learn a filing system.
2. Users voluntarily invoke retrieval repeatedly.
3. At least a meaningful plurality of retrieval sets produce an accepted card.
4. Users report that resurfacing feels like useful rediscovery, not backlog guilt.
5. Resumption cards help users continue thinking rather than merely remind them that a thought existed.
6. AI mistakes are recoverable and do not silently change user intent.
7. Offline capture and sync are trusted.
8. The team can explain why a card was eligible and approximately why it ranked.
9. Privacy promises match actual technical behavior.
10. The product remains recognizably simpler than a task manager after real-world feedback.

---

# 44. Product north star

Loose Thread should increasingly understand three things without making the user manage them:

```text
WHAT DID YOU MEAN?
        +
WHAT IS STILL OPEN?
        +
WHAT IS USEFUL TO RETURN TO NOW?
```

The product wins when it can restore continuity without becoming another system the user has to maintain.

The long-term moat is therefore not a giant feature set. It is an increasingly personal, evidence-based retrieval policy and continuity graph built from the user's own history while preserving the trust that made them willing to capture unfiltered thoughts in the first place.

> **Capture without organizing. Return without searching. Resume without rebuilding the context from scratch.**

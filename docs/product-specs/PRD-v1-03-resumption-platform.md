# 18. Behavioral feedback semantics

Feedback is not binary.

| User action | Meaning for ranking |
|---|---|
| Start | Strong positive selection signal |
| Completed | Positive usefulness + outcome signal |
| Partial | Positive selection; ambiguous fit/outcome |
| Abandoned | Weak negative for fit; do not assume thought is unwanted |
| Not now | Temporary context mismatch, not global dislike |
| Done with this | Strong suppression signal |
| None of these | Negative for the batch/context combination |
| Too short | Duration estimate correction |
| Right | Duration confirmation |
| Too long | Duration estimate correction |
| Spawned thought | Strong resumption/continuity signal |
| Opened context only | Weak interest/resumption signal |
| Search result opened | Retrieval usefulness signal separate from recommendation ranking |

MVP stores these events even if only a subset affects ranking initially.

Per-thought `accept_rate` is not used as a core ranking feature because most individual thoughts will not accumulate enough impressions. Personalization should operate across feature patterns and user history.

---

# 19. Resumption experience

A resumption card is not a task card with different copy.

For a high-confidence open loop or `unfinished` thought, the expanded experience may include:

1. current refined text,
2. original raw fragment,
3. concise “where you got to” summary if enough linked context exists,
4. up to three highly relevant linked thoughts,
5. one-tap capture to continue the thread.

No completion checkbox is required for a purely cognitive open loop.

Possible CTA labels:

- **Pick this back up**
- **Continue thinking**
- **Add to this**

The eventual outcome may be another thought rather than completion.

---

# 20. Personalization

## 20.1 MVP

MVP personalization uses deterministic aggregates after minimum sample thresholds.

Examples:

- preferred kinds by time of day,
- duration correction by bucket,
- context-specific completion rates,
- repeated rejection patterns,
- resurfacing fatigue.

No learned model is required to launch.

## 20.2 Future personalized retrieval policy

After sufficient interaction, the system may estimate:

> `P(user values seeing thought X | current context C)`

Candidate feature families:

- capacity window,
- energy/context,
- time of day/day of week,
- thought age,
- type,
- effort prior,
- commitment strength,
- temporal constraint,
- open-loop status,
- thread activity,
- prior impressions,
- prior outcomes,
- user-specific duration patterns,
- semantic relation to recently active work.

Training must avoid interpreting private content beyond what is necessary for user-serving personalization and must comply with explicit privacy commitments.

---

# 21. Anonymous use, identity, and account migration

The original onboarding requires no account for capture and an account at first retrieval. This introduces an important state transition that must be defined.

## 21.1 Anonymous device identity

On first launch, create:

```text
anonymous_device_id
local_encryption_key
installation_created_at
```

Captures are stored locally under this identity.

## 21.2 First retrieval

MVP may require account creation before cloud-backed retrieval if necessary for synchronization and server-side processing.

Account creation must:

1. create authenticated user,
2. claim eligible anonymous local records,
3. upload them idempotently,
4. preserve original local IDs as client IDs,
5. avoid duplicates if migration is retried,
6. retain capture functionality even if account creation fails.

## 21.3 Multiple devices

After authentication:

- server user ID is authoritative identity,
- local records use stable UUIDs generated client-side,
- sync is idempotent,
- remote and local versions include modification metadata.

---

# 22. Local-first sync

Offline capture is non-negotiable.

## 22.1 Requirements

Every mutable record includes:

```text
id
client_created_at
server_created_at nullable
updated_at
sync_version
sync_status
is_deleted
device_id
```

## 22.2 Conflict policy

General rule:

- raw capture fields are append-only/immutable,
- user edits to refined text use last explicit user edit unless conflict cannot be safely resolved,
- status transitions use ordered event logs rather than blind last-write-wins where possible,
- deletion creates a tombstone,
- AI enrichment never overwrites a newer user edit.

## 22.3 Retry policy

Sync uses exponential backoff with jitter and resumes automatically.

The UI does not show technical sync errors unless user action is required. A subtle “saved on this device” state is sufficient when offline.

---

# 23. Privacy, security, and retention

Loose Thread may contain highly sensitive unfiltered speech. Privacy claims must be technically precise.

## 23.1 Required commitments

- encrypted in transit,
- encrypted at rest on backend infrastructure,
- local storage protected using platform-appropriate secure storage/encryption strategy,
- Row Level Security on every user-owned table,
- no user content used to train shared/general models unless separately and explicitly opted in,
- one-tap export,
- one-tap account/content deletion,
- model providers configured for the strongest available no-training/data-retention terms appropriate to the product,
- minimum necessary logging of raw content,
- redaction of content from ordinary application logs.

## 23.2 Audio retention

The previous spec conflicted between “always preserve raw audio” and “delete audio after 30 days.”

Resolved policy for MVP:

- raw **transcript/text** is retained until user deletion,
- raw **audio** is retained only when needed for transcription/recovery,
- default server audio retention: up to 30 days,
- user may delete audio immediately,
- after audio deletion, transcript remains available,
- retention policy is disclosed in-product,
- local audio may be deleted after successful transcription/sync according to platform storage policy.

If later user research shows permanent audio retention is important, it should be opt-in rather than assumed.

## 23.3 Deletion semantics

“Delete everything” must:

1. delete or tombstone user records from active databases,
2. queue deletion of audio/object storage,
3. invalidate embeddings and derived summaries,
4. remove account-linked analytics identifiers where legally/product appropriate,
5. follow documented backup expiration procedures,
6. provide confirmation when deletion has been initiated/completed according to architecture.

## 23.4 Sensitive inference

The enrichment system must not infer protected or highly sensitive personal traits that the user did not explicitly ask the product to model.

---

# 24. UX specification

## Screen 0 — First-use capture

Preferred onboarding is experiential rather than explanatory.

Initial prompt:

> **What’s something you don’t want to lose?**

Primary control: mic.

After first capture:

> “That’s basically it. Loose Thread keeps things like this and brings them back when you have room for them.”

Mic permission should be requested immediately adjacent to an understandable user action, not as a detached permissions tutorial.

## Screen 1 — Capture / home

Requirements:

- app launch lands here,
- record control usable within p95 <3 seconds,
- tap-to-toggle and press/hold interaction supported if technically reliable,
- keyboard affordance available,
- recent captures shown only as lightweight proof of capture, not as a task feed,
- no backlog count,
- no productivity dashboard.

States:

- idle,
- recording,
- transcription processing,
- saved locally/offline,
- enrichment pending,
- permission denied,
- microphone unavailable.

## Screen 2 — Confirmation

Default auto-dismiss around 2 seconds.

Shows:

- refined text or raw fallback,
- bucket chip if confidence acceptable,
- edit,
- undo/delete.

If model split one capture into multiple thoughts, confirmation may show compact stacked items.

If enrichment fails, show saved raw text/transcript without an error-heavy experience.

## Screen 3 — Capacity picker

Primary chips:

`5` · `15` · `30` · `60` · `a while`

Optional context controls:

- phone only,
- out,
- home,
- low energy.

The screen should be usable with time alone.

## Screen 4 — Three options

Up to three cards.

Each includes:

- refined thought,
- bucket,
- one short reason for resurfacing when useful,
- subtle origin/time context.

Actions:

- **Start** / **Pick this back up** depending on thought,
- **Not now**,
- **Done with this**.

Footer:

- **None of these** → one reshuffle maximum.

Do not display rank scores or AI confidence.

## Screen 5 — Session

Contains:

- selected thought,
- relevant context,
- optional timer initialized from chosen window,
- simple capture affordance,
- no unrelated feed.

Timer is optional and must never imply failure when exceeded.

## Screen 6 — Wrap

Two lightweight inputs:

**Did it fit?**

- shorter than expected,
- about right,
- longer than expected.

**Where did you land?**

- done,
- partial,
- stopped,
- spawned something new.

“Spawned something new” immediately opens capture and stores `spawned_from` relation.

## Screen 7 — Library

Available within two deliberate taps from capture.

Functions:

- search,
- recent thoughts,
- active/dormant filtering,
- expanded thought view,
- editing,
- delete/archive/restore.

No default total count.

Thread browser is v1.5.

## Screen 8 — Gardening (v1.5)

Opt-in only.

One dormant thought at a time:

- **Keep**
- **Let go**

Never show “47 items left.”

---

# 25. Failure and degraded states

Capture must remain trustworthy when infrastructure fails.

| Failure | User experience | System behavior |
|---|---|---|
| No network | “Saved on this device.” | Queue sync/enrichment. |
| Transcription failure | Preserve audio; offer simple edit/retry. | Mark transcription pending/failed. |
| Enrichment timeout | Show raw transcript. | Retry asynchronously. |
| Invalid model JSON | No user-facing model error. | Store raw; retry with validation/repair path. |
| Embedding failure | Thought still available in library. | Retry; exclude relationship-dependent features. |
| Backend unavailable | Capture works locally. | Sync later. |
| Account creation fails | Capture remains available. | Do not strand local data. |
| Retrieval service fails | Offer library search or retry. | Never return fabricated cards. |
| Insufficient candidates | Show 1–2 good matches. | Do not pad with low-quality results. |

---

# 26. Copy and tone

Voice: a thoughtful friend who took notes and is handing one back. Not a coach, manager, therapist, or productivity system.

| Never | Instead |
|---|---|
| “Overdue” | “You mentioned wanting to do this before Friday.” |
| “3 days late” | “From last week.” |
| “You haven’t done this” | “You wanted to come back to this.” |
| “Task completed 🔥 streak 4” | “Nice.” |
| “Backlog: 47” | No count. |
| “Are you sure you want to delete?” | “Let this one go?” |
| “AI recommends…” | Usually omit AI framing. |

Avoid generalized neurological claims in user-facing copy unless evidence and review justify them.

---

# 27. Accessibility

MVP requirements:

- VoiceOver/TalkBack labels for all controls.
- Touch targets meet platform minimums.
- Recording state conveyed through more than color.
- No meaning relies solely on animation.
- Reduced motion respected.
- Text capture is a first-class alternative to voice.
- Dynamic text sizing supported without clipping core controls.
- High contrast tested in light/dark themes if both themes ship.
- Haptic feedback is optional and never required to understand state.
- Session timer is screen-reader compatible.

---

# 28. Technical architecture

## 28.1 Client

Recommended:

- React Native,
- Expo where practical,
- `expo-sqlite` or equivalent SQLite layer,
- secure platform key storage,
- local event queue,
- background sync within platform limits.

## 28.2 Backend

Recommended:

- Supabase Auth,
- Postgres,
- pgvector,
- object storage for temporary audio,
- Row Level Security,
- Edge Functions or equivalent server functions,
- scheduled jobs for background enrichment/dormancy.

Architecture must not depend on a single model vendor.

## 28.3 AI services

Logical components:

1. transcription provider,
2. stage-1 interpretation model,
3. embeddings provider,
4. relationship/thread confirmation model,
5. thread-summary model,
6. retrieval service.

Providers may be consolidated initially.

All model calls require:

- schema validation,
- timeout,
- retries with cap,
- model/version logging,
- token/cost logging without unnecessary raw-content logs,
- request correlation ID,
- graceful fallback.

## 28.4 Retrieval architecture

Do not pass the full active corpus to a large language model for every retrieval as the default architecture.

MVP preferred path:

```text
SQL hard filters
    ↓
feature calculation
    ↓
heuristic ranking
    ↓
semantic dedup/diversity
    ↓
return up to 3
```

An LLM may be used for concise explanation text or special ambiguity resolution, but retrieval quality should be inspectable and testable without opaque end-to-end generation.

This keeps latency, cost, privacy exposure, and debugging risk lower.

---

# Loose Thread — Product Requirements Document

*Working name. Alternatives: Unfinished, Sidequest, Thread, Half-Thought.*

**Version:** 1.0 — Build-Ready Product Specification  
**Owner:** Blessed  
**Status:** Approved for MVP implementation planning  
**Primary platforms:** iOS and Android via React Native / Expo  
**Product category:** Personal cognitive continuity / thought resumption  

---

## 0. Executive summary

Loose Thread is an ambient cognitive continuity system for people who generate thoughts, intentions, questions, ideas, and unfinished mental fragments faster than they can organize them.

The product has one core promise:

> **Capture with almost no friction. Organize invisibly. Resurface only what is useful when the user has capacity to engage with it.**

Loose Thread is not a conventional task manager, notes app, productivity coach, calendar, or generic AI assistant. It is designed around a specific failure pattern: users often lose important thoughts because capture tools demand organization at the moment of capture, and they later fail to retrieve those thoughts because traditional systems return long undifferentiated lists.

The product therefore follows a pull-based loop:

```text
CAPTURE
  ↓
UNDERSTAND
  ↓
STORE
  ↓
USER DECLARES CAPACITY
  ↓
SURFACE THREE OPTIONS
  ↓
RESUME / ACT
  ↓
CAPTURE OUTCOME
  ↓
LEARN
```

The long-term product advantage is not merely better duration estimation. It is a personalized model of what a user is likely to value seeing again in a given context, built from their own historical captures, retrieval choices, session outcomes, timing patterns, and thought relationships.

MVP success is demonstrated when users repeatedly experience the reaction:

> **“Oh — yes. I forgot about that.”**

with curiosity or relief rather than guilt.

---

# 1. Problem

Most capture tools require users to create structure before the thought is safely stored. The user may need to decide whether the thought is a task, note, project item, reminder, calendar event, bookmark, or idea. They may also be asked to assign tags, priority, date, folder, project, or status.

That organizational work occurs at exactly the moment the user is trying not to lose the thought.

For people with high idea-generation rates, fragmented attention, executive-function challenges, frequent interruptions, or low tolerance for administrative overhead, the cost of organizing a thought can exceed the perceived value of capturing it.

The second problem is retrieval.

Traditional tools usually answer:

> “What have I saved?”

with a list.

A list of dozens or hundreds of items transfers the organization problem from capture time to retrieval time. The user must search, prioritize, estimate effort, remember context, and choose what matters now.

Loose Thread instead answers:

> **“Given the capacity I have right now, what are a few things worth returning to?”**

A third and less-served problem is cognitive resumption. People frequently remember the existence of a project or idea but lose the mental state that made it meaningful:

- what question they were answering,
- what hypothesis they were forming,
- what decision was unresolved,
- what contradiction they noticed,
- what they had already ruled out,
- what the next thread of thought was.

Loose Thread must preserve and reconstruct this continuity without pretending that every fragment is a task.

---

# 2. Product thesis

## 2.1 Core insight

> **Zero structure in. Structure applied in the background. Retrieval indexed by the capacity the user actually has now.**

The user should not need to classify a thought in order to save it.

The system may infer structure, but inference is subordinate to the original capture. The system must never silently convert speculation into obligation, uncertainty into certainty, or curiosity into a task.

## 2.2 Category definition

Externally, early positioning may focus on thought capture and ADHD-friendly retrieval because the pain is acute and legible.

Internally, the product should be designed as:

> **A personal cognitive continuity system that captures fragments of intention and thought without demanding organization, reconstructs their context over time, and resurfaces useful unfinished mental state when the user has capacity to engage with it.**

This broader architecture supports future use by founders, researchers, writers, engineers, students, creators, executives, and other high-context knowledge workers without weakening the initial wedge.

## 2.3 What Loose Thread is not

Loose Thread is deliberately not:

- a full project-management system,
- a calendar scheduler,
- a habit tracker,
- a streak product,
- a goal-coaching app,
- a knowledge-base dashboard,
- a generic AI chatbot,
- a notes app with automatic tags,
- a system that tries to maximize user output.

The goal is continuity, not optimization theater.

---

# 3. Target users and jobs to be done

## 3.1 Primary user

Adults who identify with ADHD-related executive-function challenges and already attempt to capture thoughts in tools such as voice memos, Notes, reminders, messaging themselves, or loosely organized Notion pages, but consistently fail at retrieval.

Common characteristics:

- high thought and idea generation,
- frequent context switching,
- aversion to categorization overhead,
- inconsistent use of conventional task systems,
- large collections of notes they rarely revisit,
- difficulty restarting interrupted thinking,
- strong negative reaction to backlog guilt.

The product must not require a diagnosis and must not make medical claims.

## 3.2 Secondary users

- founders,
- researchers,
- writers,
- software engineers,
- product/design professionals,
- students,
- creators,
- executives,
- anyone with high idea generation and low tolerance for capture administration.

## 3.3 Core jobs to be done

1. **Capture:** “Get this out of my head before I lose it without breaking what I am doing.”
2. **Selection:** “I have a small window of time and do not want to decide from a giant list. Give me a few worthwhile options.”
3. **Rediscovery:** “There was something I wanted to look into, but I cannot remember what it was.”
4. **Resumption:** “I was in the middle of thinking something through and got pulled away. Help me get back to where my mind was.”
5. **Release:** “Let old thoughts disappear without making me feel like I failed.”

Job 4 is the strongest long-term differentiator.

---

# 4. Product principles

These are constraints, not aspirations.

| # | Principle | Product consequence |
|---|---|---|
| 1 | **Capture must be under 3 seconds to recording.** | App opens directly to capture. No dashboard or feed before the mic. |
| 2 | **Never require structure at capture.** | Projects, tags, priorities, and folders are never mandatory. |
| 3 | **Never show the full list by default.** | Library is available but is not the default operating model. |
| 4 | **Three options, never more per retrieval set.** | Retrieval reduces decision burden instead of relocating it. |
| 5 | **The app only speaks when spoken to in MVP.** | No push notifications, badge pressure, or streaks in v1. |
| 6 | **Never shame.** | No overdue language, red failure states, backlog counts, or productivity grading. |
| 7 | **Never invent a commitment.** | A musing remains a musing; a question remains a question. |
| 8 | **Never erase an explicit commitment or constraint.** | If the user says “before Friday,” that information is preserved. |
| 9 | **Original meaning outranks model polish.** | Raw capture is immutable and inspectable. |
| 10 | **Thoughts are allowed to die.** | Dormancy and letting go are product features. |
| 11 | **AI failure must not block capture.** | Storage succeeds even if transcription, enrichment, embeddings, or sync fail. |
| 12 | **Intelligence should feel quiet.** | Avoid generic chat interfaces and unnecessary AI explanation. |
| 13 | **Personalization must be earned from behavior.** | The system starts heuristic and learns from real outcomes. |
| 14 | **Privacy is part of the product experience.** | Sensitive captures require explicit retention, deletion, and provider policies. |

---

# 5. Core loop

## 5.1 Capture loop

```text
User opens app
    ↓
Mic immediately available
    ↓
Voice / text / share capture
    ↓
Local write succeeds first
    ↓
Optional transcription
    ↓
Immediate interpretation
    ↓
Short confirmation
    ↓
Return to capture state
```

The user does not need to wait for AI processing to finish before leaving the app.

## 5.2 Retrieval loop

```text
User asks for something to return to
    ↓
Declares available time
    ↓
Optionally declares situational constraints
    ↓
Hard-filter incompatible thoughts
    ↓
Rank candidates
    ↓
Select three with bounded diversity
    ↓
User starts / postpones / lets go / rejects set
```

## 5.3 Resumption loop

```text
User selects unfinished thought
    ↓
Restore original wording
    ↓
Show concise thread context if useful
    ↓
User continues thinking or acting
    ↓
New capture may be spawned
    ↓
Relationship stored
```

## 5.4 Learning loop

Every meaningful retrieval interaction produces behavior data. The system may use this to improve ranking but must not infer user motivation beyond evidence.

---

# 6. Core concepts

## 6.1 Thought

A single captured unit of user meaning.

A thought may be:

- actionable,
- speculative,
- factual,
- emotional,
- incomplete,
- a question,
- a reminder,
- a reference,
- a commitment,
- or some combination of these.

`Thought` is the storage primitive. Classification is metadata, not identity.

## 6.2 Capture

The original input event that produced one or more thoughts. A single spoken capture can legitimately contain multiple independent thoughts.

This distinction is important because one audio clip may split into two or more thought records while preserving one common source.

## 6.3 Open loop

An unresolved cognitive state that may be useful to resume.

Examples:

- unanswered question,
- unresolved decision,
- incomplete explanation,
- unfinished idea,
- implementation blocker,
- promised follow-up,
- research gap,
- conversation continuation.

Open-loop detection is separate from `kind`. A research thought may or may not be open; an idea may or may not be open.

## 6.4 Thread

A system-created grouping representing an evolving line of thought or activity.

Threads are emergent and invisible or lightly surfaced in MVP. Users do not need to manually create or manage them.

## 6.5 Relationship

A directional or undirected relationship between thoughts and/or threads.

Initial supported relation types:

- `continues`
- `elaborates`
- `answers`
- `contradicts`
- `references`
- `spawned_from`
- `same_topic`
- `same_person`
- `same_project`

## 6.6 Capacity window

A user-declared amount of available time used for retrieval.

## 6.7 Session

A period in which the user chooses to engage with a surfaced thought.

## 6.8 Dormant thought

A thought excluded from ordinary retrieval because it has become stale, repeatedly ignored, explicitly deferred for a long period, or otherwise appears low-value for active resurfacing.

Dormancy is reversible and is not equivalent to deletion.

---

# 7. Thought meaning model

Loose Thread must preserve distinctions that conventional task systems flatten.

## 7.1 `kind`

Initial values:

```text
task
idea
question
research
unfinished
reminder
observation
reference
feeling
```

`kind` is best-effort semantic metadata. It does not determine whether something is shown.

## 7.2 Commitment strength

The system must explicitly model whether the user expressed an obligation.

```text
none
curiosity
possible
intended
committed
```

Examples:

| User statement | Commitment strength |
|---|---|
| “I wonder whether Rust would be useful here.” | curiosity |
| “Maybe I could learn some Rust.” | possible |
| “I want to learn Rust.” | intended |
| “I told Sarah I would send the Rust prototype Friday.” | committed |

The system must never raise commitment strength beyond what the source supports.

## 7.3 Surface policy

Some thoughts should be captured but not normally returned as actionable recommendations.

```text
normal
resumption_only
search_only
never_proactive
```

Default examples:

- `feeling` → `search_only` in MVP unless attached to an open loop.
- pure reference material → `search_only`.
- unfinished thought → `resumption_only` or `normal` depending on confidence.

This resolves the ambiguity of whether every captured `kind` should participate in retrieval.

## 7.4 Confidence

Every inferred field produced by AI must include confidence where uncertainty can materially change behavior.

Required confidence fields in MVP:

- thought boundary / split confidence,
- kind confidence,
- commitment confidence,
- duration confidence,
- temporal parsing confidence,
- context confidence,
- open-loop confidence.

Low confidence must reduce behavioral consequences, not merely be logged.

---

# 8. Temporal model

Loose Thread never asks users to assign deadlines during normal capture. It does, however, preserve explicit temporal information already present in the capture.

Example:

> “Remember to cancel that subscription before Friday.”

The system may store:

```text
temporal_expression: "before Friday"
temporal_type: deadline
temporal_at: resolved timestamp if safely resolvable
temporal_source: explicit_user_statement
temporal_confidence: 0.96
```

Supported temporal types:

```text
deadline
not_before
appointment_reference
relative_time
recurrence_mentioned
unknown
```

Rules:

1. Never invent a date.
2. Never transform vague language into false precision.
3. Preserve the literal temporal phrase even when resolution succeeds.
4. If a date is ambiguous, preserve the expression and leave the normalized timestamp null.
5. Passing a user-stated date does not create an “overdue” state.
6. Retrieval may use explicit temporal relevance as a ranking signal.
7. Copy must describe what the user said rather than accuse them of lateness.

Example after the date passes:

> “You mentioned wanting to do this before Friday.”

Not:

> “3 days overdue.”

---

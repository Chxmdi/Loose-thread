from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import UUID

from loose_thread_api.models.retrievals import RetrievalContexts, WindowLabel
from loose_thread_api.retrieval.engine import RetrievalCandidate, RetrievalEngine

NOW = datetime(2026, 9, 1, 16, 0, tzinfo=UTC)


def candidate(
    index: int,
    *,
    text: str | None = None,
    kind: str = "task",
    duration: str = "snack",
    energy: str = "medium",
    contexts: list[str] | None = None,
    context_confidence: float = 0.9,
    energy_confidence: float = 0.9,
    status: str = "active",
    surface_policy: str = "normal",
    embedding: list[float] | None = None,
    score_age_days: int = 14,
) -> RetrievalCandidate:
    return RetrievalCandidate(
        id=UUID(f"00000000-0000-4000-8000-{index:012d}"),
        refined_text=text or f"Thought {index}",
        kind=kind,
        commitment_strength="intended",
        duration_bucket=duration,
        energy=energy,
        contexts=contexts or ["anywhere"],
        temporal={},
        open_loop={"is_open": True},
        confidence={"contexts": context_confidence, "energy": energy_confidence},
        status=status,
        surface_policy=surface_policy,
        last_surfaced_at=None,
        surface_count=0,
        snooze_until=None,
        embedding=embedding,
        created_at=NOW - timedelta(days=score_age_days),
        relationship_count=0,
        kind_affinity=0.5,
        recent_rejections=0,
    )


def test_fixed_corpus_is_deterministic_and_capacity_eligible() -> None:
    engine = RetrievalEngine()
    corpus = [
        candidate(1, duration="spark"),
        candidate(2, duration="snack"),
        candidate(3, duration="session"),
        candidate(4, duration="deep"),
    ]
    first_ranked, first_selected = engine.rank(
        corpus,
        window=WindowLabel.FIFTEEN,
        contexts=RetrievalContexts(),
        now=NOW,
    )
    second_ranked, second_selected = engine.rank(
        list(reversed(corpus)),
        window=WindowLabel.FIFTEEN,
        contexts=RetrievalContexts(),
        now=NOW,
    )

    assert [item.candidate.id for item in first_ranked] == [
        item.candidate.id for item in second_ranked
    ]
    assert [item.candidate.id for item in first_selected] == [
        item.candidate.id for item in second_selected
    ]
    assert {item.candidate.duration_bucket for item in first_ranked} == {"spark", "snack"}


def test_fresh_open_thought_with_unknown_duration_clears_minimum_score() -> None:
    unknown = candidate(1, duration="unknown", score_age_days=0)

    ranked, selected = RetrievalEngine().rank(
        [unknown],
        window=WindowLabel.FIFTEEN,
        contexts=RetrievalContexts(),
        now=NOW,
    )

    assert ranked[0].score >= 0.42
    assert [item.candidate.id for item in selected] == [unknown.id]


def test_high_confidence_context_filters_but_low_confidence_only_reweights() -> None:
    engine = RetrievalEngine()
    high = candidate(
        1,
        energy="high",
        energy_confidence=0.95,
        contexts=["laptop"],
        context_confidence=0.95,
    )
    low = candidate(
        2,
        energy="high",
        energy_confidence=0.4,
        contexts=["laptop"],
        context_confidence=0.4,
    )
    ranked, _ = engine.rank(
        [high, low],
        window=WindowLabel.FIFTEEN,
        contexts=RetrievalContexts(phone_only=True, low_energy=True),
        now=NOW,
    )
    assert [item.candidate.id for item in ranked] == [low.id]


def test_recently_surfaced_thought_is_penalized_instead_of_hidden() -> None:
    recent = replace(
        candidate(1),
        last_surfaced_at=NOW - timedelta(hours=1),
        surface_count=12,
    )

    ranked, selected = RetrievalEngine().rank(
        [recent],
        window=WindowLabel.FIFTEEN,
        contexts=RetrievalContexts(),
        now=NOW,
    )

    assert [item.candidate.id for item in selected] == [recent.id]
    assert ranked[0].components["fatigue_penalty"] > 0


def test_feedback_calibration_changes_the_next_retrieval_score() -> None:
    original = candidate(1, duration="spark", contexts=["home"])
    calibrated = replace(
        original,
        kind_affinity=0.7,
        duration_adjustment=0.05,
        context_affinity=0.7,
    )

    original_ranked, _ = RetrievalEngine().rank(
        [original],
        window=WindowLabel.FIFTEEN,
        contexts=RetrievalContexts(),
        now=NOW,
    )
    calibrated_ranked, _ = RetrievalEngine().rank(
        [calibrated],
        window=WindowLabel.FIFTEEN,
        contexts=RetrievalContexts(),
        now=NOW,
    )

    assert calibrated_ranked[0].score > original_ranked[0].score
    assert calibrated_ranked[0].components["personal_kind_affinity"] == 0.7
    assert (
        calibrated_ranked[0].components["capacity_fit"]
        > original_ranked[0].components["capacity_fit"]
    )
    assert (
        calibrated_ranked[0].components["context_fit"]
        > original_ranked[0].components["context_fit"]
    )


def test_near_duplicates_are_suppressed_and_diversity_is_bounded() -> None:
    engine = RetrievalEngine()
    corpus = [
        candidate(1, text="Draft launch email", embedding=[1.0, 0.0]),
        candidate(2, text="Draft the launch email", embedding=[0.99, 0.01]),
        candidate(3, text="Research keyboard options", kind="research", embedding=[0.0, 1.0]),
        candidate(4, text="Book launch room", embedding=[0.5, 0.5]),
    ]
    _, selected = engine.rank(
        corpus,
        window=WindowLabel.FIFTEEN,
        contexts=RetrievalContexts(),
        now=NOW,
    )
    texts = {item.candidate.refined_text for item in selected}
    assert len(selected) == 3
    assert not {"Draft launch email", "Draft the launch email"}.issubset(texts)
    assert any(item.candidate.kind == "research" for item in selected)


def test_fewer_than_three_and_no_result_when_nothing_is_eligible_are_allowed() -> None:
    engine = RetrievalEngine()
    eligible = candidate(1, duration="spark")
    done = candidate(2, duration="spark", status="done")
    hidden = candidate(3, duration="spark", surface_policy="search_only")
    _, selected = engine.rank(
        [eligible, done, hidden],
        window=WindowLabel.FIVE,
        contexts=RetrievalContexts(),
        now=NOW,
    )
    assert [item.candidate.id for item in selected] == [eligible.id]

    _, none = engine.rank(
        [done, hidden],
        window=WindowLabel.FIVE,
        contexts=RetrievalContexts(),
        now=NOW,
    )
    assert none == []


def test_best_eligible_candidate_is_returned_below_the_score_threshold() -> None:
    eligible = candidate(1, duration="spark")

    ranked, selected = RetrievalEngine(minimum_score=1.0).rank(
        [eligible],
        window=WindowLabel.FIVE,
        contexts=RetrievalContexts(),
        now=NOW,
    )

    assert ranked[0].score < 1.0
    assert [item.candidate.id for item in selected] == [eligible.id]

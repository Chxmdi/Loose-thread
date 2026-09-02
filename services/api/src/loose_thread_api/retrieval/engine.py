import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from loose_thread_api.models.retrievals import RetrievalContexts, WindowLabel

RANKING_VERSION = "capacity-v1"
MINIMUM_SCORE = 0.42
CONTEXT_HARD_FILTER_CONFIDENCE = 0.8

WEIGHTS = {
    "rediscovery_value": 0.22,
    "capacity_fit": 0.20,
    "context_fit": 0.14,
    "open_loop_value": 0.14,
    "thread_momentum": 0.10,
    "personal_kind_affinity": 0.08,
    "explicit_temporal_relevance": 0.07,
    "novelty": 0.05,
}

CAPACITY_FIT: dict[WindowLabel, dict[str, float]] = {
    WindowLabel.FIVE: {"spark": 1.0, "unknown": 0.4},
    WindowLabel.FIFTEEN: {"spark": 0.8, "snack": 1.0, "unknown": 0.4},
    WindowLabel.THIRTY: {"snack": 1.0, "session": 0.85, "unknown": 0.4},
    WindowLabel.SIXTY: {"snack": 0.65, "session": 1.0, "deep": 0.65, "unknown": 0.4},
    WindowLabel.A_WHILE: {"session": 0.85, "deep": 1.0, "unknown": 0.4},
}


@dataclass(frozen=True)
class RetrievalCandidate:
    id: UUID
    refined_text: str
    kind: str
    commitment_strength: str
    duration_bucket: str
    energy: str
    contexts: list[str]
    temporal: dict[str, Any]
    open_loop: dict[str, Any]
    confidence: dict[str, Any]
    status: str
    surface_policy: str
    last_surfaced_at: datetime | None
    surface_count: int
    snooze_until: datetime | None
    embedding: Sequence[float] | None
    created_at: datetime
    relationship_count: int
    kind_affinity: float
    recent_rejections: int
    duration_adjustment: float = 0.0
    context_affinity: float = 0.5


@dataclass(frozen=True)
class ScoredCandidate:
    candidate: RetrievalCandidate
    score: float
    components: dict[str, float]


class RetrievalEngine:
    def __init__(
        self,
        *,
        weights: Mapping[str, float] | None = None,
        minimum_score: float = MINIMUM_SCORE,
    ) -> None:
        self._weights = dict(weights or WEIGHTS)
        if set(self._weights) != set(WEIGHTS):
            raise ValueError("retrieval weights must define every ranking component")
        self._minimum_score = minimum_score

    def rank(
        self,
        candidates: list[RetrievalCandidate],
        *,
        window: WindowLabel,
        contexts: RetrievalContexts,
        excluded_ids: set[UUID] | None = None,
        now: datetime | None = None,
    ) -> tuple[list[ScoredCandidate], list[ScoredCandidate]]:
        resolved_now = now or datetime.now(UTC)
        excluded = excluded_ids or set()
        eligible = [
            self._score(candidate, window=window, contexts=contexts, now=resolved_now)
            for candidate in candidates
            if candidate.id not in excluded
            and self._eligible(candidate, window=window, contexts=contexts, now=resolved_now)
        ]
        ranked = sorted(eligible, key=lambda item: (-item.score, item.candidate.id.hex))
        selected = self._select(ranked)
        return ranked, selected

    def _eligible(
        self,
        candidate: RetrievalCandidate,
        *,
        window: WindowLabel,
        contexts: RetrievalContexts,
        now: datetime,
    ) -> bool:
        if candidate.status != "active" or candidate.surface_policy != "normal":
            return False
        if candidate.duration_bucket not in CAPACITY_FIT[window]:
            return False
        if candidate.snooze_until is not None and candidate.snooze_until > now:
            return False
        temporal_type = candidate.temporal.get("type")
        resolved_at = self._datetime(candidate.temporal.get("resolved_at"))
        if temporal_type == "not_before" and resolved_at is not None and resolved_at > now:
            return False

        context_confidence = self._number(candidate.confidence.get("contexts"), default=0.0)
        energy_confidence = self._number(candidate.confidence.get("energy"), default=0.0)
        tags = set(candidate.contexts)
        if context_confidence >= CONTEXT_HARD_FILTER_CONFIDENCE:
            if contexts.phone_only and tags.intersection({"laptop", "needs_quiet"}):
                return False
            if contexts.out and "home" in tags:
                return False
            if contexts.home and "out" in tags:
                return False
        return not (
            contexts.low_energy
            and candidate.energy == "high"
            and energy_confidence >= CONTEXT_HARD_FILTER_CONFIDENCE
        )

    def _score(
        self,
        candidate: RetrievalCandidate,
        *,
        window: WindowLabel,
        contexts: RetrievalContexts,
        now: datetime,
    ) -> ScoredCandidate:
        age_days = max(0.0, (now - candidate.created_at).total_seconds() / 86400)
        rediscovery = (1 - math.exp(-age_days / 7)) * max(0.45, 1 - age_days / 730)
        capacity = max(
            0.0,
            min(
                1.0,
                CAPACITY_FIT[window][candidate.duration_bucket] + candidate.duration_adjustment,
            ),
        )
        context_fit = self._context_fit(candidate, contexts)
        open_loop = 0.95 if candidate.open_loop.get("is_open") is True else 0.35
        momentum = min(1.0, candidate.relationship_count / 3)
        affinity = max(0.0, min(1.0, candidate.kind_affinity))
        temporal = self._temporal_relevance(candidate.temporal, now)
        novelty = max(0.1, 1 - candidate.surface_count * 0.18)
        fatigue = 0.0
        if candidate.last_surfaced_at is not None:
            days_since = max(0.0, (now - candidate.last_surfaced_at).total_seconds() / 86400)
            fatigue += max(0.0, 0.16 * (1 - days_since / 14))
        rejection = min(0.3, candidate.recent_rejections * 0.1)
        components = {
            "rediscovery_value": rediscovery,
            "capacity_fit": capacity,
            "context_fit": context_fit,
            "open_loop_value": open_loop,
            "thread_momentum": momentum,
            "personal_kind_affinity": affinity,
            "explicit_temporal_relevance": temporal,
            "novelty": novelty,
            "fatigue_penalty": fatigue,
            "rejection_penalty": rejection,
        }
        score = sum(components[name] * weight for name, weight in self._weights.items())
        score -= fatigue + rejection
        return ScoredCandidate(candidate=candidate, score=round(score, 8), components=components)

    def _select(self, ranked: list[ScoredCandidate]) -> list[ScoredCandidate]:
        selected: list[ScoredCandidate] = []
        remaining = [candidate for candidate in ranked if candidate.score >= self._minimum_score]
        while remaining and len(selected) < 3:
            top = remaining[0]
            if selected and all(
                item.candidate.kind == selected[0].candidate.kind for item in selected
            ):
                diverse = next(
                    (
                        item
                        for item in remaining
                        if item.candidate.kind != selected[0].candidate.kind
                        and top.score - item.score <= 0.08
                    ),
                    None,
                )
                if diverse is not None:
                    top = diverse
            remaining.remove(top)
            if any(self._near_duplicate(top.candidate, item.candidate) for item in selected):
                continue
            selected.append(top)
        return selected

    def _context_fit(self, candidate: RetrievalCandidate, contexts: RetrievalContexts) -> float:
        requested: set[str] = set()
        if contexts.phone_only:
            requested.add("phone_ok")
        if contexts.out:
            requested.add("out")
        if contexts.home:
            requested.add("home")
        if contexts.low_energy:
            requested.add("low_energy_ok")
        if not requested:
            base = 0.65
        else:
            tags = set(candidate.contexts)
            matches = len(requested.intersection(tags))
            base = 0.4 + 0.6 * (matches / len(requested))
        adjustment = (max(0.0, min(1.0, candidate.context_affinity)) - 0.5) * 0.2
        return max(0.0, min(1.0, base + adjustment))

    def _temporal_relevance(self, temporal: dict[str, Any], now: datetime) -> float:
        resolved_at = self._datetime(temporal.get("resolved_at"))
        if resolved_at is None:
            return 0.5
        days = (resolved_at - now).total_seconds() / 86400
        if -1 <= days <= 3:
            return 1.0
        if 3 < days <= 14:
            return 0.8
        if days > 14:
            return 0.4
        return 0.2

    def _near_duplicate(self, left: RetrievalCandidate, right: RetrievalCandidate) -> bool:
        if left.embedding is not None and right.embedding is not None:
            similarity = self._cosine(left.embedding, right.embedding)
            if similarity >= 0.94:
                return True
        left_tokens = set(re.findall(r"[a-z0-9]+", left.refined_text.lower()))
        right_tokens = set(re.findall(r"[a-z0-9]+", right.refined_text.lower()))
        union = left_tokens | right_tokens
        return bool(union) and len(left_tokens & right_tokens) / len(union) >= 0.8

    @staticmethod
    def _cosine(left: Sequence[float], right: Sequence[float]) -> float:
        dot = sum(float(a) * float(b) for a, b in zip(left, right, strict=True))
        left_norm = math.sqrt(sum(float(value) ** 2 for value in left))
        right_norm = math.sqrt(sum(float(value) ** 2 for value in right))
        if left_norm == 0 or right_norm == 0:
            return 0.0
        return dot / (left_norm * right_norm)

    @staticmethod
    def _datetime(value: object) -> datetime | None:
        if isinstance(value, datetime):
            return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
        if not isinstance(value, str):
            return None
        try:
            parsed = datetime.fromisoformat(value)
            return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)
        except ValueError:
            return None

    @staticmethod
    def _number(value: object, *, default: float) -> float:
        return float(value) if isinstance(value, int | float) else default

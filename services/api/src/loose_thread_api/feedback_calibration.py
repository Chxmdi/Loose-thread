from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

import asyncpg

from loose_thread_api.models.calibration import CalibrationDebugView
from loose_thread_api.models.jobs import Job
from loose_thread_api.orchestration.worker import JobHandlerError

CALIBRATION_VERSION = "feedback-v1"


@dataclass(frozen=True)
class CalibrationSignals:
    kind: float = 0.0
    duration: float = 0.0
    context: float = 0.0


class FeedbackCalibrationRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def apply(self, *, user_id: UUID, feedback_id: UUID) -> None:
        async with self._pool.acquire() as connection, connection.transaction():
            event = await connection.fetchrow(
                """
                select feedback.id, feedback.event_type, feedback.event_data,
                       feedback.calibration_applied_at,
                       thought.kind, thought.duration_bucket, thought.contexts
                from public.feedback_events feedback
                left join public.thoughts thought
                  on thought.id = feedback.thought_id and thought.user_id = feedback.user_id
                where feedback.id = $1 and feedback.user_id = $2
                for update of feedback
                """,
                feedback_id,
                user_id,
            )
            if event is None:
                raise JobHandlerError(
                    "feedback_not_found",
                    "Feedback event is unavailable for calibration",
                    retryable=False,
                )
            if event["calibration_applied_at"] is not None:
                return

            await connection.execute(
                """
                insert into public.user_calibration (user_id)
                values ($1)
                on conflict (user_id) do nothing
                """,
                user_id,
            )
            current = await connection.fetchrow(
                "select * from public.user_calibration where user_id = $1 for update",
                user_id,
            )
            if current is None:
                raise RuntimeError("calibration row was not created")

            signals = self._signals(str(event["event_type"]), dict(event["event_data"]))
            kind_affinity = self._mapping(current["kind_affinity"])
            duration_calibration = self._mapping(current["duration_calibration"])
            context_affinity = self._mapping(current["context_affinity"])

            kind = event["kind"]
            duration = event["duration_bucket"]
            contexts = list(event["contexts"] or [])
            if isinstance(kind, str) and signals.kind:
                kind_affinity[kind] = self._bounded(
                    kind_affinity.get(kind, 0.5) + signals.kind * 0.10,
                    lower=0.1,
                    upper=0.9,
                )
            if isinstance(duration, str) and signals.duration:
                duration_calibration[duration] = self._bounded(
                    duration_calibration.get(duration, 0.0) + signals.duration * 0.05,
                    lower=-0.2,
                    upper=0.2,
                )
            if signals.context:
                for context in contexts:
                    if isinstance(context, str):
                        context_affinity[context] = self._bounded(
                            context_affinity.get(context, 0.5) + signals.context * 0.06,
                            lower=0.1,
                            upper=0.9,
                        )

            await connection.execute(
                """
                update public.user_calibration
                set duration_calibration = $2::jsonb,
                    kind_affinity = $3::jsonb,
                    context_affinity = $4::jsonb,
                    observation_count = observation_count + 1,
                    updated_at = now()
                where user_id = $1
                """,
                user_id,
                duration_calibration,
                kind_affinity,
                context_affinity,
            )
            await connection.execute(
                """
                update public.feedback_events
                set calibration_applied_at = now(), calibration_version = $3
                where id = $1 and user_id = $2
                """,
                feedback_id,
                user_id,
                CALIBRATION_VERSION,
            )

    async def get_for_user(self, *, user_id: UUID) -> CalibrationDebugView:
        row = await self._pool.fetchrow(
            "select * from public.user_calibration where user_id = $1",
            user_id,
        )
        if row is None:
            return CalibrationDebugView()
        return CalibrationDebugView.model_validate(dict(row))

    @staticmethod
    def _signals(event_type: str, event_data: dict[str, Any]) -> CalibrationSignals:
        if event_type == "session_completed":
            outcome = str(event_data.get("outcome", ""))
            fit = str(event_data.get("fit", ""))
            kind = {
                "done": 1.0,
                "partial": 0.5,
                "stopped": -0.5,
                "spawned_new": 0.4,
            }.get(outcome, 0.0)
            duration = {"right": 1.0, "shorter": -0.5, "longer": -0.5}.get(fit, 0.0)
            return CalibrationSignals(kind=kind, duration=duration, context=kind)
        if event_type == "retrieval_action" and event_data.get("action") == "start":
            return CalibrationSignals(kind=0.2, context=0.2)
        # `not_now` and `done_with_this` describe timing/item state, not dislike of a kind.
        return CalibrationSignals()

    @staticmethod
    def _mapping(value: object) -> dict[str, float]:
        if not isinstance(value, dict):
            return {}
        return {
            str(key): float(item) for key, item in value.items() if isinstance(item, int | float)
        }

    @staticmethod
    def _bounded(value: float, *, lower: float, upper: float) -> float:
        return round(max(lower, min(upper, value)), 6)


class FeedbackCalibrationJobHandler:
    def __init__(self, repository: FeedbackCalibrationRepository) -> None:
        self._repository = repository

    async def __call__(self, job: Job) -> None:
        if job.entity_type != "feedback_event":
            raise JobHandlerError(
                "invalid_calibration_job",
                "Calibration job must target a feedback event",
                retryable=False,
            )
        await self._repository.apply(user_id=job.user_id, feedback_id=job.entity_id)

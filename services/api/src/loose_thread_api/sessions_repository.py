from typing import Any
from uuid import UUID

import asyncpg

from loose_thread_api.models.sessions import (
    RetrievalAction,
    RetrievalActionCreate,
    SessionComplete,
    SessionOutcome,
    SessionStart,
    SessionView,
    SpawnThoughtCreate,
    SpawnThoughtResponse,
)


class SessionConflictError(RuntimeError):
    pass


class SessionRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def start(self, *, user_id: UUID, body: SessionStart) -> SessionView:
        existing = await self.get(user_id=user_id, session_id=body.id)
        if existing is not None:
            return existing
        try:
            async with self._pool.acquire() as connection, connection.transaction():
                thought = await connection.fetchrow(
                    "select status from public.thoughts where id = $1 and user_id = $2 and not is_deleted",
                    body.thought_id,
                    user_id,
                )
                if thought is None or thought["status"] not in ("active", "in_progress"):
                    raise SessionConflictError("thought is not available to start")
                if body.retrieval_id is not None:
                    selected = await connection.fetchval(
                        """
                        select selected from public.retrieval_impressions
                        where retrieval_id = $1 and thought_id = $2 and user_id = $3
                        """,
                        body.retrieval_id,
                        body.thought_id,
                        user_id,
                    )
                    if selected is not True:
                        raise SessionConflictError("thought was not selected by this retrieval")
                row = await connection.fetchrow(
                    """
                    insert into public.sessions (
                        id, user_id, thought_id, retrieval_id, window_minutes, window_label
                    ) values ($1, $2, $3, $4, $5, $6)
                    returning *
                    """,
                    body.id,
                    user_id,
                    body.thought_id,
                    body.retrieval_id,
                    self._minutes(body.window.value),
                    body.window.value,
                )
                await connection.execute(
                    "update public.thoughts set status = 'in_progress' where id = $1 and user_id = $2",
                    body.thought_id,
                    user_id,
                )
                if body.retrieval_id is not None:
                    await connection.execute(
                        """
                        update public.retrieval_impressions
                        set selected = true, action = 'start'
                        where retrieval_id = $1 and thought_id = $2 and user_id = $3
                        """,
                        body.retrieval_id,
                        body.thought_id,
                        user_id,
                    )
                await self._feedback(
                    connection,
                    user_id=user_id,
                    session_id=body.id,
                    retrieval_id=body.retrieval_id,
                    thought_id=body.thought_id,
                    event_type="session_started",
                    event_data={"window": body.window.value},
                    idempotency_key=body.idempotency_key,
                )
        except asyncpg.UniqueViolationError as exc:
            retry = await self.get(user_id=user_id, session_id=body.id)
            if retry is not None:
                return retry
            raise SessionConflictError("session or idempotency key is already in use") from exc
        if row is None:
            raise RuntimeError("session insert did not return a row")
        return self._view(row)

    async def complete(
        self, *, user_id: UUID, session_id: UUID, body: SessionComplete
    ) -> SessionView:
        async with self._pool.acquire() as connection, connection.transaction():
            current = await connection.fetchrow(
                "select * from public.sessions where id = $1 and user_id = $2 for update",
                session_id,
                user_id,
            )
            if current is None:
                raise SessionConflictError("session was not found")
            if current["ended_at"] is not None:
                if (
                    current["outcome"] == body.outcome.value
                    and current["fit_feedback"] == body.fit.value
                    and current["actual_minutes"] == body.actual_minutes
                ):
                    return self._view(current)
                raise SessionConflictError("session is already completed with a different outcome")
            row = await connection.fetchrow(
                """
                update public.sessions
                set ended_at = now(), outcome = $3, fit_feedback = $4,
                    actual_minutes = $5, updated_at = now()
                where id = $1 and user_id = $2
                returning *
                """,
                session_id,
                user_id,
                body.outcome.value,
                body.fit.value,
                body.actual_minutes,
            )
            thought_status = "done" if body.outcome is SessionOutcome.DONE else "active"
            await connection.execute(
                "update public.thoughts set status = $3 where id = $1 and user_id = $2",
                current["thought_id"],
                user_id,
                thought_status,
            )
            await self._feedback(
                connection,
                user_id=user_id,
                session_id=session_id,
                retrieval_id=current["retrieval_id"],
                thought_id=current["thought_id"],
                event_type="session_completed",
                event_data={
                    "outcome": body.outcome.value,
                    "fit": body.fit.value,
                    "actual_minutes": body.actual_minutes,
                },
                idempotency_key=body.idempotency_key,
                enqueue_calibration=True,
            )
        if row is None:
            raise RuntimeError("session completion did not return a row")
        return self._view(row)

    async def spawn(
        self, *, user_id: UUID, session_id: UUID, body: SpawnThoughtCreate
    ) -> SpawnThoughtResponse:
        try:
            async with self._pool.acquire() as connection, connection.transaction():
                session = await connection.fetchrow(
                    "select * from public.sessions where id = $1 and user_id = $2 for update",
                    session_id,
                    user_id,
                )
                if session is None:
                    raise SessionConflictError("session was not found")
                capture = await connection.fetchrow(
                    """
                    insert into public.captures (
                        id, user_id, device_id, idempotency_key, capture_mode, raw_text,
                        timezone, client_created_at, processing_status
                    ) values ($1, $2, $3, $4, 'text', $5, $6, $7, 'succeeded')
                    on conflict (user_id, idempotency_key) do update
                    set idempotency_key = public.captures.idempotency_key
                    returning id
                    """,
                    body.capture_id,
                    user_id,
                    body.device_id,
                    body.idempotency_key,
                    body.raw_text,
                    body.timezone,
                    body.client_created_at,
                )
                if capture is None:
                    raise RuntimeError("spawn capture did not return a row")
                thought = await connection.fetchrow(
                    """
                    insert into public.thoughts (
                        id, user_id, capture_id, client_created_at, raw_fragment, refined_text,
                        refined_source, kind, commitment_strength, surface_policy, duration_bucket,
                        energy, contexts, open_loop, confidence, enrichment_version
                    ) values (
                        $1, $2, $3, $4, $5, $5, 'user_raw', 'unfinished', 'none', 'normal',
                        'unknown', 'unknown', '{anywhere}', '{"is_open":true,"type":"spawned"}',
                        '{"kind":1,"commitment_strength":1,"duration_bucket":0,"energy":0,"contexts":1,"surface_policy":1}',
                        'user-spawn-v1'
                    )
                    on conflict (capture_id, split_index, enrichment_version) do update
                    set refined_text = public.thoughts.refined_text
                    returning id
                    """,
                    body.thought_id,
                    user_id,
                    capture["id"],
                    body.client_created_at,
                    body.raw_text,
                )
                if thought is None:
                    raise RuntimeError("spawn thought did not return a row")
                await connection.execute(
                    """
                    insert into public.thought_relationships (
                        user_id, from_thought_id, to_thought_id, relation_type,
                        confidence, source, rationale
                    ) values ($1, $2, $3, 'spawned_from', 1, 'user', 'Created during session')
                    on conflict (from_thought_id, to_thought_id, relation_type) do nothing
                    """,
                    user_id,
                    thought["id"],
                    session["thought_id"],
                )
                await connection.execute(
                    """
                    update public.sessions
                    set ended_at = coalesce(ended_at, now()), outcome = 'spawned_new', updated_at = now()
                    where id = $1 and user_id = $2
                    """,
                    session_id,
                    user_id,
                )
                await connection.execute(
                    "update public.thoughts set status = 'active' where id = $1 and user_id = $2",
                    session["thought_id"],
                    user_id,
                )
                await connection.execute(
                    """
                    insert into public.jobs (
                        user_id, job_type, entity_type, entity_id, idempotency_key,
                        payload, correlation_id
                    ) values ($1, 'embed_thought', 'thought', $2, $3, $4::jsonb, gen_random_uuid())
                    on conflict (user_id, idempotency_key) do nothing
                    """,
                    user_id,
                    thought["id"],
                    f"embed_thought:{thought['id']}:v1",
                    {"thought_id": str(thought["id"])},
                )
                await self._feedback(
                    connection,
                    user_id=user_id,
                    session_id=session_id,
                    retrieval_id=session["retrieval_id"],
                    thought_id=thought["id"],
                    event_type="thought_spawned",
                    event_data={"spawned_from": str(session["thought_id"])},
                    idempotency_key=f"spawn:{body.idempotency_key}",
                )
        except asyncpg.UniqueViolationError as exc:
            raise SessionConflictError("spawn identifiers are already in use") from exc
        return SpawnThoughtResponse(
            capture_id=capture["id"],
            thought_id=thought["id"],
            spawned_from_thought_id=session["thought_id"],
        )

    async def record_retrieval_action(
        self, *, user_id: UUID, retrieval_id: UUID, body: RetrievalActionCreate
    ) -> None:
        async with self._pool.acquire() as connection, connection.transaction():
            exists = await connection.fetchval(
                "select true from public.retrievals where id = $1 and user_id = $2",
                retrieval_id,
                user_id,
            )
            if exists is not True:
                raise SessionConflictError("retrieval was not found")
            if body.action is RetrievalAction.NONE_OF_THESE:
                await connection.execute(
                    """
                    update public.retrieval_impressions set action = 'none_of_these'
                    where retrieval_id = $1 and user_id = $2 and selected
                    """,
                    retrieval_id,
                    user_id,
                )
            else:
                if body.thought_id is None:
                    raise SessionConflictError("thought_id is required for this action")
                updated = await connection.execute(
                    """
                    update public.retrieval_impressions set action = $4
                    where retrieval_id = $1 and thought_id = $2 and user_id = $3 and selected
                    """,
                    retrieval_id,
                    body.thought_id,
                    user_id,
                    body.action.value,
                )
                if updated != "UPDATE 1":
                    raise SessionConflictError("thought was not selected by this retrieval")
                if body.action is RetrievalAction.NOT_NOW:
                    await connection.execute(
                        "update public.thoughts set snooze_until = now() + interval '1 day' where id = $1 and user_id = $2",
                        body.thought_id,
                        user_id,
                    )
                elif body.action is RetrievalAction.DONE_WITH_THIS:
                    await connection.execute(
                        "update public.thoughts set status = 'archived' where id = $1 and user_id = $2",
                        body.thought_id,
                        user_id,
                    )
            await self._feedback(
                connection,
                user_id=user_id,
                session_id=None,
                retrieval_id=retrieval_id,
                thought_id=body.thought_id,
                event_type="retrieval_action",
                event_data={"action": body.action.value},
                idempotency_key=body.idempotency_key,
                enqueue_calibration=True,
            )

    async def get(self, *, user_id: UUID, session_id: UUID) -> SessionView | None:
        row = await self._pool.fetchrow(
            "select * from public.sessions where id = $1 and user_id = $2",
            session_id,
            user_id,
        )
        return self._view(row) if row is not None else None

    @staticmethod
    async def _feedback(
        connection: asyncpg.Connection,
        *,
        user_id: UUID,
        session_id: UUID | None,
        retrieval_id: UUID | None,
        thought_id: UUID | None,
        event_type: str,
        event_data: dict[str, Any],
        idempotency_key: str,
        enqueue_calibration: bool = False,
    ) -> UUID:
        feedback = await connection.fetchrow(
            """
            insert into public.feedback_events (
                user_id, session_id, retrieval_id, thought_id,
                event_type, event_data, idempotency_key
            ) values ($1, $2, $3, $4, $5, $6::jsonb, $7)
            on conflict (user_id, idempotency_key) do update
            set idempotency_key = public.feedback_events.idempotency_key
            returning id
            """,
            user_id,
            session_id,
            retrieval_id,
            thought_id,
            event_type,
            event_data,
            idempotency_key,
        )
        if feedback is None:
            raise RuntimeError("feedback insert did not return a row")
        feedback_id = UUID(str(feedback["id"]))
        if enqueue_calibration:
            await connection.execute(
                """
                insert into public.jobs (
                    user_id, job_type, entity_type, entity_id, idempotency_key,
                    payload, correlation_id
                ) values (
                    $1, 'apply_feedback_calibration', 'feedback_event', $2, $3,
                    $4::jsonb, gen_random_uuid()
                )
                on conflict (user_id, idempotency_key) do nothing
                """,
                user_id,
                feedback_id,
                f"apply_feedback_calibration:{feedback_id}:v1",
                {"feedback_id": str(feedback_id)},
            )
        return feedback_id

    @staticmethod
    def _view(row: asyncpg.Record) -> SessionView:
        return SessionView(
            id=row["id"],
            thought_id=row["thought_id"],
            retrieval_id=row["retrieval_id"],
            window=row["window_label"],
            started_at=row["started_at"],
            ended_at=row["ended_at"],
            outcome=row["outcome"],
            fit=row["fit_feedback"],
            actual_minutes=row["actual_minutes"],
        )

    @staticmethod
    def _minutes(window: str) -> int | None:
        return int(window) if window != "a_while" else None

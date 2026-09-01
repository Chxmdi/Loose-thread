from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import asyncpg
from pgvector import Vector

from loose_thread_api.models.retrievals import (
    RetrievalCard,
    RetrievalContexts,
    RetrievalCreate,
    RetrievalResponse,
    WindowLabel,
)
from loose_thread_api.retrieval.engine import (
    RANKING_VERSION,
    RetrievalCandidate,
    RetrievalEngine,
)


class RetrievalConflictError(RuntimeError):
    pass


class RetrievalRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def create(
        self,
        *,
        user_id: UUID,
        request: RetrievalCreate,
        engine: RetrievalEngine,
    ) -> RetrievalResponse:
        existing = await self.get_for_user(user_id=user_id, retrieval_id=request.id)
        if existing is not None:
            return existing

        excluded_ids: set[UUID] = set()
        if request.reshuffle_of is not None:
            parent = await self._pool.fetchrow(
                """
                select reshuffle_of, result_thought_ids
                from public.retrievals
                where id = $1 and user_id = $2
                """,
                request.reshuffle_of,
                user_id,
            )
            if parent is None:
                raise RetrievalConflictError("original retrieval was not found")
            if parent["reshuffle_of"] is not None:
                raise RetrievalConflictError("a reshuffle cannot be reshuffled again")
            excluded_ids = set(parent["result_thought_ids"])

        now = datetime.now(UTC)
        candidates = await self._load_candidates(user_id=user_id)
        ranked, selected = engine.rank(
            candidates,
            window=request.window,
            contexts=request.contexts,
            excluded_ids=excluded_ids,
            now=now,
        )
        selected_ids = [item.candidate.id for item in selected]
        selected_set = set(selected_ids)
        try:
            async with self._pool.acquire() as connection, connection.transaction():
                row = await connection.fetchrow(
                    """
                    insert into public.retrievals (
                        id, user_id, requested_at, window_label, contexts, candidate_count,
                        result_thought_ids, ranking_version, reshuffle_of
                    )
                    values ($1, $2, $3, $4, $5::jsonb, $6, $7, $8, $9)
                    returning created_at
                    """,
                    request.id,
                    user_id,
                    now,
                    request.window.value,
                    request.contexts.model_dump(mode="json"),
                    len(ranked),
                    selected_ids,
                    RANKING_VERSION,
                    request.reshuffle_of,
                )
                for rank, item in enumerate(ranked, start=1):
                    await connection.execute(
                        """
                        insert into public.retrieval_impressions (
                            user_id, retrieval_id, thought_id, rank_position,
                            score, score_components, selected
                        )
                        values ($1, $2, $3, $4, $5, $6::jsonb, $7)
                        """,
                        user_id,
                        request.id,
                        item.candidate.id,
                        rank,
                        item.score,
                        item.components,
                        item.candidate.id in selected_set,
                    )
                if selected_ids:
                    await connection.execute(
                        """
                        update public.thoughts
                        set last_surfaced_at = $3, surface_count = surface_count + 1
                        where user_id = $1 and id = any($2::uuid[])
                        """,
                        user_id,
                        selected_ids,
                        now,
                    )
        except asyncpg.UniqueViolationError as exc:
            retry = await self.get_for_user(user_id=user_id, retrieval_id=request.id)
            if retry is not None:
                return retry
            if request.reshuffle_of is not None:
                raise RetrievalConflictError("this retrieval has already been reshuffled") from exc
            raise RetrievalConflictError("retrieval id is already in use") from exc
        if row is None:
            raise RuntimeError("retrieval insert did not return a row")
        return RetrievalResponse(
            id=request.id,
            window=request.window,
            contexts=request.contexts,
            reshuffle_of=request.reshuffle_of,
            candidate_count=len(ranked),
            ranking_version=RANKING_VERSION,
            cards=[self._card(item.candidate, rank) for rank, item in enumerate(selected, start=1)],
            created_at=row["created_at"],
        )

    async def create_reshuffle(
        self,
        *,
        user_id: UUID,
        retrieval_id: UUID,
        new_id: UUID,
        engine: RetrievalEngine,
    ) -> RetrievalResponse:
        parent = await self._pool.fetchrow(
            """
            select window_label, contexts
            from public.retrievals
            where id = $1 and user_id = $2
            """,
            retrieval_id,
            user_id,
        )
        if parent is None:
            raise RetrievalConflictError("original retrieval was not found")
        return await self.create(
            user_id=user_id,
            request=RetrievalCreate(
                id=new_id,
                window=WindowLabel(parent["window_label"]),
                contexts=RetrievalContexts.model_validate(parent["contexts"]),
                reshuffle_of=retrieval_id,
            ),
            engine=engine,
        )

    async def get_for_user(
        self, *, user_id: UUID, retrieval_id: UUID
    ) -> RetrievalResponse | None:
        row = await self._pool.fetchrow(
            """
            select id, window_label, contexts, reshuffle_of, candidate_count,
                   ranking_version, result_thought_ids, created_at
            from public.retrievals
            where id = $1 and user_id = $2
            """,
            retrieval_id,
            user_id,
        )
        if row is None:
            return None
        thought_rows = await self._pool.fetch(
            """
            select id, refined_text, kind, commitment_strength, duration_bucket,
                   energy, contexts, open_loop
            from public.thoughts
            where user_id = $1 and id = any($2::uuid[])
            order by array_position($2::uuid[], id)
            """,
            user_id,
            row["result_thought_ids"],
        )
        return RetrievalResponse(
            id=row["id"],
            window=WindowLabel(row["window_label"]),
            contexts=RetrievalContexts.model_validate(row["contexts"]),
            reshuffle_of=row["reshuffle_of"],
            candidate_count=row["candidate_count"],
            ranking_version=row["ranking_version"],
            cards=[self._card_from_record(item, rank) for rank, item in enumerate(thought_rows, 1)],
            created_at=row["created_at"],
        )

    async def debug_for_user(
        self, *, user_id: UUID, retrieval_id: UUID
    ) -> dict[str, Any] | None:
        retrieval = await self._pool.fetchrow(
            "select * from public.retrievals where id = $1 and user_id = $2",
            retrieval_id,
            user_id,
        )
        if retrieval is None:
            return None
        impressions = await self._pool.fetch(
            """
            select thought_id, rank_position, score, score_components, selected, action, created_at
            from public.retrieval_impressions
            where retrieval_id = $1 and user_id = $2
            order by rank_position
            """,
            retrieval_id,
            user_id,
        )
        return {
            "retrieval": dict(retrieval),
            "impressions": [dict(item) for item in impressions],
        }

    async def _load_candidates(self, *, user_id: UUID) -> list[RetrievalCandidate]:
        rows = await self._pool.fetch(
            """
            select t.id, t.refined_text, t.kind, t.commitment_strength, t.duration_bucket,
                   t.energy, t.contexts, t.temporal, t.open_loop, t.confidence, t.status,
                   t.surface_policy, t.last_surfaced_at, t.surface_count, t.snooze_until,
                   t.embedding, t.created_at,
                   (
                       select count(*)
                       from public.thought_relationships relationship
                       where relationship.user_id = t.user_id
                         and (relationship.from_thought_id = t.id or relationship.to_thought_id = t.id)
                         and relationship.created_at > now() - interval '30 days'
                   )::integer as relationship_count,
                   coalesce((calibration.kind_affinity ->> t.kind)::double precision, 0.5)
                       as kind_affinity,
                   (
                       select count(*)
                       from public.retrieval_impressions impression
                       where impression.user_id = t.user_id and impression.thought_id = t.id
                         and impression.action = 'not_now'
                         and impression.created_at > now() - interval '30 days'
                   )::integer as recent_rejections
            from public.thoughts t
            left join public.user_calibration calibration on calibration.user_id = t.user_id
            where t.user_id = $1 and not t.is_deleted
            order by t.created_at desc, t.id
            limit 500
            """,
            user_id,
        )
        candidates: list[RetrievalCandidate] = []
        for row in rows:
            values = dict(row)
            embedding = values.get("embedding")
            if isinstance(embedding, Vector):
                values["embedding"] = embedding.to_list()
            candidates.append(RetrievalCandidate(**values))
        return candidates

    @staticmethod
    def _card(candidate: RetrievalCandidate, rank: int) -> RetrievalCard:
        return RetrievalCard(
            thought_id=candidate.id,
            rank=rank,
            refined_text=candidate.refined_text,
            kind=candidate.kind,
            commitment_strength=candidate.commitment_strength,
            duration_bucket=candidate.duration_bucket,
            energy=candidate.energy,
            contexts=candidate.contexts,
            open_loop=candidate.open_loop,
        )

    @staticmethod
    def _card_from_record(record: asyncpg.Record, rank: int) -> RetrievalCard:
        return RetrievalCard(
            thought_id=record["id"],
            rank=rank,
            refined_text=record["refined_text"],
            kind=record["kind"],
            commitment_strength=record["commitment_strength"],
            duration_bucket=record["duration_bucket"],
            energy=record["energy"],
            contexts=record["contexts"],
            open_loop=record["open_loop"],
        )

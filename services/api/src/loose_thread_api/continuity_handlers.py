from collections.abc import Awaitable, Callable

from loose_thread_api.agents.continuity import ContinuityOutput
from loose_thread_api.continuity_repository import ContinuityRepository
from loose_thread_api.embeddings import EmbeddingOutput
from loose_thread_api.models.jobs import Job
from loose_thread_api.orchestration.worker import JobHandlerError

Embed = Callable[[str], Awaitable[EmbeddingOutput]]
Relate = Callable[..., Awaitable[ContinuityOutput]]


class EmbeddingJobHandler:
    def __init__(
        self,
        *,
        repository: ContinuityRepository,
        embed: Embed,
        max_attempts: int,
    ) -> None:
        self._repository = repository
        self._embed = embed
        self._max_attempts = max_attempts

    async def __call__(self, job: Job) -> None:
        text = await self._repository.get_thought_text(
            user_id=job.user_id,
            thought_id=job.entity_id,
        )
        if text is None:
            raise JobHandlerError(
                "thought_not_embeddable",
                "Thought is missing or unavailable for embedding",
                retryable=False,
            )
        try:
            output = await self._embed(text)
            await self._repository.save_embedding_and_enqueue_link(
                job=job,
                output=output,
                max_attempts=self._max_attempts,
            )
        except Exception as exc:
            raise JobHandlerError(
                "embedding_failed",
                "Thought embedding failed",
                retryable=True,
            ) from exc


class ContinuityJobHandler:
    def __init__(
        self,
        *,
        repository: ContinuityRepository,
        relate: Relate,
        model: str,
        candidate_limit: int,
    ) -> None:
        self._repository = repository
        self._relate = relate
        self._model = model
        self._candidate_limit = candidate_limit

    async def __call__(self, job: Job) -> None:
        loaded = await self._repository.load_source_and_candidates(
            user_id=job.user_id,
            thought_id=job.entity_id,
            limit=self._candidate_limit,
        )
        if loaded is None:
            raise JobHandlerError(
                "thought_not_linkable",
                "Thought is missing or has no embedding",
                retryable=True,
            )
        thought, candidates = loaded
        run_id, started = await self._repository.start_agent_run(job=job, model=self._model)
        candidate_ids = {candidate.id for candidate in candidates}
        if not candidates:
            await self._repository.succeed_agent_run(
                run_id=run_id,
                job=job,
                output=None,
                candidate_ids=candidate_ids,
                started_monotonic=started,
            )
            return
        try:
            output = await self._relate(
                thought_id=thought.id,
                refined_text=thought.refined_text,
                kind=thought.kind,
                commitment_strength=thought.commitment_strength,
                candidates=candidates,
                correlation_id=str(job.correlation_id),
            )
            await self._repository.succeed_agent_run(
                run_id=run_id,
                job=job,
                output=output,
                candidate_ids=candidate_ids,
                started_monotonic=started,
            )
        except Exception as exc:
            await self._repository.fail_agent_run(
                run_id=run_id,
                started_monotonic=started,
                error_code=type(exc).__name__,
            )
            raise JobHandlerError(
                "continuity_failed",
                "Continuity analysis failed",
                retryable=True,
            ) from exc

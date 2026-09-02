import os
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest
from fastapi.testclient import TestClient

from loose_thread_api.agents.resumption import (
    ResumptionAgent,
    ResumptionEvidence,
    ResumptionOutput,
    ResumptionTelemetry,
)
from loose_thread_api.auth import AuthenticatedUser, get_current_user
from loose_thread_api.config import Settings
from loose_thread_api.db.pool import create_database_pool
from loose_thread_api.feedback_calibration import (
    CALIBRATION_VERSION,
    FeedbackCalibrationJobHandler,
    FeedbackCalibrationRepository,
)
from loose_thread_api.main import create_app
from loose_thread_api.models.jobs import Job
from loose_thread_api.models.resumption import ResumptionAgentResult
from loose_thread_api.models.retrievals import WindowLabel
from loose_thread_api.models.sessions import (
    FitFeedback,
    SessionComplete,
    SessionOutcome,
    SessionStart,
    SpawnThoughtCreate,
)
from loose_thread_api.resumption_service import ResumptionService
from loose_thread_api.sessions_repository import SessionRepository

USER = UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")


@pytest.fixture
async def database_pool() -> AsyncIterator[asyncpg.Pool]:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        pytest.skip("DATABASE_URL is required for Postgres integration tests")
    pool = await create_database_pool(database_url)
    await pool.execute("delete from auth.users where id = $1", USER)
    await pool.execute(
        "insert into auth.users (id,email) values ($1,'resumption@example.test')",
        USER,
    )
    try:
        yield pool
    finally:
        await pool.execute("delete from auth.users where id = $1", USER)
        await pool.close()


async def insert_thought(
    pool: asyncpg.Pool,
    text: str,
    *,
    is_open: bool = True,
) -> UUID:
    capture_id, thought_id = uuid4(), uuid4()
    await pool.execute(
        """
        insert into public.captures (
            id,user_id,device_id,idempotency_key,capture_mode,raw_text,
            timezone,client_created_at,processing_status
        ) values ($1,$2,$3,$4,'text',$5,'UTC',$6,'succeeded')
        """,
        capture_id,
        USER,
        uuid4(),
        f"session:{capture_id}",
        text,
        datetime.now(UTC),
    )
    await pool.execute(
        """
        insert into public.thoughts (
            id,user_id,capture_id,client_created_at,raw_fragment,refined_text,
            refined_source,kind,commitment_strength,surface_policy,duration_bucket,
            energy,open_loop
        ) values ($1,$2,$3,$4,$5,$5,'user_raw','unfinished','none','normal','session','medium',$6)
        """,
        thought_id,
        USER,
        capture_id,
        datetime.now(UTC),
        text,
        {"is_open": is_open},
    )
    return thought_id


async def test_grounded_resumption_uses_only_linked_evidence_and_audits_run(
    database_pool: asyncpg.Pool,
) -> None:
    selected = await insert_thought(database_pool, "Work out the launch demo story")
    linked = await insert_thought(database_pool, "The demo should prove capture survives failures")
    unlinked = await insert_thought(database_pool, "Private unrelated planning note")
    await database_pool.execute(
        """
        insert into public.thought_relationships (
            user_id,from_thought_id,to_thought_id,relation_type,confidence,source
        ) values ($1,$2,$3,'elaborates',0.95,'model')
        """,
        USER,
        selected,
        linked,
    )

    async def fake_resume(**kwargs: object) -> ResumptionOutput:
        evidence = kwargs["evidence"]
        assert isinstance(evidence, list)
        assert [item.id for item in evidence] == [linked]
        assert unlinked not in {item.id for item in evidence}
        return ResumptionOutput(
            result=ResumptionAgentResult(
                where_you_got_to="You decided the demo should prove capture survives failures.",
                supporting_thought_ids=[linked],
                unresolved_loop="The full demo story was still unresolved.",
                suggested_prompt="What should the next proof point be?",
            ),
            telemetry=ResumptionTelemetry(
                trace_id="trace_11111111111111111111111111111111",
                response_id="resp_resume_test",
                usage={"requests": 1, "input_tokens": 30, "output_tokens": 20, "total_tokens": 50},
            ),
        )

    response = await ResumptionService(
        database_pool,
        resume=fake_resume,
        model="test-model",
    ).get(user_id=USER, thought_id=selected)
    assert response is not None
    assert response.raw_fragment == "Work out the launch demo story"
    assert [item.id for item in response.supporting_thoughts] == [linked]
    run = await database_pool.fetchrow(
        "select status,openai_trace_id from public.agent_runs where id = $1",
        response.agent_run_id,
    )
    assert run is not None
    assert run["status"] == "succeeded"
    assert run["openai_trace_id"] == "trace_11111111111111111111111111111111"


async def test_insufficient_context_returns_original_without_calling_model(
    database_pool: asyncpg.Pool,
) -> None:
    selected = await insert_thought(database_pool, "A thought with no linked history")

    async def must_not_run(**_: object) -> ResumptionOutput:
        raise AssertionError("resumption model should not run without linked evidence")

    response = await ResumptionService(
        database_pool,
        resume=must_not_run,
        model="test-model",
    ).get(user_id=USER, thought_id=selected)
    assert response is not None
    assert response.raw_fragment == "A thought with no linked history"
    assert response.where_you_got_to is None
    assert response.supporting_thoughts == []
    assert response.agent_run_id is None


@pytest.mark.parametrize(
    ("outcome", "expected_status"),
    [
        (SessionOutcome.DONE, "done"),
        (SessionOutcome.PARTIAL, "active"),
        (SessionOutcome.STOPPED, "active"),
    ],
)
async def test_session_outcome_transitions(
    database_pool: asyncpg.Pool,
    outcome: SessionOutcome,
    expected_status: str,
) -> None:
    thought_id = await insert_thought(database_pool, f"Session thought for {outcome.value}")
    repository = SessionRepository(database_pool)
    session_id = uuid4()
    started = await repository.start(
        user_id=USER,
        body=SessionStart(
            id=session_id,
            thought_id=thought_id,
            window=WindowLabel.THIRTY,
            idempotency_key=f"start:{session_id}",
        ),
    )
    assert started.window is WindowLabel.THIRTY
    assert await database_pool.fetchval(
        "select status from public.thoughts where id = $1",
        thought_id,
    ) == "in_progress"

    completed = await repository.complete(
        user_id=USER,
        session_id=session_id,
        body=SessionComplete(
            outcome=outcome,
            fit=FitFeedback.RIGHT,
            actual_minutes=24,
            idempotency_key=f"complete:{session_id}",
        ),
    )
    duplicate = await repository.complete(
        user_id=USER,
        session_id=session_id,
        body=SessionComplete(
            outcome=outcome,
            fit=FitFeedback.RIGHT,
            actual_minutes=24,
            idempotency_key=f"complete:{session_id}",
        ),
    )
    assert completed == duplicate
    assert completed.ended_at is not None
    assert await database_pool.fetchval(
        "select status from public.thoughts where id = $1",
        thought_id,
    ) == expected_status


async def test_spawned_thought_and_relation_are_idempotent(
    database_pool: asyncpg.Pool,
) -> None:
    source_id = await insert_thought(database_pool, "Explore the demo narrative")
    repository = SessionRepository(database_pool)
    session_id = uuid4()
    await repository.start(
        user_id=USER,
        body=SessionStart(
            id=session_id,
            thought_id=source_id,
            window=WindowLabel.FIFTEEN,
            idempotency_key=f"start:{session_id}",
        ),
    )
    body = SpawnThoughtCreate(
        capture_id=uuid4(),
        thought_id=uuid4(),
        device_id=uuid4(),
        idempotency_key=f"spawn-capture:{session_id}",
        raw_text="The diagnostics should show grounded trace IDs",
        timezone="America/Toronto",
        client_created_at=datetime.now(UTC),
    )
    first = await repository.spawn(user_id=USER, session_id=session_id, body=body)
    second = await repository.spawn(user_id=USER, session_id=session_id, body=body)
    assert first == second
    assert await database_pool.fetchval(
        """
        select count(*) from public.thought_relationships
        where from_thought_id = $1 and to_thought_id = $2 and relation_type = 'spawned_from'
        """,
        first.thought_id,
        source_id,
    ) == 1
    assert await database_pool.fetchval(
        "select count(*) from public.jobs where entity_id = $1 and job_type = 'embed_thought'",
        first.thought_id,
    ) == 1
    assert await database_pool.fetchval(
        "select outcome from public.sessions where id = $1",
        session_id,
    ) == "spawned_new"


async def test_feedback_calibration_is_durable_and_replay_safe(
    database_pool: asyncpg.Pool,
) -> None:
    thought_id = await insert_thought(database_pool, "Calibrate this unfinished session")
    repository = SessionRepository(database_pool)
    session_id = uuid4()
    await repository.start(
        user_id=USER,
        body=SessionStart(
            id=session_id,
            thought_id=thought_id,
            window=WindowLabel.THIRTY,
            idempotency_key=f"start:{session_id}",
        ),
    )
    await repository.complete(
        user_id=USER,
        session_id=session_id,
        body=SessionComplete(
            outcome=SessionOutcome.DONE,
            fit=FitFeedback.RIGHT,
            actual_minutes=24,
            idempotency_key=f"complete:{session_id}",
        ),
    )

    record = await database_pool.fetchrow(
        """
        select job.*
        from public.jobs job
        join public.feedback_events feedback on feedback.id = job.entity_id
        where feedback.session_id = $1 and feedback.event_type = 'session_completed'
          and job.job_type = 'apply_feedback_calibration'
        """,
        session_id,
    )
    assert record is not None
    job = Job.from_record(record)
    handler = FeedbackCalibrationJobHandler(FeedbackCalibrationRepository(database_pool))

    await handler(job)
    await handler(job)

    calibration = await database_pool.fetchrow(
        "select * from public.user_calibration where user_id = $1",
        USER,
    )
    assert calibration is not None
    assert calibration["observation_count"] == 1
    assert calibration["kind_affinity"]["unfinished"] == 0.6
    assert calibration["duration_calibration"]["session"] == 0.05
    event = await database_pool.fetchrow(
        "select calibration_applied_at,calibration_version from public.feedback_events where id = $1",
        job.entity_id,
    )
    assert event is not None
    assert event["calibration_applied_at"] is not None
    assert event["calibration_version"] == CALIBRATION_VERSION
    visible_feedback = await FeedbackCalibrationRepository(
        database_pool
    ).list_feedback_for_user(user_id=USER)
    completion = next(item for item in visible_feedback if item.event_type == "session_completed")
    assert completion.id == job.entity_id
    assert completion.event_data["fit"] == "right"
    assert completion.calibration_version == CALIBRATION_VERSION

    app = create_app(Settings(database_url=os.environ["DATABASE_URL"]))

    async def override_user() -> AuthenticatedUser:
        return AuthenticatedUser(id=USER, is_anonymous=True)

    app.dependency_overrides[get_current_user] = override_user
    with TestClient(app) as client:
        response = client.get("/v1/debug/feedback")

    assert response.status_code == 200
    response_completion = next(
        item for item in response.json() if item["event_type"] == "session_completed"
    )
    assert response_completion["id"] == str(job.entity_id)
    assert response_completion["calibration_version"] == CALIBRATION_VERSION


def test_resumption_agent_rejects_unsupplied_evidence_id() -> None:
    supplied = uuid4()
    result = ResumptionAgentResult(
        where_you_got_to="Unsupported",
        supporting_thought_ids=[uuid4()],
    )
    with pytest.raises(ValueError, match="unsupplied"):
        ResumptionAgent._validate_ids(
            [
                ResumptionEvidence(
                    id=supplied,
                    refined_text="Supplied evidence",
                    relation_type="continues",
                )
            ],
            result,
        )

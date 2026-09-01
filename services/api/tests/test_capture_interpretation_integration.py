import os
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest
from fastapi.testclient import TestClient

from loose_thread_api.agents.handler import InterpretationJobHandler
from loose_thread_api.agents.interpreter import (
    InterpreterOutput,
    InterpreterTelemetry,
    ThoughtInterpreter,
)
from loose_thread_api.agents.repository import AgentRunRepository
from loose_thread_api.auth import AuthenticatedUser, get_current_user
from loose_thread_api.captures import CaptureRepository
from loose_thread_api.config import Settings
from loose_thread_api.db.pool import create_database_pool
from loose_thread_api.main import create_app
from loose_thread_api.models.captures import CaptureCreate, CaptureMode
from loose_thread_api.models.interpretation import (
    CommitmentStrength,
    Confidence,
    DurationBucket,
    Energy,
    Entities,
    InterpretationResult,
    InterpretedThought,
    OpenLoop,
    SurfacePolicy,
    Temporal,
    TemporalType,
    ThoughtKind,
)
from loose_thread_api.models.jobs import Job, JobStatus
from loose_thread_api.orchestration.repository import JobRepository
from loose_thread_api.orchestration.worker import JobHandlerError

USER_A = UUID("33333333-3333-4333-8333-333333333333")
USER_B = UUID("44444444-4444-4444-8444-444444444444")


@pytest.fixture
async def database_pool() -> AsyncIterator[asyncpg.Pool]:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        pytest.skip("DATABASE_URL is required for Postgres integration tests")

    pool = await create_database_pool(database_url)
    await pool.execute("delete from auth.users where id = any($1::uuid[])", [USER_A, USER_B])
    await pool.execute(
        """
        insert into auth.users (id, email)
        values ($1, 'capture-a@example.test'), ($2, 'capture-b@example.test')
        """,
        USER_A,
        USER_B,
    )
    try:
        yield pool
    finally:
        await pool.execute("delete from auth.users where id = any($1::uuid[])", [USER_A, USER_B])
        await pool.close()


def capture_payload(*, capture_id: UUID, idempotency_key: str, raw_text: str) -> dict[str, str]:
    return {
        "id": str(capture_id),
        "device_id": str(uuid4()),
        "idempotency_key": idempotency_key,
        "capture_mode": "text",
        "raw_text": raw_text,
        "timezone": "America/Toronto",
        "client_created_at": "2026-09-01T09:00:00-04:00",
    }


def interpreted_thought(
    *,
    raw_fragment: str,
    refined_text: str,
    kind: ThoughtKind = ThoughtKind.TASK,
    commitment: CommitmentStrength = CommitmentStrength.INTENDED,
    temporal: Temporal | None = None,
) -> InterpretedThought:
    return InterpretedThought(
        raw_fragment=raw_fragment,
        refined_text=refined_text,
        kind=kind,
        commitment_strength=commitment,
        duration_bucket=DurationBucket.SNACK,
        energy=Energy.MEDIUM,
        contexts=["computer"],
        entities=Entities(),
        temporal=temporal or Temporal(),
        open_loop=OpenLoop(is_open=kind is ThoughtKind.TASK, type="action"),
        surface_policy=SurfacePolicy.NORMAL,
        confidence=Confidence(
            kind=0.95,
            commitment_strength=0.8,
            duration_bucket=0.6,
            energy=0.5,
            surface_policy=0.9,
        ),
    )


def interpreter_output(*thoughts: InterpretedThought) -> InterpreterOutput:
    return InterpreterOutput(
        result=InterpretationResult(thoughts=list(thoughts)),
        telemetry=InterpreterTelemetry(
            trace_id="trace_0123456789abcdef0123456789abcdef",
            response_id="resp_test",
            usage={"requests": 1, "input_tokens": 50, "output_tokens": 25, "total_tokens": 75},
        ),
    )


async def create_and_claim(
    pool: asyncpg.Pool, *, raw_text: str, idempotency_key: str
) -> tuple[CaptureRepository, JobRepository, UUID, Job]:
    captures = CaptureRepository(pool)
    jobs = JobRepository(pool)
    capture_id = uuid4()
    await captures.create_with_job(
        user_id=USER_A,
        capture=CaptureCreate(
            id=capture_id,
            device_id=uuid4(),
            idempotency_key=idempotency_key,
            capture_mode=CaptureMode.TEXT,
            raw_text=raw_text,
            timezone="America/Toronto",
            client_created_at=datetime(2026, 9, 1, 9, 0, tzinfo=UTC),
        ),
        max_attempts=5,
    )
    claimed = await jobs.claim(worker_id="interpreter-test", limit=1, lease_seconds=60)
    assert len(claimed) == 1
    return captures, jobs, capture_id, claimed[0]


async def test_post_capture_is_idempotent_and_raw_is_persisted_first(
    database_pool: asyncpg.Pool,
) -> None:
    database_url = os.environ["DATABASE_URL"]
    app = create_app(Settings(database_url=database_url))

    async def override_user() -> AuthenticatedUser:
        return AuthenticatedUser(id=USER_A, is_anonymous=True)

    app.dependency_overrides[get_current_user] = override_user
    capture_id = uuid4()
    payload = capture_payload(
        capture_id=capture_id,
        idempotency_key="offline-device:42",
        raw_text="Maybe I should email Sam.",
    )
    with TestClient(app) as client:
        first = client.post("/v1/captures", json=payload)
        duplicate = client.post("/v1/captures", json=payload)

    assert first.status_code == 202
    assert duplicate.status_code == 202
    assert first.json()["id"] == duplicate.json()["id"] == str(capture_id)
    assert first.json()["job_id"] == duplicate.json()["job_id"]
    assert first.json()["created"] is True
    assert duplicate.json()["created"] is False
    row = await database_pool.fetchrow(
        "select raw_text, processing_status from public.captures where id = $1",
        capture_id,
    )
    assert row is not None
    assert row["raw_text"] == payload["raw_text"]
    assert row["processing_status"] == "queued"


async def test_interpreter_persists_multiple_thoughts_and_audits_run(
    database_pool: asyncpg.Pool,
) -> None:
    raw_text = "Email Sam about launch. Also research quiet keyboards."
    captures, jobs, capture_id, claimed = await create_and_claim(
        database_pool,
        raw_text=raw_text,
        idempotency_key="multi-thought",
    )

    async def fake_interpret(**_: str) -> InterpreterOutput:
        return interpreter_output(
            interpreted_thought(
                raw_fragment="Email Sam about launch.",
                refined_text="Email Sam about the launch",
            ),
            interpreted_thought(
                raw_fragment="research quiet keyboards.",
                refined_text="Research quiet keyboards",
                kind=ThoughtKind.RESEARCH,
                commitment=CommitmentStrength.CURIOSITY,
            ),
        )

    handler = InterpretationJobHandler(
        captures=captures,
        agent_runs=AgentRunRepository(database_pool),
        interpret=fake_interpret,
        model="test-model",
        max_attempts=5,
    )
    await handler(claimed)
    await jobs.complete(job_id=claimed.id, worker_id="interpreter-test")

    capture = await captures.get_for_user(user_id=USER_A, capture_id=capture_id)
    assert capture is not None
    assert capture.processing_status == "succeeded"
    assert [thought.kind for thought in capture.thoughts] == ["task", "research"]
    runs = await AgentRunRepository(database_pool).list_for_user(user_id=USER_A)
    assert len(runs) == 1
    assert runs[0]["status"] == "succeeded"
    assert runs[0]["openai_trace_id"] == "trace_0123456789abcdef0123456789abcdef"
    assert runs[0]["usage"]["total_tokens"] == 75


async def test_tentative_commitment_and_literal_date_survive_persistence(
    database_pool: asyncpg.Pool,
) -> None:
    raw_text = "Maybe email Sam tomorrow morning."
    captures, jobs, capture_id, claimed = await create_and_claim(
        database_pool,
        raw_text=raw_text,
        idempotency_key="tentative-date",
    )

    async def fake_interpret(**_: str) -> InterpreterOutput:
        return interpreter_output(
            interpreted_thought(
                raw_fragment=raw_text,
                refined_text="Maybe email Sam tomorrow morning",
                commitment=CommitmentStrength.POSSIBLE,
                temporal=Temporal(
                    literal="tomorrow morning",
                    type=TemporalType.RELATIVE_TIME,
                    resolved_at=datetime(2026, 9, 2, 9, 0, tzinfo=UTC),
                    source="explicit_user_statement",
                ),
            )
        )

    handler = InterpretationJobHandler(
        captures=captures,
        agent_runs=AgentRunRepository(database_pool),
        interpret=fake_interpret,
        model="test-model",
        max_attempts=5,
    )
    await handler(claimed)
    await jobs.complete(job_id=claimed.id, worker_id="interpreter-test")

    capture = await captures.get_for_user(user_id=USER_A, capture_id=capture_id)
    assert capture is not None
    thought = capture.thoughts[0]
    assert thought.commitment_strength == "possible"
    assert thought.temporal["literal"] == "tomorrow morning"
    assert thought.temporal["source"] == "explicit_user_statement"


async def test_malformed_interpreter_result_keeps_raw_capture_retryable(
    database_pool: asyncpg.Pool,
) -> None:
    raw_text = "Remember this exactly."
    captures, jobs, capture_id, claimed = await create_and_claim(
        database_pool,
        raw_text=raw_text,
        idempotency_key="malformed-output",
    )

    async def malformed_interpret(**_: str) -> InterpreterOutput:
        raise ValueError("invalid structured output")

    handler = InterpretationJobHandler(
        captures=captures,
        agent_runs=AgentRunRepository(database_pool),
        interpret=malformed_interpret,
        model="test-model",
        max_attempts=5,
    )
    with pytest.raises(JobHandlerError) as error:
        await handler(claimed)
    await jobs.fail(
        job_id=claimed.id,
        worker_id="interpreter-test",
        error_code=error.value.code,
        error_message=str(error.value),
        retry_delay_seconds=0,
        retryable=error.value.retryable,
    )

    row = await database_pool.fetchrow(
        """
        select c.raw_text, c.processing_status, j.status, j.last_error_code
        from public.captures c join public.jobs j on j.entity_id = c.id
        where c.id = $1
        """,
        capture_id,
    )
    assert row is not None
    assert row["raw_text"] == raw_text
    assert row["processing_status"] == "failed"
    assert row["status"] == JobStatus.RETRY_WAIT.value
    assert row["last_error_code"] == "interpreter_failed"


def test_provenance_validator_rejects_invented_fragment_or_date() -> None:
    raw_text = "Call Sam next week."
    invented_fragment = interpreter_output(
        interpreted_thought(raw_fragment="Call Alex", refined_text="Call Alex")
    ).result
    with pytest.raises(ValueError, match="raw fragment"):
        ThoughtInterpreter._validate_provenance(raw_text, invented_fragment)

    invented_date = interpreter_output(
        interpreted_thought(
            raw_fragment=raw_text,
            refined_text="Call Sam next week",
            temporal=Temporal(
                literal="on Friday",
                type=TemporalType.DEADLINE,
                source="explicit_user_statement",
            ),
        )
    ).result
    with pytest.raises(ValueError, match="temporal text"):
        ThoughtInterpreter._validate_provenance(raw_text, invented_date)


async def test_agent_run_debug_is_user_scoped_and_omits_sensitive_failures(
    database_pool: asyncpg.Pool,
) -> None:
    await database_pool.execute(
        """
        insert into public.agent_runs (
            user_id, agent_name, model, schema_version, prompt_version, status,
            input_entity_ids, output_entity_ids, correlation_id, completed_at,
            latency_ms, error_code, error_message
        )
        values
            ($1, 'thought_interpreter', 'test-model', '1.0', 'interpreter-v1',
             'failed', '[]'::jsonb, '[]'::jsonb, $3, now(), 1,
             'safe_code', 'private capture text'),
            ($2, 'resumption', 'test-model', '1.0', 'resumption-v1',
             'succeeded', '[]'::jsonb, '[]'::jsonb, $4, now(), 1, null, null)
        """,
        USER_A,
        USER_B,
        uuid4(),
        uuid4(),
    )
    app = create_app(Settings(database_url=os.environ["DATABASE_URL"]))

    async def override_user() -> AuthenticatedUser:
        return AuthenticatedUser(id=USER_A, is_anonymous=True)

    app.dependency_overrides[get_current_user] = override_user
    with TestClient(app) as client:
        response = client.get("/v1/debug/agent-runs")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["agent_name"] == "thought_interpreter"
    assert payload[0]["error_code"] == "safe_code"
    assert "error_message" not in payload[0]
    assert "private capture text" not in response.text

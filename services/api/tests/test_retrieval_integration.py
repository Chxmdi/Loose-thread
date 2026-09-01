import os
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import asyncpg
import pytest
from fastapi.testclient import TestClient

from loose_thread_api.auth import AuthenticatedUser, get_current_user
from loose_thread_api.config import Settings
from loose_thread_api.db.pool import create_database_pool
from loose_thread_api.main import create_app
from loose_thread_api.models.retrievals import RetrievalCreate, WindowLabel
from loose_thread_api.retrieval.engine import RANKING_VERSION, RetrievalEngine
from loose_thread_api.retrieval.repository import RetrievalConflictError, RetrievalRepository

USER_A = UUID("99999999-9999-4999-8999-999999999999")
USER_B = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")


@pytest.fixture
async def database_pool() -> AsyncIterator[asyncpg.Pool]:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        pytest.skip("DATABASE_URL is required for Postgres integration tests")
    pool = await create_database_pool(database_url)
    await pool.execute("delete from auth.users where id = any($1::uuid[])", [USER_A, USER_B])
    await pool.execute(
        "insert into auth.users (id,email) values ($1,'retrieval-a@example.test'),($2,'retrieval-b@example.test')",
        USER_A,
        USER_B,
    )
    try:
        yield pool
    finally:
        await pool.execute("delete from auth.users where id = any($1::uuid[])", [USER_A, USER_B])
        await pool.close()


async def insert_thought(
    pool: asyncpg.Pool,
    index: int,
    *,
    user_id: UUID = USER_A,
    embedding: list[float] | None = None,
) -> UUID:
    capture_id, thought_id = uuid4(), uuid4()
    text = f"Open loop number {index} for the Thursday demo"
    created_at = datetime.now(UTC) - timedelta(days=10 + index)
    await pool.execute(
        """
        insert into public.captures (
            id,user_id,device_id,idempotency_key,capture_mode,raw_text,
            timezone,client_created_at,processing_status
        ) values ($1,$2,$3,$4,'text',$5,'UTC',$6,'succeeded')
        """,
        capture_id,
        user_id,
        uuid4(),
        f"retrieval:{capture_id}",
        text,
        created_at,
    )
    await pool.execute(
        """
        insert into public.thoughts (
            id,user_id,capture_id,client_created_at,raw_fragment,refined_text,
            refined_source,kind,commitment_strength,surface_policy,duration_bucket,
            energy,contexts,open_loop,confidence,created_at
        ) values (
            $1,$2,$3,$4,$5,$5,'user_raw',$6,'intended','normal','session',
            'medium',$7,'{"is_open":true}',$8,$4
        )
        """,
        thought_id,
        user_id,
        capture_id,
        created_at,
        text,
        "research" if index % 2 else "task",
        ["home"] if index % 2 else ["anywhere"],
        {"contexts": 0.9, "energy": 0.9},
    )
    if embedding is not None:
        await pool.execute(
            "update public.thoughts set embedding = $2 where id = $1",
            thought_id,
            embedding,
        )
    return thought_id


async def test_api_returns_at_most_three_and_persists_all_candidate_scores(
    database_pool: asyncpg.Pool,
) -> None:
    for index in range(5):
        await insert_thought(database_pool, index)
    await insert_thought(database_pool, 99, user_id=USER_B)
    app = create_app(Settings(database_url=os.environ["DATABASE_URL"]))

    async def override_user() -> AuthenticatedUser:
        return AuthenticatedUser(id=USER_A, is_anonymous=True)

    app.dependency_overrides[get_current_user] = override_user
    retrieval_id = uuid4()
    with TestClient(app) as client:
        response = client.post(
            "/v1/retrievals",
            json={
                "id": str(retrieval_id),
                "window": "a while",
                "contexts": {"home": True},
            },
        )
        duplicate = client.post(
            "/v1/retrievals",
            json={
                "id": str(retrieval_id),
                "window": "a while",
                "contexts": {"home": True},
            },
        )
        debug = client.get(f"/v1/debug/retrievals/{retrieval_id}")

    assert response.status_code == 201
    assert duplicate.status_code == 201
    payload = response.json()
    assert payload == duplicate.json()
    assert payload["ranking_version"] == RANKING_VERSION
    assert 1 <= len(payload["cards"]) <= 3
    assert payload["candidate_count"] == 5
    assert debug.status_code == 200
    assert len(debug.json()["impressions"]) == 5
    assert all(item["score_components"] for item in debug.json()["impressions"])


async def test_database_vectors_are_normalized_for_duplicate_suppression(
    database_pool: asyncpg.Pool,
) -> None:
    embedding = [1.0, *([0.0] * 1535)]
    await insert_thought(database_pool, 1, embedding=embedding)
    await insert_thought(database_pool, 2, embedding=embedding)

    result = await RetrievalRepository(database_pool).create(
        user_id=USER_A,
        request=RetrievalCreate(id=uuid4(), window=WindowLabel.A_WHILE),
        engine=RetrievalEngine(),
    )

    assert result.candidate_count == 2
    assert len(result.cards) == 1


async def test_one_reshuffle_cap_and_original_cards_are_excluded(
    database_pool: asyncpg.Pool,
) -> None:
    for index in range(8):
        await insert_thought(database_pool, index)
    repository = RetrievalRepository(database_pool)
    engine = RetrievalEngine()
    original = await repository.create(
        user_id=USER_A,
        request=RetrievalCreate(id=uuid4(), window=WindowLabel.A_WHILE),
        engine=engine,
    )
    reshuffled = await repository.create_reshuffle(
        user_id=USER_A,
        retrieval_id=original.id,
        new_id=uuid4(),
        engine=engine,
    )
    assert {card.thought_id for card in original.cards}.isdisjoint(
        {card.thought_id for card in reshuffled.cards}
    )

    with pytest.raises(RetrievalConflictError, match="already been reshuffled"):
        await repository.create_reshuffle(
            user_id=USER_A,
            retrieval_id=original.id,
            new_id=uuid4(),
            engine=engine,
        )
    with pytest.raises(RetrievalConflictError, match="cannot be reshuffled"):
        await repository.create_reshuffle(
            user_id=USER_A,
            retrieval_id=reshuffled.id,
            new_id=uuid4(),
            engine=engine,
        )

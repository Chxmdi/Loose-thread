import json

import asyncpg
from pgvector.asyncpg import register_vector


async def configure_connection(connection: asyncpg.Connection) -> None:
    await register_vector(connection, schema="extensions")
    await connection.set_type_codec(
        "json",
        schema="pg_catalog",
        encoder=json.dumps,
        decoder=json.loads,
        format="text",
    )
    await connection.set_type_codec(
        "jsonb",
        schema="pg_catalog",
        encoder=json.dumps,
        decoder=json.loads,
        format="text",
    )


async def create_database_pool(database_url: str) -> asyncpg.Pool:
    return await asyncpg.create_pool(
        dsn=database_url,
        min_size=1,
        max_size=10,
        command_timeout=30,
        init=configure_connection,
    )

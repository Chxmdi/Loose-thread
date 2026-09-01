from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import asyncpg
import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from loose_thread_api.auth import SupabaseAuthClient
from loose_thread_api.config import Settings, get_settings
from loose_thread_api.db.pool import create_database_pool
from loose_thread_api.routes.captures import router as captures_router
from loose_thread_api.routes.debug import router as debug_router
from loose_thread_api.routes.retrievals import router as retrievals_router
from loose_thread_api.routes.sessions import router as sessions_router
from loose_thread_api.routes.thoughts import router as thoughts_router


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        database_pool: asyncpg.Pool | None = None
        http_client = httpx.AsyncClient()
        app.state.database_pool = None
        app.state.auth_client = None
        app.state.settings = resolved_settings

        if resolved_settings.database_url is not None:
            database_pool = await create_database_pool(
                resolved_settings.database_url.get_secret_value()
            )
            app.state.database_pool = database_pool
        if (
            resolved_settings.supabase_url is not None
            and resolved_settings.supabase_anon_key is not None
        ):
            app.state.auth_client = SupabaseAuthClient(resolved_settings, http_client)

        try:
            yield
        finally:
            await http_client.aclose()
            if database_pool is not None:
                await database_pool.close()

    application = FastAPI(title="Loose Thread API", version="0.1.0", lifespan=lifespan)
    allowed_origins = resolved_settings.allowed_cors_origins()
    if allowed_origins:
        application.add_middleware(
            CORSMiddleware,
            allow_origins=allowed_origins,
            allow_credentials=True,
            allow_methods=["GET", "POST", "OPTIONS"],
            allow_headers=["Authorization", "Content-Type"],
        )
    application.include_router(captures_router)
    application.include_router(retrievals_router)
    application.include_router(sessions_router)
    application.include_router(thoughts_router)
    application.include_router(debug_router)

    @application.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "service": "loose-thread-api"}

    return application


app = create_app()

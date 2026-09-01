from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

import httpx
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from loose_thread_api.config import Settings

bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class AuthenticatedUser:
    id: UUID
    is_anonymous: bool


class SupabaseAuthClient:
    def __init__(self, settings: Settings, client: httpx.AsyncClient) -> None:
        if settings.supabase_url is None or settings.supabase_anon_key is None:
            raise ValueError("SUPABASE_URL and SUPABASE_ANON_KEY are required for authentication")
        self._user_url = f"{str(settings.supabase_url).rstrip('/')}/auth/v1/user"
        self._api_key = settings.supabase_anon_key.get_secret_value()
        self._client = client

    async def authenticate(self, token: str) -> AuthenticatedUser:
        try:
            response = await self._client.get(
                self._user_url,
                headers={
                    "apikey": self._api_key,
                    "Authorization": f"Bearer {token}",
                },
                timeout=10.0,
            )
        except httpx.HTTPError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Authentication service unavailable",
            ) from exc

        if response.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired access token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        if response.is_error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Authentication service unavailable",
            )

        payload = response.json()
        try:
            user_id = UUID(str(payload["id"]))
        except (KeyError, TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Authentication service returned an invalid user",
            ) from exc
        return AuthenticatedUser(
            id=user_id,
            is_anonymous=bool(payload.get("is_anonymous", False)),
        )


async def get_current_user(
    request: Request,
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_scheme),
    ],
) -> AuthenticatedUser:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer access token required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    auth_client = getattr(request.app.state, "auth_client", None)
    if not isinstance(auth_client, SupabaseAuthClient):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication is not configured",
        )
    return await auth_client.authenticate(credentials.credentials)

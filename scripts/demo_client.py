from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class DemoEnvironment:
    api_url: str
    supabase_url: str
    anon_key: str
    service_role_key: str | None
    timeout_seconds: float

    @classmethod
    def load(cls) -> DemoEnvironment:
        load_dotenv(ROOT / ".env", override=False)
        values = {
            "SUPABASE_URL": os.getenv("DEMO_SUPABASE_URL") or os.getenv("SUPABASE_URL"),
            "SUPABASE_ANON_KEY": os.getenv("DEMO_SUPABASE_ANON_KEY")
            or os.getenv("SUPABASE_PUBLISHABLE_KEY")
            or os.getenv("SUPABASE_ANON_KEY")
            or os.getenv("EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY"),
        }
        missing = [name for name, value in values.items() if not value]
        if missing:
            raise RuntimeError(f"Missing demo environment: {', '.join(missing)}")
        return cls(
            api_url=(
                os.getenv("DEMO_API_URL")
                or os.getenv("EXPO_PUBLIC_API_URL")
                or "http://127.0.0.1:8000"
            ).rstrip("/"),
            supabase_url=str(values["SUPABASE_URL"]).rstrip("/"),
            anon_key=str(values["SUPABASE_ANON_KEY"]),
            service_role_key=os.getenv("SUPABASE_SECRET_KEY")
            or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
            or None,
            timeout_seconds=float(os.getenv("DEMO_TIMEOUT_SECONDS", "240")),
        )


class DemoClient:
    def __init__(self, environment: DemoEnvironment) -> None:
        self.environment = environment
        self._http = httpx.Client(timeout=30)
        self.access_token: str | None = None
        self.user_id: str | None = None

    def close(self) -> None:
        self._http.close()

    def health(self) -> dict[str, Any]:
        response = self._http.get(f"{self.environment.api_url}/health")
        response.raise_for_status()
        return response.json()

    def sign_in_anonymously(self) -> None:
        response = self._http.post(
            f"{self.environment.supabase_url}/auth/v1/signup",
            headers={"apikey": self.environment.anon_key},
            json={"data": {}},
        )
        response.raise_for_status()
        body = response.json()
        self.access_token = body["access_token"]
        self.user_id = body["user"]["id"]

    def use_session(self, *, access_token: str, user_id: str) -> None:
        self.access_token = access_token
        self.user_id = user_id

    def api(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        expected: int | tuple[int, ...] = (200, 201, 202, 204),
    ) -> Any:
        if self.access_token is None:
            raise RuntimeError("Demo client is not authenticated")
        response = self._http.request(
            method,
            f"{self.environment.api_url}{path}",
            headers={"Authorization": f"Bearer {self.access_token}"},
            json=json,
        )
        expected_codes = (expected,) if isinstance(expected, int) else expected
        if response.status_code not in expected_codes:
            raise RuntimeError(
                f"{method} {path} failed ({response.status_code}): {response.text[:300]}"
            )
        return None if response.status_code == 204 else response.json()

    def rest(self, table: str, *, params: dict[str, str]) -> list[dict[str, Any]]:
        if self.access_token is None:
            raise RuntimeError("Demo client is not authenticated")
        response = self._http.get(
            f"{self.environment.supabase_url}/rest/v1/{table}",
            headers={
                "apikey": self.environment.anon_key,
                "Authorization": f"Bearer {self.access_token}",
            },
            params=params,
        )
        response.raise_for_status()
        return response.json()

    def create_capture(self, raw_text: str) -> tuple[str, dict[str, Any]]:
        capture_id = str(uuid4())
        response = self.api(
            "POST",
            "/v1/captures",
            json={
                "id": capture_id,
                "device_id": str(uuid4()),
                "idempotency_key": f"demo-capture:{capture_id}",
                "capture_mode": "text",
                "raw_text": raw_text,
                "timezone": "UTC",
                "client_created_at": "2026-09-01T18:00:00Z",
            },
            expected=202,
        )
        persisted = self.api("GET", f"/v1/captures/{capture_id}", expected=200)
        if persisted["raw_text"] != raw_text:
            raise RuntimeError("Raw capture was not retained before enrichment")
        return capture_id, response

    def wait_capture(self, capture_id: str) -> dict[str, Any]:
        return self.wait_for(
            f"capture {capture_id}",
            lambda: self.api("GET", f"/v1/captures/{capture_id}", expected=200),
            lambda body: body["processing_status"] == "succeeded" and bool(body["thoughts"]),
        )

    def wait_jobs(self) -> list[dict[str, Any]]:
        terminal = {"succeeded", "dead"}
        jobs = self.wait_for(
            "durable jobs",
            lambda: self.api("GET", "/v1/debug/jobs", expected=200),
            lambda rows: bool(rows) and all(row["status"] in terminal for row in rows),
        )
        failed = [row for row in jobs if row["status"] != "succeeded"]
        if failed:
            codes = [row.get("last_error_code") for row in failed]
            raise RuntimeError(f"Durable jobs did not succeed: {codes}")
        return jobs

    def wait_for(self, label: str, fetch: Any, ready: Any) -> Any:
        deadline = time.monotonic() + self.environment.timeout_seconds
        last: Any = None
        while time.monotonic() < deadline:
            last = fetch()
            if ready(last):
                return last
            time.sleep(1)
        raise RuntimeError(f"Timed out waiting for {label}; last state={str(last)[:500]}")

    def delete_user(self, user_id: str) -> None:
        service_key = self.environment.service_role_key
        if not service_key:
            raise RuntimeError("SUPABASE_SERVICE_ROLE_KEY is required to reset demo data")
        headers = {"apikey": service_key}
        if not service_key.startswith("sb_secret_"):
            headers["Authorization"] = f"Bearer {service_key}"
        response = self._http.delete(
            f"{self.environment.supabase_url}/auth/v1/admin/users/{user_id}",
            headers=headers,
        )
        response.raise_for_status()

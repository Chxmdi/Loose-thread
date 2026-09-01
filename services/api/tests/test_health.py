import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from loose_thread_api.config import Settings
from loose_thread_api.main import app


def test_health() -> None:
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "loose-thread-api"}


def test_production_settings_name_every_missing_credential(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name in (
        "DATABASE_URL",
        "SUPABASE_URL",
        "SUPABASE_PUBLISHABLE_KEY",
        "SUPABASE_ANON_KEY",
        "OPENAI_API_KEY",
    ):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(ValidationError) as error:
        Settings(environment="production", _env_file=None)

    message = str(error.value)
    assert "DATABASE_URL" in message
    assert "SUPABASE_URL" in message
    assert "SUPABASE_PUBLISHABLE_KEY" in message
    assert "OPENAI_API_KEY" in message


def test_production_settings_accept_complete_service_configuration() -> None:
    settings = Settings(
        environment="production",
        database_url="postgresql://example.test/database",
        supabase_url="https://example.supabase.co",
        supabase_anon_key="public-key",
        openai_api_key="server-key",
        cors_origins="https://demo.example, https://preview.example",
        port=9123,
        _env_file=None,
    )

    assert settings.port == 9123
    assert settings.allowed_cors_origins() == [
        "https://demo.example",
        "https://preview.example",
    ]


def test_modern_supabase_publishable_key_alias_is_supported() -> None:
    settings = Settings(
        supabase_publishable_key="sb_publishable_test",
        _env_file=None,
    )

    assert settings.supabase_anon_key is not None
    assert settings.supabase_anon_key.get_secret_value() == "sb_publishable_test"

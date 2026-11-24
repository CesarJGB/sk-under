from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.settings import Settings

ORIGIN = "http://127.0.0.1:5173"


def make_client(**options) -> TestClient:
    settings = Settings(_env_file=None, **options)
    return TestClient(
        create_app(settings),
        base_url="http://127.0.0.1:8000",
        client=("127.0.0.1", 50000),
    )


@pytest.fixture
def client(monkeypatch) -> TestClient:
    for variable in (
        "SK_ENV", "SK_ACCESS_TOKEN", "SK_MAX_FILE_BYTES", "SK_ALLOWED_ORIGINS",
        "SK_SAVE_GENERAL_KEY_HEX", "SK_SAVE_STATISTICS_KEY_HEX", "SK_SAVE_IV_HEX",
        "SK_CLOUD_SESSION_TOKEN", "SK_CLOUD_UNIQUE_ID", "SK_CLOUD_DISTRO_ID",
        "SK_CLOUD_ADMIN_TOKEN", "SK_CLOUD_WRITE_ENABLED", "SK_CLOUD_BACKUP_DIR",
        "SK_NATIVE_AUTH_ENABLED", "SK_NATIVE_WRITE_ENABLED", "SK_NATIVE_STORE_KEY",
        "SK_NATIVE_STORE_DIR", "SK_NATIVE_BACKUP_DIR", "SK_NATIVE_BACKUP_KEY",
        "SK_NATIVE_ORIGIN", "SK_NATIVE_AUTO_IDENTITY", "SK_NATIVE_AUTO_ALLOW_WRITE",
        "SK_NATIVE_PORTAL_ENABLED",
        "SK_NATIVE_TRUSTED_PROXIES", "SK_NATIVE_DISTRO_ID", "SK_NATIVE_UNIQUE_ID",
        "SK_NATIVE_PROFILE_LABEL",
        "SK_NATIVE_PROFILE_ALLOW_WRITE", "SK_NATIVE_IDLE_SECONDS",
        "SK_NATIVE_ABSOLUTE_SECONDS", "SK_NATIVE_LOGIN_ATTEMPTS",
        "SK_NATIVE_LOGIN_WINDOW_SECONDS",
    ):
        monkeypatch.delenv(variable, raising=False)
    return make_client(env="development", allowed_origins=[ORIGIN])


@pytest.fixture
def fixture_path() -> Path:
    return Path(__file__).parent / "fixtures" / "sintetico.skdemo"


@pytest.fixture
def original(fixture_path: Path) -> bytes:
    return fixture_path.read_bytes()


@pytest.fixture
def legacy_gems_policy(monkeypatch):
    """Exercise the legacy backup/upload mechanics against a fake provider.

    Tests for the current write policy use the unmodified production path.
    There is no equivalent switch in the application.
    """
    monkeypatch.setattr("app.cloud.gems_editor.validate_gems_transition", lambda document, target: None)

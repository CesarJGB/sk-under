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
    ):
        monkeypatch.delenv(variable, raising=False)
    return make_client(env="development", allowed_origins=[ORIGIN])


@pytest.fixture
def fixture_path() -> Path:
    return Path(__file__).parent / "fixtures" / "sintetico.skdemo"


@pytest.fixture
def original(fixture_path: Path) -> bytes:
    return fixture_path.read_bytes()

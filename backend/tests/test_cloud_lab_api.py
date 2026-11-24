import json
from hashlib import sha256
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.cloud.backup_store import LabBackupStore
from app.cloud.lab_service import CloudLabService
from app.cloud.provider import (
    AcquiredCloudSave,
    CloudProviderUnauthenticated,
    CloudProviderUnavailable,
    CloudSaveMetadata,
)
from app.main import create_app
from app.settings import Settings
from conftest import ORIGIN, make_client

V1 = "/api/v1"
LAB = V1 + "/cloud/lab"
ACCESS = "t" * 32
ADMIN = "a" * 32
FIXTURE = Path(__file__).parent / "fixtures" / "cloud-save-gems.json"


def canonical(document: dict) -> bytes:
    return json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(", ", ": ")).encode()


class FakeProvider:
    def __init__(self, payload: bytes):
        self.payload = payload
        self.calls = 0

    def download(self, limit=8 * 1024 * 1024):
        self.calls += 1
        metadata = CloudSaveMetadata(
            "fake-remote", len(self.payload), sha256(self.payload).hexdigest(), source="modern-cloud"
        )
        return AcquiredCloudSave(metadata, self.payload)


class FakeUpload:
    status = 200
    accepted = True


class FakeUploader:
    def __init__(self, provider: FakeProvider):
        self.provider = provider
        self.calls: list[bytes] = []

    def upload(self, aggregate: bytes):
        self.calls.append(aggregate)
        self.provider.payload = aggregate
        return FakeUpload()


def lab_client(tmp_path: Path, *, write=True, admin=True, uploader=True):
    provider = FakeProvider(FIXTURE.read_bytes())
    fake_uploader = FakeUploader(provider) if uploader else None
    service = CloudLabService(
        provider,
        LabBackupStore(tmp_path / "backups"),
        uploader=fake_uploader,
        write_enabled=write,
        admin_configured=admin,
    )
    settings = Settings(
        _env_file=None,
        env="production",
        access_token=ACCESS,
        allowed_origins=[ORIGIN],
        cloud_write_enabled=write,
        cloud_admin_token=ADMIN if admin else None,
    )
    app = create_app(settings)
    app.state.cloud_lab = service
    client = TestClient(app, base_url="http://127.0.0.1:8000", client=("127.0.0.1", 50000))
    return client, provider, fake_uploader


def auth(token=ACCESS):
    return {"Authorization": f"Bearer {token}"}


def admin_header(token=ADMIN):
    return {"X-SK-Cloud-Admin": token}


def assert_error(response, status, code):
    assert response.status_code == status, response.text
    assert response.headers["Cache-Control"] == "no-store"
    error = response.json()["error"]
    assert error["code"] == code
    return error


def test_lab_defaults_to_disabled_without_credentials(client):
    status = client.get(LAB + "/status")
    assert status.status_code == 200
    assert status.headers["Cache-Control"] == "no-store"
    body = status.json()
    assert body["mode"] == "disabled"
    assert body["read_ready"] is False
    assert body["write_enabled"] is False
    assert body["write_ready"] is False
    assert body["min_gems"] == 0 and body["max_gems"] == 2_147_483_647


def test_lab_requires_the_existing_access_token():
    production = make_client(env="production", access_token=ACCESS)
    denied = production.get(LAB + "/status")
    assert_error(denied, 401, "access_denied")
    assert production.get(LAB + "/status", headers=auth()).status_code == 200
    assert_error(production.get(LAB + "/save"), 401, "access_denied")
    assert_error(production.get(LAB + "/save", headers=auth()), 503, "cloud_lab_not_configured")


def test_load_and_prepare_real_flow_without_network(tmp_path):
    client, provider, _ = lab_client(tmp_path)
    loaded = client.get(LAB + "/save", headers=auth())
    assert loaded.status_code == 200, loaded.text
    assert loaded.json()["gems"] == 1000
    assert loaded.json()["remote"]["source"] == "modern-cloud"
    assert provider.calls == 1

    prepared = client.post(LAB + "/prepare", headers=auth(), json={"new_gems": 1001})
    assert prepared.status_code == 200, prepared.text
    body = prepared.json()
    assert body["changed"] is True
    assert body["original_gems"] == 1000 and body["new_gems"] == 1001
    assert body["changed_fields"] == ["gameData.gems", "gameData.varGems"]
    assert body["validation"] == {
        "valid": True,
        "structure_valid": True,
        "only_gems_changed": False,
        "message": "Campos modificados: gameData.gems, gameData.varGems.",
    }
    assert body["backup"]["original_sha256"] == sha256(FIXTURE.read_bytes()).hexdigest()
    backup_dir = tmp_path / "backups" / body["backup"]["id"]
    assert (backup_dir / "original.json").read_bytes() == FIXTURE.read_bytes()
    assert json.loads((backup_dir / "candidate.json").read_text())["gameData"]["gems"] == 1001
    assert "cloudSaveId" not in prepared.text and "sintetico-cuenta-gemas" not in prepared.text

    backups = client.get(LAB + "/backups", headers=auth())
    assert backups.status_code == 200
    assert [item["id"] for item in backups.json()["backups"]] == [body["backup"]["id"]]


def test_confirm_requires_admin_header_and_phrase(tmp_path):
    client, _, uploader = lab_client(tmp_path)
    prepared = client.post(LAB + "/prepare", headers=auth(), json={"new_gems": 1001}).json()
    url = LAB + "/confirm"
    payload = {
        "backup_id": prepared["backup"]["id"],
        "expected_sha256": prepared["candidate_sha256"],
        "confirmation": "SUBIR",
    }
    assert_error(client.post(url, headers=auth(), json=payload), 403, "cloud_admin_denied")
    assert_error(
        client.post(url, headers=auth() | admin_header("b" * 32), json=payload),
        403,
        "cloud_admin_denied",
    )
    assert_error(
        client.post(url, headers=auth() | admin_header(), json={**payload, "confirmation": "subir"}),
        422,
        "invalid_request",
    )
    assert uploader.calls == []
    assert_error(
        client.post(url, headers=auth() | admin_header(), json={**payload, "expected_sha256": "0" * 64}),
        422,
        "cloud_hash_mismatch",
    )
    assert uploader.calls == []


def test_confirm_persists_and_verifies_then_restores(tmp_path):
    client, provider, uploader = lab_client(tmp_path)
    prepared = client.post(LAB + "/prepare", headers=auth(), json={"new_gems": 1001}).json()
    confirmed = client.post(
        LAB + "/confirm",
        headers=auth() | admin_header(),
        json={
            "backup_id": prepared["backup"]["id"],
            "expected_sha256": prepared["candidate_sha256"],
            "confirmation": "SUBIR",
        },
    )
    assert confirmed.status_code == 200, confirmed.text
    body = confirmed.json()
    assert body["uploaded"] is True and body["accepted"] is True and body["persisted"] is True
    assert body["remote_gems"] == 1001
    assert len(uploader.calls) == 1
    assert json.loads(uploader.calls[0])["gameData"]["gems"] == 1001
    assert "sintetico-cuenta-gemas" not in confirmed.text

    verified = client.post(
        LAB + "/verify", headers=auth(), json={"backup_id": prepared["backup"]["id"]}
    )
    assert verified.status_code == 200, verified.text
    assert verified.json()["matches_candidate"] is True
    assert verified.json()["remote_gems"] == 1001

    restored = client.post(
        LAB + "/restore",
        headers=auth() | admin_header(),
        json={"backup_id": prepared["backup"]["id"], "confirmation": "RESTAURAR"},
    )
    assert restored.status_code == 200, restored.text
    assert restored.json()["persisted"] is True
    assert restored.json()["remote_gems"] == 1000
    assert provider.payload == FIXTURE.read_bytes()


def test_confirm_rejects_noop_and_remote_changes(tmp_path):
    client, provider, uploader = lab_client(tmp_path)
    noop = client.post(LAB + "/prepare", headers=auth(), json={"new_gems": 1000}).json()
    response = client.post(
        LAB + "/confirm",
        headers=auth() | admin_header(),
        json={
            "backup_id": noop["backup"]["id"],
            "expected_sha256": noop["candidate_sha256"],
            "confirmation": "SUBIR",
        },
    )
    assert_error(response, 409, "cloud_no_changes")
    assert uploader.calls == []

    changed = client.post(LAB + "/prepare", headers=auth(), json={"new_gems": 1001}).json()
    document = json.loads(FIXTURE.read_bytes())
    document["gameData"]["gems"] = 5000
    provider.payload = canonical(document)
    response = client.post(
        LAB + "/confirm",
        headers=auth() | admin_header(),
        json={
            "backup_id": changed["backup"]["id"],
            "expected_sha256": changed["candidate_sha256"],
            "confirmation": "SUBIR",
        },
    )
    assert_error(response, 409, "cloud_remote_changed")
    assert uploader.calls == []


def test_write_disabled_and_admin_missing_fail_closed(tmp_path):
    client, _, _ = lab_client(tmp_path, write=False, uploader=False)
    prepared = client.post(LAB + "/prepare", headers=auth(), json={"new_gems": 1001}).json()
    response = client.post(
        LAB + "/confirm",
        headers=auth() | admin_header(),
        json={
            "backup_id": prepared["backup"]["id"],
            "expected_sha256": prepared["candidate_sha256"],
            "confirmation": "SUBIR",
        },
    )
    assert_error(response, 503, "cloud_write_disabled")

    no_admin, _, _ = lab_client(tmp_path / "other", admin=False)
    response = no_admin.post(
        LAB + "/confirm",
        headers=auth(),
        json={
            "backup_id": prepared["backup"]["id"],
            "expected_sha256": prepared["candidate_sha256"],
            "confirmation": "SUBIR",
        },
    )
    assert_error(response, 503, "cloud_admin_not_configured")


def test_invalid_values_and_bodies_are_rejected(tmp_path):
    client, _, uploader = lab_client(tmp_path)
    for value in (-1, 2_147_483_648, True, "1001", 1001.0, None):
        response = client.post(LAB + "/prepare", headers=auth(), json={"new_gems": value})
        assert response.status_code == 422, (value, response.text)
    assert uploader.calls == []
    assert client.post(LAB + "/prepare", headers=auth(), json={"new_gems": 1001, "extra": 1}).status_code == 422


def test_bad_backup_ids_are_rejected(tmp_path):
    client, _, _ = lab_client(tmp_path)
    for backup_id in ("../" + "0" * 32, "0" * 31, "g" * 32):
        response = client.post(LAB + "/verify", headers=auth(), json={"backup_id": backup_id})
        assert response.status_code == 422, (backup_id, response.text)
    assert client.post(LAB + "/verify", headers=auth(), json={"backup_id": "0" * 32}).status_code == 404


def test_cors_allows_the_admin_header(client):
    preflight = client.options(
        LAB + "/confirm",
        headers={
            "Origin": ORIGIN,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type,x-sk-cloud-admin",
        },
    )
    assert preflight.status_code == 200
    assert preflight.headers["Access-Control-Allow-Origin"] == ORIGIN
    assert "x-sk-cloud-admin" in preflight.headers["Access-Control-Allow-Headers"].lower()


def test_openapi_documents_the_guarded_flow(client):
    schema = client.get("/openapi.json").json()
    for operation in ("/save", "/prepare", "/confirm", "/restore", "/verify", "/backups", "/status"):
        assert LAB + operation in schema["paths"]
    confirm = schema["paths"][LAB + "/confirm"]["post"]
    security = confirm["security"]
    assert {"EditorBearer": []} in security
    assert {"CloudAdminToken": []} in security
    restore = schema["paths"][LAB + "/restore"]["post"]
    assert {"CloudAdminToken": []} in restore["security"]
    status = schema["paths"][LAB + "/status"]["get"]
    assert {"CloudAdminToken": []} not in status["security"]


def test_lab_status_reports_live_only_with_full_server_configuration(tmp_path):
    client, _, _ = lab_client(tmp_path)
    body = client.get(LAB + "/status", headers=auth()).json()
    assert body["mode"] == "live"
    assert body["write_ready"] is True
    assert body["admin_configured"] is True
    assert body["backup_count"] == 0


class FailingProvider:
    def __init__(self, error):
        self.error = error

    def download(self, limit=8 * 1024 * 1024):
        raise self.error


@pytest.mark.parametrize(
    ("error", "code"),
    [
        (CloudProviderUnauthenticated("token-secreto"), "cloud_session_rejected"),
        (CloudProviderUnavailable("host-privado"), "cloud_provider_unavailable"),
    ],
)
def test_upstream_session_and_network_errors_are_typed(tmp_path, error, code):
    service = CloudLabService(
        FailingProvider(error),
        LabBackupStore(tmp_path / "backups"),
        uploader=None,
        write_enabled=False,
        admin_configured=True,
    )
    settings = Settings(
        _env_file=None,
        env="production",
        access_token=ACCESS,
        allowed_origins=[ORIGIN],
        cloud_write_enabled=False,
        cloud_admin_token=ADMIN,
    )
    app = create_app(settings)
    app.state.cloud_lab = service
    client = TestClient(app, base_url="http://127.0.0.1:8000", client=("127.0.0.1", 50000))
    response = client.get(LAB + "/save", headers=auth())
    error_body = assert_error(response, 502, code)
    assert "token-secreto" not in response.text and "host-privado" not in response.text
    assert error_body["issues"] == []


def test_lab_route_enforces_json_and_body_limits(tmp_path):
    client, _, _ = lab_client(tmp_path)
    assert_error(
        client.post(LAB + "/prepare", headers=auth() | {"Content-Type": "text/plain"}, content=b"x"),
        415,
        "invalid_content_type",
    )
    assert_error(
        client.post(LAB + "/prepare", headers=auth() | {"Content-Type": "application/json"},
                    content=b"x" * 20_000),
        413,
        "request_too_large",
    )


def test_cloud_settings_validate_credentials_and_backup_path(tmp_path):
    from pydantic import ValidationError

    with pytest.raises(ValidationError) as short:
        Settings(_env_file=None, env="production", cloud_admin_token="short")
    assert "short" not in str(short.value)
    with pytest.raises(ValidationError):
        Settings(_env_file=None, env="production", cloud_backup_dir="relative/backups")
    configured = Settings(
        _env_file=None,
        env="production",
        cloud_session_token="session",
        cloud_unique_id="device",
        cloud_distro_id="distro",
        cloud_admin_token=ADMIN,
        cloud_write_enabled=True,
        cloud_backup_dir=str(tmp_path / "backups"),
    )
    assert configured.cloud_configured is True
    assert configured.cloud_admin_configured is True
    assert configured.cloud_write_ready is True
    read_only = Settings(
        _env_file=None,
        env="production",
        cloud_session_token="session",
        cloud_unique_id="device",
        cloud_distro_id="distro",
        cloud_admin_token=ADMIN,
        cloud_write_enabled=False,
    )
    assert read_only.cloud_configured is True and read_only.cloud_write_ready is False

import json
from datetime import UTC, datetime, timedelta
from itertools import count
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.cloud.backup_store import BackupStoreError, LabBackupStore
from app.cloud.lab_service import CloudLabService
from app.main import create_app
from test_advanced_editor import payload as advanced_payload
from test_character_editor import payload as character_payload
from test_cloud_lab_api import FakeProvider, FakeUpload
from test_fish_chip_editor import payload as fish_payload
from test_native_api import API, HEADERS, PAYLOAD_A, assert_error, confirmation, login, make_native, prepare
from test_skill_editor import payload as skill_payload
from test_skin_editor import payload as skin_payload
from test_unified_editor import plan, source_bytes


def history(client):
    response = client.get(API + "/backups", headers=HEADERS)
    assert response.status_code == 200, response.text
    return response.json()


def prepare_unified(client):
    source = client.get(API + "/save", headers=HEADERS)
    assert source.status_code == 200, source.text
    return client.post(
        API + "/prepare-unified", headers=HEADERS, json=plan() | {"source_sha256": source.json()["sha256"]}
    )


def native_store(env):
    subject = env["store"].identity_subject(email="a@example.test", uid=1, player_id=11)
    return LabBackupStore(env["service"].backup_root / subject, cipher_key=env["service"].backup_key)


def test_unified_native_backup_survives_logout_and_service_restart(tmp_path):
    env = make_native(tmp_path, write=True)
    client = env["client"]
    original = source_bytes()
    provider = env["providers"]["unique-a"]
    provider.payload = original
    assert login(client).status_code == 200

    response = prepare_unified(client)
    assert response.status_code == 200, response.text
    draft = response.json()
    backup_id = draft["backup"]["id"]
    store = native_store(env)
    bundle = store.load(backup_id)
    assert bundle.original == provider.payload == original
    for name in ("original.json", "candidate.json", "record.json"):
        assert (store.root / backup_id / name).read_bytes().startswith(b"SKB1")
    assert env["uploaders"]["unique-a"].calls == []
    listing = history(client)
    assert listing["total"] == listing["listed"] == 1 and listing["unreadable"] == 0
    assert listing["next_cursor"] is None
    row = listing["backups"][0]
    assert row["id"] == backup_id
    assert row["created_at"] == bundle.record.created_at
    assert row["field"] == "unified" and row["kind"] == "edit"
    assert row["status"] == "prepared" and row["restoration"] is None
    assert row["changed"] is True and row["original_size"] == len(original)
    assert row["changes"] == draft["change_count"]
    assert row["categories"] == ["gems", "fish_chip", "fish_progress", "advanced"]
    assert row["integrity"] == "verified" and row["can_restore"] is True
    assert row["interrupted"] is False

    assert client.post(API + "/confirm", headers=HEADERS, json=confirmation(draft)).json()["persisted"]
    assert provider.payload == bundle.candidate
    assert history(client)["backups"][0]["status"] == "verified"
    assert client.post(API + "/logout", headers=HEADERS, json={}).status_code == 204
    assert_error(client.get(API + "/backups", headers=HEADERS), 401, "native_session_required")

    restarted_app = create_app(env["settings"])
    restarted_service = restarted_app.state.native_service
    restarted_service.client = env["auth"]
    restarted_service.provider_factory = env["service"].provider_factory
    restarted_service.uploader_factory = env["service"].uploader_factory
    client = TestClient(restarted_app, base_url="http://127.0.0.1:8000", client=("127.0.0.1", 50000))
    assert login(client).status_code == 200
    assert history(client)["backups"][0]["status"] == "verified"

    endpoint = API + "/restore"
    attempted = client.post(endpoint, headers=HEADERS, json={"backup_id": backup_id})
    assert attempted.status_code == 422
    assert provider.payload == bundle.candidate
    result = client.post(endpoint, headers=HEADERS, json={"backup_id": backup_id, "confirmation": "RESTAURAR"})
    assert result.json()["persisted"]
    assert provider.payload == original
    assert history(client)["backups"][0]["restoration"] == "verified"


def test_upload_without_persistence_uses_actual_history_status(tmp_path, monkeypatch):
    env = make_native(tmp_path, write=True)
    env["providers"]["unique-a"].payload = source_bytes()
    client = env["client"]
    assert login(client).status_code == 200
    draft = prepare_unified(client).json()
    monkeypatch.setattr(env["uploaders"]["unique-a"], "upload", lambda _payload: FakeUpload())
    result = client.post(API + "/confirm", headers=HEADERS, json=confirmation(draft))
    assert result.status_code == 200 and result.json()["persisted"] is False
    record = history(client)["backups"][0]
    assert record["status"] == "unverified"
    assert record["restoration"] is None


@pytest.mark.parametrize("failed_file", ["original.json", "candidate.json", "record.json"])
def test_unified_write_cannot_proceed_without_complete_backup(tmp_path, monkeypatch, failed_file):
    env = make_native(tmp_path, write=True)
    env["providers"]["unique-a"].payload = source_bytes()
    client = env["client"]
    assert login(client).status_code == 200
    write = LabBackupStore._write_private

    def fail(store, path, data, **options):
        if path.name == failed_file:
            raise BackupStoreError("fixture write failure")
        return write(store, path, data, **options)

    monkeypatch.setattr(LabBackupStore, "_write_private", fail)
    assert_error(prepare_unified(client), 500, "backup_store")
    assert history(client)["total"] == 0
    assert list(native_store(env).root.iterdir()) == []
    result = client.post(API + "/confirm", headers=HEADERS, json={
        "backup_id": "1" * 32, "expected_sha256": "2" * 64, "confirmation": "SUBIR",
    })
    assert_error(result, 404, "backup_not_found")
    assert env["uploaders"]["unique-a"].calls == []
    assert env["providers"]["unique-a"].payload == source_bytes()


@pytest.mark.parametrize(("failure", "expected"), [
    ("wrong_key", "authentication"), ("incompatible", "incompatible"),
    ("damaged_candidate", "authentication"), ("missing_original", "file_unavailable"),
    ("invalid_fingerprint", "integrity"),
])
def test_unreadable_records_remain_visible(tmp_path, failure, expected):
    env = make_native(tmp_path)
    env["providers"]["unique-a"].payload = source_bytes()
    client = env["client"]
    assert login(client).status_code == 200
    record = prepare_unified(client).json()["backup"]
    backup_id = record["id"]
    store = native_store(env)
    directory = store.root / backup_id
    if failure == "wrong_key":
        env["service"].backup_key = b"z" * 32
    elif failure == "incompatible":
        record["unified_plan"]["unknown_operation"] = True
        store._write_private(directory / "record.json", json.dumps(record).encode(), exclusive=False)
    elif failure == "damaged_candidate":
        path = directory / "candidate.json"
        path.write_bytes(path.read_bytes()[:-1])
    elif failure == "invalid_fingerprint":
        record["original_sha256"] = "0" * 64
        store._write_private(directory / "record.json", json.dumps(record).encode(), exclusive=False)
    else:
        (directory / "original.json").unlink()

    report = history(client)
    assert report["total"] == report["listed"] == report["unreadable"] == 1
    row = report["backups"][0]
    assert row["status"] == "unreadable" and row["problem"] == expected
    assert {"id", "created_at", "field", "kind", "status", "problem", "integrity", "can_restore"} <= set(row)
    assert row["integrity"] == "unreadable" and row["can_restore"] is False
    assert "original_size" not in row and "summary" not in row


def test_missing_storage_and_root_filesystem_are_unavailable(tmp_path, monkeypatch):
    env = make_native(tmp_path, write=True)
    env["providers"]["unique-a"].payload = source_bytes()
    client = env["client"]
    assert login(client).status_code == 200
    env["service"].backup_root.rmdir()
    assert_error(client.get(API + "/backups", headers=HEADERS), 503, "native_backup_unavailable")
    env["service"].backup_root.mkdir()
    env["service"].backup_require_mount = True
    read_text = Path.read_text

    def read(path, *args, **kwargs):
        if path == Path("/proc/self/mountinfo"):
            return "23 0 0:22 / / rw - overlay overlay rw\n"
        return read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", read)
    assert_error(client.get(API + "/backups", headers=HEADERS), 503, "native_backup_unavailable")
    assert_error(prepare_unified(client), 503, "native_backup_unavailable")
    assert env["uploaders"]["unique-a"].calls == []


def test_history_reports_total_and_lists_most_recent_first(tmp_path, monkeypatch):
    seconds = count()
    start = datetime(2026, 11, 25, tzinfo=UTC)
    monkeypatch.setattr(
        "app.cloud.backup_store._now",
        lambda: (start + timedelta(seconds=next(seconds))).isoformat(),
    )
    env = make_native(tmp_path)
    client = env["client"]
    assert login(client).status_code == 200
    service = CloudLabService(FakeProvider(PAYLOAD_A), native_store(env))
    prepared = [service.prepare(1001 + index).backup.id for index in range(26)]
    report = history(client)
    assert report["total"] == 26 and report["listed"] == report["limit"] == 25
    assert [row["id"] for row in report["backups"]] == list(reversed(prepared[1:]))
    assert report["next_cursor"]

    # Una inserción nueva no desplaza la página ya pedida: el cursor es estable.
    inserted = service.prepare(2000).backup.id
    older = client.get(API + "/backups", headers=HEADERS, params={
        "limit": 25, "cursor": report["next_cursor"],
    })
    assert older.status_code == 200, older.text
    second = older.json()
    assert second["total"] == 27 and second["listed"] == 1
    assert second["backups"][0]["id"] == prepared[0]
    assert second["next_cursor"] is None
    assert inserted != prepared[0]

    invalid = client.get(API + "/backups", headers=HEADERS, params={"cursor": "no-es-un-cursor"})
    assert_error(invalid, 422, "invalid_backup_id")


def test_manual_backup_is_verified_and_does_not_write(tmp_path):
    env = make_native(tmp_path)
    provider = env["providers"]["unique-a"]
    provider.payload = source_bytes()
    client = env["client"]
    assert login(client).status_code == 200

    response = client.post(API + "/backups", headers=HEADERS, json={"confirmation": "RESPALDAR"})
    assert response.status_code == 200, response.text
    assert "verificado" in response.json()["message"]
    assert provider.payload == source_bytes()
    assert env["uploaders"]["unique-a"].calls == []

    row = history(client)["backups"][0]
    assert row["kind"] == "manual" and row["field"] == "snapshot"
    assert row["status"] == "available" and row["integrity"] == "verified"
    assert row["can_restore"] is True and row["changed"] is False
    assert row["summary"]["save_size"] == len(source_bytes())
    assert row["summary"]["gems"] == 1000
    directory = native_store(env).root / row["id"]
    assert sorted(path.name for path in directory.iterdir()) == ["events.jsonl", "original.json", "record.json"]
    assert native_store(env).load(row["id"]).original == source_bytes()

    assert client.post(API + "/backups", headers=HEADERS, json={"confirmation": "SUBIR"}).status_code == 422


def test_historical_restore_creates_preventive_and_can_be_undone(tmp_path):
    env = make_native(tmp_path, write=True)
    provider = env["providers"]["unique-a"]
    provider.payload = source_bytes()
    client = env["client"]
    assert login(client).status_code == 200

    draft = prepare(client)
    original = source_bytes()
    assert client.post(API + "/confirm", headers=HEADERS, json=confirmation(draft)).json()["persisted"]
    edited = provider.payload
    assert edited != original

    changed = client.post(API + "/restore-history", headers=HEADERS, json={
        "backup_id": draft["backup"]["id"], "confirmation": "RESTAURAR",
        "expected_sha256": "0" * 64,
    })
    assert_error(changed, 409, "cloud_remote_changed")
    assert provider.payload == edited
    assert history(client)["total"] == 1

    restored = client.post(API + "/restore-history", headers=HEADERS, json={
        "backup_id": draft["backup"]["id"], "confirmation": "RESTAURAR",
    })
    assert restored.status_code == 200, restored.text
    result = restored.json()
    assert result["persisted"] is True and result["historical"] is True
    assert result["preventive_backup_id"]
    assert provider.payload == original

    report = history(client)
    assert report["total"] == 2
    target = next(row for row in report["backups"] if row["id"] == draft["backup"]["id"])
    preventive = next(row for row in report["backups"] if row["id"] == result["preventive_backup_id"])
    assert target["restoration"] == "verified"
    assert preventive["kind"] == "preventive" and preventive["status"] == "available"
    assert preventive["summary"]["gems"] == 1002

    undone = client.post(API + "/restore-history", headers=HEADERS, json={
        "backup_id": preventive["id"], "confirmation": "RESTAURAR",
    })
    assert undone.status_code == 200, undone.text
    assert undone.json()["persisted"] is True
    assert provider.payload == edited
    assert history(client)["total"] == 3


def test_historical_restore_of_current_version_does_not_write(tmp_path):
    env = make_native(tmp_path, write=True)
    client = env["client"]
    assert login(client).status_code == 200
    draft = prepare(client)
    result = client.post(API + "/restore-history", headers=HEADERS, json={
        "backup_id": draft["backup"]["id"], "confirmation": "RESTAURAR",
    })
    assert result.status_code == 200, result.text
    assert result.json()["already_original"] is True and result.json()["persisted"] is True
    assert env["uploaders"]["unique-a"].calls == []
    assert history(client)["total"] == 1


def test_interrupted_upload_is_reported_after_timeout(tmp_path):
    env = make_native(tmp_path)
    client = env["client"]
    assert login(client).status_code == 200
    draft = prepare(client)
    native_store(env).claim_confirmation_attempt(draft["backup"]["id"])
    row = history(client)["backups"][0]
    assert row["status"] == "unverified" and row["interrupted"] is False

    created = datetime.fromisoformat(row["created_at"])
    env["service"].now = lambda: created.timestamp() + 600
    row = history(client)["backups"][0]
    assert row["status"] == "unverified" and row["interrupted"] is True


def test_version_endpoint_lists_backup_capabilities(tmp_path):
    env = make_native(tmp_path)
    body = env["client"].get("/api/v1/version").json()
    assert body["service"] == "sk-under"
    assert body["api_version"]
    assert {"native_backup_history", "native_backup_manual", "native_backup_restore_historical"} <= set(body["features"])


@pytest.mark.parametrize(("method", "payload", "argument", "field"), [
    ("prepare", lambda: PAYLOAD_A, 1234, "gems"),
    ("prepare_fish_chip", fish_payload, 9, "fish_chip"),
    ("prepare_characters", character_payload, ["Ranger"], "characters"),
    ("prepare_skills", skill_payload, [{"code": "Knight", "index": 1}], "skills"),
    ("prepare_skins", skin_payload, [{"code": "Knight", "index": 1}], "skins"),
    ("prepare_advanced", advanced_payload, {"season_coin": 120}, "advanced"),
    ("prepare_unified", source_bytes, plan(), "unified"),
])
def test_legacy_record_shapes_remain_readable(tmp_path, method, payload, argument, field):
    store = LabBackupStore(tmp_path / "backups", cipher_key=b"s" * 32)
    original = payload()
    service = CloudLabService(FakeProvider(original), store)
    prepared = getattr(service, method)(argument)
    record = prepared.backup.summary()
    for key in ("original_value", "candidate_value"):
        record.pop(key)
    if field == "gems":
        record.pop("field")
    if field == "advanced":
        record["advanced_plan"].pop("pets")
        record["advanced_plan"].pop("pet_food")
    path = store.root / prepared.backup.id / "record.json"
    store._write_private(path, json.dumps(record).encode(), exclusive=False)
    historical_bytes = path.read_bytes()

    assert store.list()[0].field == field
    reopened = LabBackupStore(store.root, cipher_key=store.cipher_key).load(prepared.backup.id)
    assert reopened.original == original
    assert reopened.candidate == prepared.edit.candidate
    assert path.read_bytes() == historical_bytes

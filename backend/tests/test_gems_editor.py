import gzip
import json
import stat
from pathlib import Path

import pytest

from app.cloud.backup_store import (
    BackupAlreadyConfirmed,
    BackupIntegrityError,
    BackupNotFound,
    InvalidBackupId,
    LabBackupStore,
)
from app.cloud.gems_editor import (
    MAX_GEMS,
    GemsFieldMissing,
    InvalidGemsValue,
    UnsupportedAggregateSerialization,
    prepare_gems_edit,
    read_gems,
)
from app.cloud.lab_service import (
    CloudLabService,
    LabAlreadyConfirmed,
    LabNoChanges,
    LabRemoteChanged,
    LabWriteDisabled,
)
from app.cloud.provider import AcquiredCloudSave, CloudSaveMetadata
from app.cloud_save import AggregateFormatError
from hashlib import sha256

FIXTURE = Path(__file__).parent / "fixtures" / "cloud-save-gems.json"


def canonical(document: dict) -> bytes:
    return json.dumps(
        document, ensure_ascii=False, sort_keys=True, separators=(", ", ": "), allow_nan=False
    ).encode()


def document() -> dict:
    return json.loads(FIXTURE.read_bytes())


def test_reads_current_gems_without_touching_the_copy():
    original = FIXTURE.read_bytes()
    snapshot = read_gems(original)
    assert snapshot.gems == 1000
    assert snapshot.size == len(original)
    assert snapshot.sha256 == sha256(original).hexdigest()
    assert snapshot.serialzed_version == 1
    assert FIXTURE.read_bytes() == original


def test_edit_changes_only_game_data_gems():
    original = FIXTURE.read_bytes()
    edit = prepare_gems_edit(original, 1001)
    assert edit.changed is True
    assert (edit.original_gems, edit.new_gems) == (1000, 1001)
    assert edit.original == original and edit.candidate != original
    assert edit.original_sha256 == sha256(original).hexdigest()
    assert edit.candidate_sha256 == sha256(edit.candidate).hexdigest()
    assert edit.binary.changed_original_bytes == edit.binary.changed_modified_bytes == 1
    assert edit.binary.first_difference == original.index(b'"gems": 1000') + len(b'"gems": 100')

    before = document()
    after = json.loads(edit.candidate)
    restored = json.loads(edit.candidate)
    restored["gameData"]["gems"] = before["gameData"]["gems"]
    assert restored == before
    assert after["gameData"]["gems"] == 1001
    assert after["itemData"] == before["itemData"]
    assert after["gameData"]["fish"] == before["gameData"]["fish"]
    assert after["miscData"] == before["miscData"]
    assert after["cloudSaveId"] == before["cloudSaveId"]


def test_edit_is_deterministic_and_canonical():
    original = FIXTURE.read_bytes()
    first = prepare_gems_edit(original, 12345)
    second = prepare_gems_edit(original, 12345)
    assert first.candidate == second.candidate
    assert canonical(json.loads(first.candidate)) == first.candidate
    assert first.candidate_sha256 == second.candidate_sha256


def test_number_of_digits_can_grow_without_touching_other_data():
    before = document()
    before["gameData"]["gems"] = 999
    original = canonical(before)
    edit = prepare_gems_edit(original, 1000)
    after = json.loads(edit.candidate)
    assert after["gameData"]["gems"] == 1000
    assert edit.candidate_size == len(original) + 1


def test_noop_preserves_exact_bytes():
    original = FIXTURE.read_bytes()
    edit = prepare_gems_edit(original, 1000)
    assert edit.changed is False
    assert edit.candidate == original
    assert edit.original_sha256 == edit.candidate_sha256
    assert edit.binary.first_difference is None


@pytest.mark.parametrize("value", [None, True, False, "1001", 1001.0, -1, MAX_GEMS + 1, [], {}])
def test_rejects_invalid_gems_values(value):
    with pytest.raises(InvalidGemsValue):
        prepare_gems_edit(FIXTURE.read_bytes(), value)


def test_accepts_documented_bounds():
    assert prepare_gems_edit(FIXTURE.read_bytes(), 0).new_gems == 0
    assert prepare_gems_edit(FIXTURE.read_bytes(), MAX_GEMS).new_gems == MAX_GEMS


def test_rejects_missing_field():
    value = document()
    del value["gameData"]["gems"]
    with pytest.raises(GemsFieldMissing):
        read_gems(canonical(value))


def test_rejects_bool_field_in_the_save():
    value = document()
    value["gameData"]["gems"] = True
    with pytest.raises(InvalidGemsValue):
        read_gems(canonical(value))


@pytest.mark.parametrize("payload", [
    b'{"serialzedVersion": 1, "cloudSaveId": "x", "platformId": "a", "gameData": {"gems": 1}}',
    gzip.compress(FIXTURE.read_bytes(), mtime=0),
])
def test_rejects_unsupported_serializations(payload):
    with pytest.raises(UnsupportedAggregateSerialization):
        prepare_gems_edit(payload, 2)


@pytest.mark.parametrize("payload", [
    b"",
    b"not json",
    b'{"serialzedVersion": 1, "cloudSaveId": "x", "platformId": "a"}',
    b'{"serialzedVersion": 1, "cloudSaveId": "x", "platformId": "a", "gameData": []}',
    b'{"serialzedVersion": 1, "cloudSaveId": "x", "platformId": "a", "gameData": {"gems": 1, "gems": 2}}',
])
def test_rejects_invalid_aggregates(payload):
    with pytest.raises((AggregateFormatError, ValueError)):
        prepare_gems_edit(payload, 2)


def test_rejects_unknown_shapes_without_modifying_input():
    original = FIXTURE.read_bytes()
    with pytest.raises(ValueError):
        prepare_gems_edit(original, -5)
    assert FIXTURE.read_bytes() == original


class FixedProvider:
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
    def __init__(self, provider: FixedProvider):
        self.provider = provider
        self.calls: list[bytes] = []

    def upload(self, aggregate: bytes):
        self.calls.append(aggregate)
        self.provider.payload = aggregate
        return FakeUpload()


def service(tmp_path: Path, provider: FixedProvider, *, write=False, uploader=None, admin=True):
    return CloudLabService(
        provider,
        LabBackupStore(tmp_path / "backups"),
        uploader=uploader,
        write_enabled=write,
        admin_configured=admin,
    )


def test_status_distinguishes_read_only_and_live(tmp_path):
    provider = FixedProvider(FIXTURE.read_bytes())
    read = service(tmp_path, provider)
    assert read.status().mode == "read_only"
    assert read.status().write_ready is False
    live = service(tmp_path, provider, write=True, uploader=FakeUploader(provider))
    assert live.status().mode == "live"
    assert live.status().write_ready is True
    assert live.status().backup_count == 0


def test_prepare_creates_verified_private_backup(tmp_path):
    provider = FixedProvider(FIXTURE.read_bytes())
    lab = service(tmp_path, provider)
    prepared = lab.prepare(1001)
    assert prepared.changed is True
    assert prepared.original_gems == 1000
    assert prepared.new_gems == 1001
    backup_dir = tmp_path / "backups" / prepared.backup.id
    assert stat.S_IMODE((tmp_path / "backups").stat().st_mode) == 0o700
    assert stat.S_IMODE(backup_dir.stat().st_mode) == 0o700
    for name in ("original.json", "candidate.json", "record.json"):
        assert stat.S_IMODE((backup_dir / name).stat().st_mode) == 0o600
    assert provider.calls == 1
    bundle = lab.store.load(prepared.backup.id)
    assert bundle.original == FIXTURE.read_bytes()
    assert json.loads(bundle.candidate)["gameData"]["gems"] == 1001
    assert [record.id for record in lab.backups()] == [prepared.backup.id]


def test_prepare_noop_is_recorded_but_not_writable(tmp_path):
    provider = FixedProvider(FIXTURE.read_bytes())
    lab = service(tmp_path, provider, write=True, uploader=FakeUploader(provider))
    prepared = lab.prepare(1000)
    assert prepared.changed is False
    with pytest.raises(LabNoChanges):
        lab.confirm(prepared.backup.id, prepared.edit.candidate_sha256)


def test_confirm_requires_server_side_write_configuration(tmp_path):
    provider = FixedProvider(FIXTURE.read_bytes())
    lab = service(tmp_path, provider, uploader=FakeUploader(provider))
    prepared = lab.prepare(1001)
    with pytest.raises(LabWriteDisabled):
        lab.confirm(prepared.backup.id, prepared.edit.candidate_sha256)


def test_confirm_checks_hash_before_any_write(tmp_path):
    provider = FixedProvider(FIXTURE.read_bytes())
    uploader = FakeUploader(provider)
    lab = service(tmp_path, provider, write=True, uploader=uploader)
    prepared = lab.prepare(1001)
    with pytest.raises(Exception):
        lab.confirm(prepared.backup.id, "0" * 64)
    assert uploader.calls == []


def test_confirm_uploads_and_verifies_persistence(tmp_path):
    provider = FixedProvider(FIXTURE.read_bytes())
    uploader = FakeUploader(provider)
    lab = service(tmp_path, provider, write=True, uploader=uploader)
    prepared = lab.prepare(1001)
    result = lab.confirm(prepared.backup.id, prepared.edit.candidate_sha256)
    assert result.uploaded is True and result.accepted is True and result.persisted is True
    assert result.remote_gems == 1001
    assert uploader.calls == [prepared.edit.candidate]
    assert lab.store.confirmation(prepared.backup.id) is not None
    with pytest.raises(LabAlreadyConfirmed):
        lab.confirm(prepared.backup.id, prepared.edit.candidate_sha256)
    assert len(uploader.calls) == 1


def test_confirm_aborts_if_remote_changed_after_prepare(tmp_path):
    provider = FixedProvider(FIXTURE.read_bytes())
    uploader = FakeUploader(provider)
    lab = service(tmp_path, provider, write=True, uploader=uploader)
    prepared = lab.prepare(1001)
    changed = document()
    changed["gameData"]["gems"] = 5000
    provider.payload = canonical(changed)
    with pytest.raises(LabRemoteChanged):
        lab.confirm(prepared.backup.id, prepared.edit.candidate_sha256)
    assert uploader.calls == []


def test_confirm_reports_failed_persistence_without_confirming(tmp_path):
    provider = FixedProvider(FIXTURE.read_bytes())
    uploader = FakeUploader(provider)
    original_upload = uploader.upload

    def upload_without_change(aggregate):
        uploader.calls.append(aggregate)
        return FakeUpload()

    uploader.upload = upload_without_change
    lab = service(tmp_path, provider, write=True, uploader=uploader)
    prepared = lab.prepare(1001)
    result = lab.confirm(prepared.backup.id, prepared.edit.candidate_sha256)
    assert result.accepted is True and result.persisted is False
    assert "no coincide" in result.message
    assert lab.store.confirmation(prepared.backup.id) is None


def test_restore_reverts_the_candidate_and_is_verified(tmp_path):
    provider = FixedProvider(FIXTURE.read_bytes())
    uploader = FakeUploader(provider)
    lab = service(tmp_path, provider, write=True, uploader=uploader)
    prepared = lab.prepare(1001)
    lab.confirm(prepared.backup.id, prepared.edit.candidate_sha256)
    restored = lab.restore(prepared.backup.id)
    assert restored.uploaded is True and restored.persisted is True
    assert restored.remote_gems == 1000
    assert uploader.calls[-1] == FIXTURE.read_bytes()
    again = lab.restore(prepared.backup.id)
    assert again.already_original is True and again.uploaded is False
    assert len(uploader.calls) == 2


def test_verify_distinguishes_candidate_and_original(tmp_path):
    provider = FixedProvider(FIXTURE.read_bytes())
    lab = service(tmp_path, provider)
    prepared = lab.prepare(1001)
    original_check = lab.verify(prepared.backup.id)
    assert original_check.matches_original is True
    assert original_check.matches_candidate is False
    provider.payload = prepared.edit.candidate
    candidate_check = lab.verify(prepared.backup.id)
    assert candidate_check.matches_candidate is True
    assert candidate_check.remote_gems == 1001


def test_backup_store_rejects_tampering_and_traversal(tmp_path):
    provider = FixedProvider(FIXTURE.read_bytes())
    lab = service(tmp_path, provider)
    prepared = lab.prepare(1001)
    candidate = tmp_path / "backups" / prepared.backup.id / "candidate.json"
    candidate.write_bytes(candidate.read_bytes().replace(b'"gems": 1001', b'"gems": 1002'))
    with pytest.raises(BackupIntegrityError):
        lab.store.load(prepared.backup.id)
    with pytest.raises(InvalidBackupId):
        lab.store.load("../" + prepared.backup.id)
    with pytest.raises(BackupNotFound):
        lab.store.load("0" * 32)


def test_backup_store_does_not_overwrite_confirmation(tmp_path):
    provider = FixedProvider(FIXTURE.read_bytes())
    lab = service(tmp_path, provider)
    prepared = lab.prepare(1001)
    lab.store.save_confirmation(prepared.backup.id, {"ok": True})
    with pytest.raises(BackupAlreadyConfirmed):
        lab.store.save_confirmation(prepared.backup.id, {"ok": False})


def test_backup_store_keeps_events_outside_the_record(tmp_path):
    provider = FixedProvider(FIXTURE.read_bytes())
    lab = service(tmp_path, provider)
    prepared = lab.prepare(1001)
    lab.verify(prepared.backup.id)
    events = (tmp_path / "backups" / prepared.backup.id / "events.jsonl").read_text().splitlines()
    assert [json.loads(line)["action"] for line in events] == ["prepare", "verify"]
    assert "cloudSaveId" not in "\n".join(events)


def test_restore_aborts_if_cloud_changed_after_confirmation(tmp_path):
    provider = FixedProvider(FIXTURE.read_bytes())
    uploader = FakeUploader(provider)
    lab = service(tmp_path, provider, write=True, uploader=uploader)
    prepared = lab.prepare(1001)
    lab.confirm(prepared.backup.id, prepared.edit.candidate_sha256)
    changed = document()
    changed["gameData"]["gems"] = 5000
    provider.payload = canonical(changed)
    calls = len(uploader.calls)
    with pytest.raises(LabRemoteChanged):
        lab.restore(prepared.backup.id)
    assert len(uploader.calls) == calls

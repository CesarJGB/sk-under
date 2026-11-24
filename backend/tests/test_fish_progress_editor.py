import json
from hashlib import sha256
from pathlib import Path

import pytest

from app.cloud.backup_store import LabBackupStore
from app.cloud.fish_progress_editor import (
    MAX_FISH_PROGRESS,
    FishProgressFieldMissing,
    InvalidFishProgressValue,
    prepare_fish_progress_edit,
    read_fish_progress,
)
from app.cloud.lab_service import CloudLabService
from app.cloud.provider import AcquiredCloudSave, CloudSaveMetadata

FIXTURE = Path(__file__).parent / "fixtures" / "cloud-save-gems.json"


def canonical(document: dict) -> bytes:
    return json.dumps(
        document, ensure_ascii=False, sort_keys=True, separators=(", ", ": "), allow_nan=False
    ).encode()


def document() -> dict:
    data = json.loads(FIXTURE.read_bytes())
    data["gameData"]["fishChip"] = 3
    data["itemData"]["materials"] = {"material_fish": 3, "material_ticket": 5}
    data["itemData"]["cumulativeFishCount"] = 42
    data["itemData"]["fishChipStorePurchaseHistory"] = {"tier": 1}
    return data


def payload() -> bytes:
    return canonical(document())


class FixedProvider:
    def __init__(self, value: bytes):
        self.payload = value

    def download(self, limit=8 * 1024 * 1024):
        return AcquiredCloudSave(
            CloudSaveMetadata(
                "fake-remote", len(self.payload), sha256(self.payload).hexdigest(), source="modern-cloud"
            ),
            self.payload,
        )


class FakeUpload:
    status = 200
    accepted = True


class FakeUploader:
    def __init__(self, provider: FixedProvider):
        self.provider = provider

    def upload(self, aggregate: bytes):
        self.provider.payload = aggregate
        return FakeUpload()


def service(tmp_path: Path, provider: FixedProvider, *, write=False, uploader=None):
    return CloudLabService(
        provider,
        LabBackupStore(tmp_path / "backups"),
        uploader=uploader,
        write_enabled=write,
        admin_configured=True,
    )


def test_reads_progress_without_touching_the_copy():
    original = payload()
    snapshot = read_fish_progress(original)
    assert snapshot.cumulative_fish_count == 42
    assert snapshot.sha256 == sha256(original).hexdigest()
    assert payload() == original


def test_edit_changes_only_cumulative_fish_count():
    original = payload()
    before = document()
    edit = prepare_fish_progress_edit(original, 120)
    assert edit.changed is True
    assert (edit.original_cumulative_fish_count, edit.new_cumulative_fish_count) == (42, 120)
    assert edit.changed_fields == ("itemData.cumulativeFishCount",)
    after = json.loads(edit.candidate)
    assert after["itemData"]["cumulativeFishCount"] == 120
    assert after["gameData"]["fishChip"] == before["gameData"]["fishChip"]
    assert after["itemData"]["materials"] == before["itemData"]["materials"]
    assert after["itemData"]["fishChipStorePurchaseHistory"] == {"tier": 1}
    restored = json.loads(edit.candidate)
    restored["itemData"]["cumulativeFishCount"] = 42
    assert restored == before


def test_edit_is_deterministic_and_noop_preserves_bytes():
    original = payload()
    first = prepare_fish_progress_edit(original, 120)
    second = prepare_fish_progress_edit(original, 120)
    assert first.candidate == second.candidate
    noop = prepare_fish_progress_edit(original, 42)
    assert noop.changed is False
    assert noop.candidate == original


@pytest.mark.parametrize("value", [None, True, False, "7", 7.0, -1, MAX_FISH_PROGRESS + 1, [], {}])
def test_rejects_invalid_progress_values(value):
    with pytest.raises(InvalidFishProgressValue):
        prepare_fish_progress_edit(payload(), value)


def test_rejects_missing_field_without_creating_it():
    missing = document()
    del missing["itemData"]["cumulativeFishCount"]
    with pytest.raises(FishProgressFieldMissing):
        read_fish_progress(canonical(missing))
    with pytest.raises(FishProgressFieldMissing):
        prepare_fish_progress_edit(canonical(missing), 120)


def test_prepare_confirm_and_restore_preserve_balance_and_history(tmp_path):
    provider = FixedProvider(payload())
    uploader = FakeUploader(provider)
    lab = service(tmp_path, provider, write=True, uploader=uploader)
    prepared = lab.prepare_fish_progress(120)
    assert prepared.backup.field == "fish_progress"
    assert prepared.backup.original_value == 42
    assert prepared.backup.candidate_value == 120
    assert prepared.summary()["field"] == "itemData.cumulativeFishCount"
    assert prepared.summary()["experimental"] is True
    assert lab.load().fish_chip == 3
    assert lab.load().cumulative_fish_count == 42

    result = lab.confirm(prepared.backup.id, prepared.candidate_sha256)
    assert result.persisted is True
    assert result.remote_value == 120
    loaded = lab.load()
    assert loaded.cumulative_fish_count == 120
    assert loaded.fish_chip == 3
    after = json.loads(provider.payload)
    assert after["gameData"]["fishChip"] == 3
    assert after["itemData"]["materials"]["material_fish"] == 3

    restored = lab.restore(prepared.backup.id)
    assert restored.persisted is True
    assert lab.load().cumulative_fish_count == 42
    assert lab.load().fish_chip == 3
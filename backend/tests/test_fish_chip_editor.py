import gzip
import json
from hashlib import sha256
from pathlib import Path

import pytest

from app.cloud.backup_store import BackupIntegrityError, LabBackupStore
from app.cloud.fish_chip_editor import (
    MAX_FISH_CHIP,
    FishChipFieldMissing,
    FishMaterialFieldMissing,
    InvalidFishChipValue,
    InvalidFishMaterialValue,
    UnsupportedFishChipSerialization,
    legacy_fish_chip_candidate_matches,
    prepare_fish_chip_edit,
    read_fish_chip,
)
from app.cloud.gems_editor import prepare_gems_edit
from app.cloud.lab_service import CloudLabService, LabNoChanges
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


def test_reads_the_experimental_balance_without_touching_the_copy():
    original = payload()
    snapshot = read_fish_chip(original)
    assert snapshot.fish_chip == 3
    assert snapshot.material_fish == 3
    assert snapshot.size == len(original)
    assert snapshot.sha256 == sha256(original).hexdigest()
    assert snapshot.serialzed_version == 1
    assert payload() == original


def test_edit_changes_only_the_two_fish_fields():
    original = payload()
    before = document()
    edit = prepare_fish_chip_edit(original, 7)
    assert edit.changed is True
    assert (edit.original_fish_chip, edit.new_fish_chip) == (3, 7)
    assert (edit.original_material_fish, edit.new_material_fish) == (3, 7)
    assert edit.changed_fields == ("gameData.fishChip", "itemData.materials.material_fish")
    assert edit.original == original and edit.candidate != original
    assert edit.original_sha256 == sha256(original).hexdigest()
    assert edit.candidate_sha256 == sha256(edit.candidate).hexdigest()

    after = json.loads(edit.candidate)
    assert after["gameData"]["fishChip"] == 7
    assert after["itemData"]["materials"]["material_fish"] == 7
    restored = json.loads(edit.candidate)
    restored["gameData"]["fishChip"] = before["gameData"]["fishChip"]
    restored["itemData"]["materials"]["material_fish"] = before["itemData"]["materials"]["material_fish"]
    # Ningún otro campo del agregado cambia.
    assert restored == before
    assert after["gameData"]["fish"] == before["gameData"]["fish"]
    assert after["itemData"]["materials"]["material_ticket"] == 5
    assert after["itemData"]["cumulativeFishCount"] == 42
    assert after["itemData"]["fishChipStorePurchaseHistory"] == {"tier": 1}


def test_edit_is_deterministic_and_noop_preserves_bytes():
    original = payload()
    first = prepare_fish_chip_edit(original, 12)
    second = prepare_fish_chip_edit(original, 12)
    assert first.candidate == second.candidate
    assert canonical(json.loads(first.candidate)) == first.candidate

    noop = prepare_fish_chip_edit(original, 3)
    assert noop.changed is False
    assert noop.candidate == original
    assert noop.binary.first_difference is None


@pytest.mark.parametrize("value", [None, True, False, "7", 7.0, -1, MAX_FISH_CHIP + 1, [], {}])
def test_rejects_invalid_fish_chip_values(value):
    with pytest.raises(InvalidFishChipValue):
        prepare_fish_chip_edit(payload(), value)


def test_accepts_non_negative_bounds():
    assert prepare_fish_chip_edit(payload(), 0).new_fish_chip == 0
    assert prepare_fish_chip_edit(payload(), MAX_FISH_CHIP).new_fish_chip == MAX_FISH_CHIP
def test_accepts_legacy_fish_chip_only_candidate_for_old_backups():
    original = payload()
    legacy = document()
    legacy["gameData"]["fishChip"] = 7
    candidate = canonical(legacy)
    assert legacy_fish_chip_candidate_matches(original, 7, candidate) is True
    # Un cambio adicional en materials no se acepta como respaldo antiguo.
    legacy["itemData"]["materials"]["material_ticket"] = 6
    assert legacy_fish_chip_candidate_matches(original, 7, canonical(legacy)) is False


def test_rejects_missing_or_non_integer_field():
    missing = document()
    del missing["gameData"]["fishChip"]
    with pytest.raises(FishChipFieldMissing):
        read_fish_chip(canonical(missing))

    invalid = document()
    invalid["gameData"]["fishChip"] = "3"
    with pytest.raises(InvalidFishChipValue):
        read_fish_chip(canonical(invalid))


def test_reads_and_creates_missing_material_fish():
    missing = document()
    del missing["itemData"]["materials"]["material_fish"]
    snapshot = read_fish_chip(canonical(missing))
    assert snapshot.material_fish is None

    edit = prepare_fish_chip_edit(canonical(missing), 7)
    assert edit.changed_fields == ("gameData.fishChip", "itemData.materials.material_fish")
    after = json.loads(edit.candidate)
    assert after["itemData"]["materials"]["material_fish"] == 7
    assert after["itemData"]["materials"]["material_ticket"] == 5

    restored = json.loads(edit.candidate)
    restored["gameData"]["fishChip"] = 3
    del restored["itemData"]["materials"]["material_fish"]
    assert canonical(restored) == canonical(missing)


def test_rejects_missing_materials_or_invalid_material_type():
    missing = document()
    del missing["itemData"]["materials"]
    with pytest.raises(FishMaterialFieldMissing):
        prepare_fish_chip_edit(canonical(missing), 7)
    assert read_fish_chip(canonical(missing)).material_fish is None

    invalid = document()
    invalid["itemData"]["materials"]["material_fish"] = {"salmon": 9}
    with pytest.raises(InvalidFishMaterialValue):
        read_fish_chip(canonical(invalid))
    with pytest.raises(InvalidFishMaterialValue):
        prepare_fish_chip_edit(canonical(invalid), 7)


@pytest.mark.parametrize("value", [
    gzip.compress(payload(), mtime=0),
    b'{"serialzedVersion": 1, "cloudSaveId": "x", "platformId": "a", "gameData": {"fishChip": 1}}',
])
def test_rejects_unsupported_serializations(value):
    with pytest.raises(UnsupportedFishChipSerialization):
        prepare_fish_chip_edit(value, 2)


def test_prepare_creates_a_field_specific_private_backup(tmp_path):
    provider = FixedProvider(payload())
    lab = service(tmp_path, provider)
    prepared = lab.prepare_fish_chip(7)
    assert prepared.changed is True
    assert (prepared.original_fish_chip, prepared.new_fish_chip) == (3, 7)
    assert prepared.backup.field == "fish_chip"
    assert prepared.backup.original_value == 3
    assert prepared.backup.candidate_value == 7
    summary = prepared.summary()
    assert summary["field"] == "gameData.fishChip"
    assert summary["experimental"] is True
    assert summary["validation"]["only_fish_fields_changed"] is True

    bundle = lab.store.load(prepared.backup.id)
    assert json.loads(bundle.original)["gameData"]["fishChip"] == 3
    assert json.loads(bundle.candidate)["gameData"]["fishChip"] == 7
    assert json.loads(bundle.candidate)["gameData"]["gems"] == 1000


def test_confirm_uploads_fish_chip_and_preserves_gems(tmp_path):
    provider = FixedProvider(payload())
    uploader = FakeUploader(provider)
    lab = service(tmp_path, provider, write=True, uploader=uploader)
    prepared = lab.prepare_fish_chip(7)
    result = lab.confirm(prepared.backup.id, prepared.candidate_sha256)
    assert result.uploaded is True and result.persisted is True
    assert result.field == "gameData.fishChip"
    assert result.remote_value == 7
    assert result.remote_material_fish == 7
    assert result.remote_gems == 1000
    assert json.loads(uploader.calls[0])["gameData"]["gems"] == 1000
    assert json.loads(uploader.calls[0])["gameData"]["fishChip"] == 7
    assert json.loads(uploader.calls[0])["itemData"]["materials"]["material_fish"] == 7
    assert lab.store.confirmation(prepared.backup.id) is not None


def test_restore_and_verify_fish_chip_backup(tmp_path):
    provider = FixedProvider(payload())
    uploader = FakeUploader(provider)
    lab = service(tmp_path, provider, write=True, uploader=uploader)
    prepared = lab.prepare_fish_chip(7)
    confirmed = lab.confirm(prepared.backup.id, prepared.candidate_sha256)
    assert confirmed.remote_value == 7

    check = lab.verify(prepared.backup.id)
    assert check.field == "gameData.fishChip"
    assert check.matches_candidate is True
    assert check.remote_value == 7
    assert check.remote_material_fish == 7

    restored = lab.restore(prepared.backup.id)
    assert restored.persisted is True
    assert restored.remote_value == 3
    assert restored.remote_material_fish == 3
    assert restored.remote_gems == 1000
    again = lab.restore(prepared.backup.id)
    assert again.already_original is True and again.uploaded is False
    assert again.remote_value == 3
    assert again.remote_material_fish == 3


def test_fish_chip_noop_is_not_writable(tmp_path):
    provider = FixedProvider(payload())
    uploader = FakeUploader(provider)
    lab = service(tmp_path, provider, write=True, uploader=uploader)
    prepared = lab.prepare_fish_chip(3)
    assert prepared.changed is False
    with pytest.raises(LabNoChanges):
        lab.confirm(prepared.backup.id, prepared.candidate_sha256)
    assert uploader.calls == []


def test_fish_chip_backup_rejects_tampering(tmp_path):
    provider = FixedProvider(payload())
    lab = service(tmp_path, provider)
    prepared = lab.prepare_fish_chip(7)
    candidate = tmp_path / "backups" / prepared.backup.id / "candidate.json"
    candidate.write_bytes(candidate.read_bytes().replace(b'"fishChip": 7', b'"fishChip": 8'))
    with pytest.raises(BackupIntegrityError):
        lab.store.load(prepared.backup.id)


def test_gems_editing_still_works_alongside_fish_chip(tmp_path):
    provider = FixedProvider(payload())
    uploader = FakeUploader(provider)
    lab = service(tmp_path, provider, write=True, uploader=uploader)

    fish = lab.prepare_fish_chip(7)
    gems = lab.prepare(1001)
    assert gems.backup.field == "gems"
    assert gems.edit.changed_fields == ("gameData.gems", "gameData.varGems")
    assert gems.edit.candidate != fish.edit.candidate

    result = lab.confirm(gems.backup.id, gems.candidate_sha256)
    assert result.persisted is True
    assert result.remote_gems == 1001
    assert json.loads(provider.payload)["gameData"]["fishChip"] == 3

    unrelated = lab.verify(fish.backup.id)
    assert unrelated.matches_candidate is False and unrelated.matches_original is False

    assert lab.restore(gems.backup.id).persisted is True
    assert json.loads(provider.payload)["gameData"]["gems"] == 1000
    assert json.loads(provider.payload)["gameData"]["fishChip"] == 3

    fish_result = lab.confirm(fish.backup.id, fish.candidate_sha256)
    assert fish_result.persisted is True
    assert fish_result.remote_value == 7
    assert fish_result.remote_material_fish == 7
    assert json.loads(provider.payload)["gameData"]["gems"] == 1000
    assert lab.restore(fish.backup.id).persisted is True
    assert json.loads(provider.payload)["gameData"]["fishChip"] == 3


def test_fish_chip_edit_does_not_replace_the_gems_policy():
    edit = prepare_gems_edit(payload(), 1001)
    assert edit.changed_fields == ("gameData.gems", "gameData.varGems")
    assert json.loads(edit.candidate)["gameData"]["fishChip"] == 3
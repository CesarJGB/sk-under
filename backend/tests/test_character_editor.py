import json
from hashlib import sha256
from pathlib import Path

import pytest

from app.cloud.backup_store import BackupIntegrityError, LabBackupStore
from app.cloud.character_editor import (
    CharacterFieldMissing,
    InvalidCharacterSelection,
    OutdatedCharacterDraft,
    UnknownCharacter,
    UnsupportedCharacterStructure,
    prepare_character_unlock_edit,
    read_characters,
    require_character_write_compatibility,
)
from app.cloud.lab_service import CloudLabService
from app.cloud.provider import AcquiredCloudSave, CloudSaveMetadata
from app.save_report import _load_character_catalog

FIXTURE = Path(__file__).parent / "fixtures" / "cloud-save-gems.json"
CODES = tuple(_load_character_catalog()["codes"])
LOCKED = tuple(code for code in CODES if code not in {"Knight", "CostumePrince"})


def canonical(document: dict) -> bytes:
    return json.dumps(
        document, ensure_ascii=False, sort_keys=True, separators=(", ", ": "), allow_nan=False
    ).encode()


def document(*, unlocked=("Knight",), include_all=True) -> dict:
    data = json.loads(FIXTURE.read_bytes())
    data["gameData"]["gems"] = 1000
    data["gameData"]["heroUnlock"] = {
        code: code in unlocked for code in CODES
    }
    if not include_all:
        data["gameData"]["heroUnlock"].pop("Ranger", None)
    data["gameData"]["heroLevel"] = {code: 0 for code in CODES}
    data["gameData"]["heroLevel"]["Knight"] = 2
    data["gameData"]["heroSkill"] = {code: 0 for code in CODES}
    data["gameData"]["heroSkillUnlock"] = {
        code: [{"Key": 0, "Value": True}, {"Key": 1, "Value": False}, {"Key": 2, "Value": False}]
        for code in CODES
    }
    data["gameData"]["skinLock"] = {code: [0, 1, -1] for code in CODES}
    data["gameData"]["currentSkinDatas"] = {"Knight": 1}
    data["itemData"]["materials"] = {"material_fish": 3, "material_ticket": 5}
    data["gameData"]["fishChip"] = 3
    return data


def payload(**kwargs) -> bytes:
    return canonical(document(**kwargs))


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


def service(tmp_path: Path, provider: FixedProvider, *, write=False):
    return CloudLabService(
        provider,
        LabBackupStore(tmp_path / "backups"),
        uploader=FakeUploader(provider) if write else None,
        write_enabled=write,
        admin_configured=True,
    )


def test_catalog_has_the_42_known_characters():
    assert len(CODES) == 42
    assert CODES[:2] == ("Knight", "Ranger")


def test_reads_unlocked_characters_without_touching_the_copy():
    original = payload()
    snapshot = read_characters(original)
    assert snapshot.unlocked == ("Knight",)
    assert snapshot.total == 42
    assert snapshot.size == len(original)
    assert snapshot.sha256 == sha256(original).hexdigest()
    assert payload() == original


def test_single_unlock_changes_only_hero_unlock_for_that_character():
    original = payload()
    before = document()
    edit = prepare_character_unlock_edit(original, ["Ranger"])
    assert edit.changed is True
    assert edit.newly_unlocked == ("Ranger",)
    assert edit.original_unlocked == ("Knight",)
    assert edit.new_unlocked == ("Knight", "Ranger")
    assert edit.changed_fields == ("gameData.heroUnlock.Ranger",)
    assert edit.original == original and edit.candidate != original

    after = json.loads(edit.candidate)
    assert after["gameData"]["heroUnlock"]["Ranger"] is True
    assert after["gameData"]["heroUnlock"]["Knight"] is True
    # Niveles, habilidades, skins y el resto del agregado permanecen intactos.
    assert after["gameData"]["heroLevel"] == before["gameData"]["heroLevel"]
    assert after["gameData"]["heroSkill"] == before["gameData"]["heroSkill"]
    assert after["gameData"]["heroSkillUnlock"] == before["gameData"]["heroSkillUnlock"]
    assert after["gameData"]["skinLock"] == before["gameData"]["skinLock"]
    assert after["gameData"]["currentSkinDatas"] == before["gameData"]["currentSkinDatas"]
    assert after["gameData"]["gems"] == before["gameData"]["gems"]
    assert after["gameData"]["fishChip"] == before["gameData"]["fishChip"]
    assert after["itemData"] == before["itemData"]

    restored = json.loads(edit.candidate)
    restored["gameData"]["heroUnlock"] = before["gameData"]["heroUnlock"]
    assert restored == before


def test_multiple_selection_preserves_already_unlocked_and_unselected():
    original = payload(unlocked=("Knight", "CostumePrince"))
    before = document(unlocked=("Knight", "CostumePrince"))
    edit = prepare_character_unlock_edit(original, ["Ranger", "Mage", "Knight"])
    assert edit.selected_codes == ("Ranger", "Mage", "Knight")
    assert edit.newly_unlocked == ("Ranger", "Mage")
    assert edit.new_unlocked == ("Knight", "CostumePrince", "Ranger", "Mage")
    assert edit.changed_fields == (
        "gameData.heroUnlock.Ranger",
        "gameData.heroUnlock.Mage",
    )
    after = json.loads(edit.candidate)
    assert after["gameData"]["heroUnlock"]["Knight"] is True
    assert after["gameData"]["heroUnlock"]["CostumePrince"] is True
    assert after["gameData"]["heroUnlock"]["Ranger"] is True
    assert after["gameData"]["heroUnlock"]["Mage"] is True
    assert after["gameData"]["heroUnlock"]["Alchemist"] is False
    # El nivel del personaje ya disponible no se toca.
    assert after["gameData"]["heroLevel"]["Knight"] == before["gameData"]["heroLevel"]["Knight"] == 2


def test_mass_unlock_marks_every_locked_character_and_stays_idempotent():
    original = payload(unlocked=("Knight", "CostumePrince"))
    edit = prepare_character_unlock_edit(original, LOCKED)
    assert edit.newly_unlocked == LOCKED
    assert edit.new_unlocked == ("Knight", "CostumePrince") + LOCKED
    assert len(edit.new_unlocked) == 42
    after = json.loads(edit.candidate)
    assert all(after["gameData"]["heroUnlock"][code] is True for code in CODES)

    noop = prepare_character_unlock_edit(edit.candidate, LOCKED)
    assert noop.changed is False
    assert noop.candidate == edit.candidate
    assert noop.newly_unlocked == ()


def test_missing_catalog_entry_is_added_only_when_selected():
    original = payload(include_all=False)
    edit = prepare_character_unlock_edit(original, ["Ranger"])
    after = json.loads(edit.candidate)
    assert after["gameData"]["heroUnlock"]["Ranger"] is True
    assert edit.changed_fields == ("gameData.heroUnlock.Ranger",)


def test_noop_selection_of_an_unlocked_character_does_not_write():
    original = payload()
    edit = prepare_character_unlock_edit(original, ["Knight"])
    assert edit.changed is False
    assert edit.candidate == original
    assert edit.binary.first_difference is None


@pytest.mark.parametrize(
    "codes",
    [
        [],
        ["Knight", "Knight"],
        ["NoExiste"],
        None,
        "Knight",
        [1],
        [""],
    ],
)
def test_rejects_invalid_or_unknown_selections(codes):
    with pytest.raises((InvalidCharacterSelection, UnknownCharacter)):
        prepare_character_unlock_edit(payload(), codes)


def test_rejects_missing_or_non_boolean_unlock_map():
    missing = document()
    del missing["gameData"]["heroUnlock"]
    with pytest.raises(CharacterFieldMissing):
        read_characters(canonical(missing))

    for invalid_value in (0, 1, "true", None):
        invalid = document()
        invalid["gameData"]["heroUnlock"]["Ranger"] = invalid_value
        with pytest.raises(UnsupportedCharacterStructure):
            prepare_character_unlock_edit(canonical(invalid), ["Ranger"])


def test_rejects_stale_backup_selection():
    original = payload()
    edit = prepare_character_unlock_edit(original, ["Ranger", "Mage"])
    with pytest.raises(OutdatedCharacterDraft):
        require_character_write_compatibility(original, ["Ranger"], edit.candidate)
    require_character_write_compatibility(original, ["Ranger", "Mage"], edit.candidate)


def test_prepare_creates_a_private_backup_and_confirm_restores(tmp_path):
    provider = FixedProvider(payload())
    lab = service(tmp_path, provider, write=True)
    prepared = lab.prepare_characters(["Ranger", "Mage"])
    assert prepared.changed is True
    assert prepared.edit.original_unlocked == ("Knight",)
    assert prepared.edit.new_unlocked == ("Knight", "Ranger", "Mage")
    assert prepared.edit.total == 42
    assert prepared.backup.field == "characters"
    assert prepared.backup.original_value == 1
    assert prepared.backup.candidate_value == 3
    assert prepared.backup.character_codes == ("Ranger", "Mage")
    summary = prepared.summary()
    assert summary["field"] == "gameData.heroUnlock"
    assert summary["experimental"] is True
    assert summary["validation"]["only_characters_changed"] is True
    assert summary["changed_fields"] == [
        "gameData.heroUnlock.Ranger",
        "gameData.heroUnlock.Mage",
    ]

    bundle = lab.store.load(prepared.backup.id)
    assert bundle.candidate == prepared.edit.candidate
    assert bundle.record.character_codes == ("Ranger", "Mage")

    confirmed = lab.confirm(prepared.backup.id, prepared.candidate_sha256)
    assert confirmed.persisted is True
    assert confirmed.remote_characters == 3
    assert confirmed.remote_gems == 1000
    assert confirmed.remote_value == 3
    uploaded = json.loads(provider.payload)
    assert uploaded["gameData"]["heroUnlock"]["Ranger"] is True
    assert uploaded["gameData"]["heroUnlock"]["Mage"] is True
    assert uploaded["gameData"]["gems"] == 1000
    assert uploaded["gameData"]["fishChip"] == 3
    assert uploaded["itemData"]["materials"] == {"material_fish": 3, "material_ticket": 5}

    verified = lab.verify(prepared.backup.id)
    assert verified.matches_candidate is True
    assert verified.remote_characters == 3

    restored = lab.restore(prepared.backup.id)
    assert restored.persisted is True
    assert restored.remote_characters == 1
    restored_document = json.loads(provider.payload)
    assert restored_document["gameData"]["heroUnlock"]["Ranger"] is False
    assert restored_document["gameData"]["heroUnlock"]["Knight"] is True
    assert restored_document["gameData"]["heroLevel"]["Knight"] == 2


def test_backup_store_rejects_a_record_with_unknown_selection(tmp_path):
    provider = FixedProvider(payload())
    lab = service(tmp_path, provider)
    prepared = lab.prepare_characters(["Ranger"])
    record_path = tmp_path / "backups" / prepared.backup.id / "record.json"
    record = json.loads(record_path.read_text())
    record["character_codes"] = ["NoExiste"]
    record_path.write_text(canonical(record).decode())
    with pytest.raises(BackupIntegrityError):
        lab.store.load(prepared.backup.id)


def test_gems_and_fish_edits_still_work_with_character_records(tmp_path):
    provider = FixedProvider(payload())
    lab = service(tmp_path, provider, write=True)
    gem_edit = lab.prepare(1001)
    assert gem_edit.changed is True
    lab.confirm(gem_edit.backup.id, gem_edit.candidate_sha256)
    assert json.loads(provider.payload)["gameData"]["gems"] == 1001

    fish_edit = lab.prepare_fish_chip(7)
    assert fish_edit.changed is True
    lab.confirm(fish_edit.backup.id, fish_edit.candidate_sha256)
    after = json.loads(provider.payload)
    assert after["gameData"]["fishChip"] == 7
    assert after["itemData"]["materials"]["material_fish"] == 7
    assert after["gameData"]["heroUnlock"]["Knight"] is True
    assert after["gameData"]["heroUnlock"]["Ranger"] is False
import json
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.catalogs import load_character_catalog
from app.cloud import skin_editor
from app.cloud.backup_store import BackupIntegrityError, LabBackupStore
from app.cloud.lab_service import CloudLabService, LabNoChanges
from app.cloud.provider import AcquiredCloudSave, CloudSaveMetadata
from app.cloud.skin_editor import (
    IncompleteSkinStructure,
    InvalidSkinSelection,
    OutdatedSkinDraft,
    SkinCatalogMissing,
    SkinFieldMissing,
    UnknownSkinCharacter,
    UnknownSkinIndex,
    UnsupportedSkinStructure,
    prepare_skin_unlock_edit,
    read_skins,
    require_skin_write_compatibility,
    skin_catalog,
)

FIXTURE = Path(__file__).parent / "fixtures" / "cloud-save-gems.json"
CATALOG = load_character_catalog()
CODES = tuple(CATALOG["codes"])
SKINS = {
    code: tuple(CATALOG["characters"][code]["skins"]) for code in CODES
}


def canonical(document: dict) -> bytes:
    return json.dumps(
        document, ensure_ascii=False, sort_keys=True, separators=(", ", ": "), allow_nan=False
    ).encode()


def skin_entries(code: str, *, unlocked=()):
    return [
        {"Key": skin["index"], "Value": 1 if skin["index"] in unlocked else 0}
        for skin in SKINS[code]
    ]


def document(*, unlocked=("Knight",), skin_unlocked=None, selected=None) -> dict:
    data = json.loads(FIXTURE.read_bytes())
    data["gameData"]["gems"] = 1000
    data["gameData"]["heroUnlock"] = {code: code in unlocked for code in CODES}
    data["gameData"]["heroLevel"] = {code: 0 for code in CODES}
    data["gameData"]["heroLevel"]["Knight"] = 2
    data["gameData"]["heroSkill"] = {code: 0 for code in CODES}
    data["gameData"]["heroSkillUnlock"] = {
        code: [
            {"Key": skill["index"], "Value": skill["index"] == 0}
            for skill in CATALOG["characters"][code]["skills"]
        ]
        for code in CODES
    }
    extra = skin_unlocked or {}
    data["gameData"]["skinLock"] = {
        code: skin_entries(code, unlocked=(0, *extra.get(code, ()))) for code in CODES
    }
    data["gameData"]["currentSkinDatas"] = {"Knight": 1} if selected is None else selected
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


class FakeUploader:
    def __init__(self, provider: FixedProvider):
        self.provider = provider
        self.calls: list[bytes] = []

    def upload(self, aggregate: bytes):
        self.calls.append(aggregate)
        self.provider.payload = aggregate
        return SimpleNamespace(status=200, accepted=True)


def service(tmp_path: Path, provider: FixedProvider, *, write=False):
    uploader = FakeUploader(provider) if write else None
    return CloudLabService(
        provider,
        LabBackupStore(tmp_path / "backups"),
        uploader=uploader,
        write_enabled=write,
        admin_configured=True,
    )


def test_catalog_contains_802_skins_with_varying_counts():
    catalog = skin_catalog()
    assert catalog.total == 802
    assert len(catalog.codes) == 42
    assert len(catalog.indices["Knight"]) == 39
    assert len(catalog.indices["Beheaded"]) == 1
    assert catalog.names[("Knight", 0)] == "Knight"
    assert catalog.keys[("Knight", 0)] == "c0_skin0"


def test_reads_skins_and_selected_skin_without_touching_the_copy():
    original = payload(selected={"Knight": 1, "Ranger": 0})
    snapshot = read_skins(original)
    assert snapshot.total == 802
    assert len(snapshot.unlocked) == 42
    assert snapshot.characters_with_data == 42
    assert len(snapshot.selected) == 2
    assert bytes(original) == payload(selected={"Knight": 1, "Ranger": 0})


def test_prepares_individual_skin_unlock_and_changes_only_the_selected_value():
    original = payload()
    edit = prepare_skin_unlock_edit(original, [{"code": "Knight", "index": 1}])
    assert edit.changed is True
    assert edit.original_unlocked == tuple(
        skin_editor.SkinRef(code=code, index=0) for code in CODES
    )
    assert edit.newly_unlocked == (skin_editor.SkinRef("Knight", 1),)
    assert edit.affected_codes == ("Knight",)
    assert edit.changed_fields == ("gameData.skinLock.Knight[1]",)
    modified = json.loads(edit.candidate)
    assert modified["gameData"]["skinLock"]["Knight"][1]["Value"] == 1
    assert modified["gameData"]["currentSkinDatas"] == {"Knight": 1}
    assert modified["gameData"]["heroUnlock"] == document()["gameData"]["heroUnlock"]
    assert modified["gameData"]["heroLevel"] == document()["gameData"]["heroLevel"]
    assert modified["gameData"]["heroSkillUnlock"] == document()["gameData"]["heroSkillUnlock"]
    assert modified["gameData"]["gems"] == 1000


def test_prepares_multiple_and_per_character_without_touching_other_skins():
    original = payload()
    edit = prepare_skin_unlock_edit(
        original,
        [
            {"code": "Knight", "index": 1},
            {"code": "Knight", "index": 2},
            {"code": "Ranger", "index": 1},
        ],
    )
    modified = json.loads(edit.candidate)
    assert [entry["Value"] for entry in modified["gameData"]["skinLock"]["Knight"][:3]] == [1, 1, 1]
    assert modified["gameData"]["skinLock"]["Ranger"][1]["Value"] == 1
    assert modified["gameData"]["skinLock"]["Ranger"][2]["Value"] == 0
    assert edit.changed_fields == (
        "gameData.skinLock.Knight[1]",
        "gameData.skinLock.Knight[2]",
        "gameData.skinLock.Ranger[1]",
    )


def test_massive_selection_changes_every_pending_skin_and_preserves_prior_values():
    original = payload(skin_unlocked={"Warlock": (3,)})
    selections = [
        {"code": code, "index": skin["index"]}
        for code in CODES
        for skin in SKINS[code]
        if not (skin["index"] == 0 or (code == "Warlock" and skin["index"] == 3))
    ]
    edit = prepare_skin_unlock_edit(original, selections)
    modified = json.loads(edit.candidate)
    assert edit.changed is True
    assert len(edit.newly_unlocked) == len(selections)
    assert edit.new_unlocked[-1] == skin_editor.SkinRef("LadyChef", 3)
    for code in CODES:
        values = [entry["Value"] for entry in modified["gameData"]["skinLock"][code]]
        assert values == [1] * len(values)
    assert modified["gameData"]["currentSkinDatas"] == {"Knight": 1}


def test_locked_character_is_reported_but_not_unlocked():
    original = payload(unlocked=("Knight",))
    edit = prepare_skin_unlock_edit(original, [{"code": "Ranger", "index": 1}])
    assert edit.locked_character_codes == ("Ranger",)
    modified = json.loads(edit.candidate)
    assert modified["gameData"]["heroUnlock"]["Ranger"] is False
    assert modified["gameData"]["heroUnlock"]["Knight"] is True


def test_unknown_and_duplicate_selections_are_rejected():
    original = payload()
    for selections, error in (
        ([{"code": "NoExiste", "index": 0}], UnknownSkinCharacter),
        ([{"code": "Knight", "index": 999}], UnknownSkinIndex),
        ([{"code": "Knight", "index": 1}] * 2, InvalidSkinSelection),
        ([], InvalidSkinSelection),
        ([{"code": "Knight", "index": "1"}], InvalidSkinSelection),
    ):
        with pytest.raises(error):
            prepare_skin_unlock_edit(original, selections)


def test_missing_field_and_unsupported_structures_are_rejected():
    data = document()
    del data["gameData"]["skinLock"]
    with pytest.raises(SkinFieldMissing):
        read_skins(canonical(data))

    data = document()
    data["gameData"]["skinLock"] = []
    with pytest.raises(UnsupportedSkinStructure):
        read_skins(canonical(data))

    data = document()
    data["gameData"]["skinLock"]["Knight"] = {"Key": 0, "Value": 1}
    with pytest.raises(UnsupportedSkinStructure):
        read_skins(canonical(data))

    data = document()
    data["gameData"]["skinLock"]["Knight"][0]["Value"] = True
    with pytest.raises(UnsupportedSkinStructure):
        read_skins(canonical(data))

    data = document()
    data["gameData"]["skinLock"]["NoExiste"] = [{"Key": 0, "Value": 0}]
    with pytest.raises(UnsupportedSkinStructure):
        read_skins(canonical(data))

    data = document()
    data["gameData"]["skinLock"]["Knight"][0]["Key"] = 999
    with pytest.raises(UnsupportedSkinStructure):
        read_skins(canonical(data))


def test_missing_selected_position_is_rejected_without_creating_entries():
    data = document()
    data["gameData"]["skinLock"]["Knight"] = data["gameData"]["skinLock"]["Knight"][:1]
    with pytest.raises(IncompleteSkinStructure):
        prepare_skin_unlock_edit(canonical(data), [{"code": "Knight", "index": 1}])
    del data["gameData"]["skinLock"]["Ranger"]
    with pytest.raises(IncompleteSkinStructure):
        prepare_skin_unlock_edit(canonical(data), [{"code": "Ranger", "index": 1}])


def test_missing_catalog_is_reported(monkeypatch):
    monkeypatch.setattr(
        skin_editor,
        "load_character_catalog",
        lambda: {"available": False, "error": "catalog_missing"},
    )
    with pytest.raises(SkinCatalogMissing):
        skin_catalog()


def test_idempotent_selection_returns_identical_bytes_without_changes():
    original = payload()
    selected = [{"code": "Knight", "index": 0}]
    edit = prepare_skin_unlock_edit(original, selected)
    assert edit.changed is False
    assert edit.candidate == original
    assert edit.newly_unlocked == ()
    assert edit.binary.first_difference is None
    require_skin_write_compatibility(original, selected, original)


def test_special_negative_value_is_only_replaced_when_explicitly_selected():
    original = payload()
    data = json.loads(original)
    data["gameData"]["skinLock"]["Knight"][5]["Value"] = -13
    original = canonical(data)
    edit = prepare_skin_unlock_edit(original, [{"code": "Knight", "index": 1}])
    modified = json.loads(edit.candidate)
    assert modified["gameData"]["skinLock"]["Knight"][5]["Value"] == -13
    assert modified["gameData"]["skinLock"]["Knight"][1]["Value"] == 1

    selected = prepare_skin_unlock_edit(original, [{"code": "Knight", "index": 5}])
    assert json.loads(selected.candidate)["gameData"]["skinLock"]["Knight"][5]["Value"] == 1


def test_outdated_draft_is_rejected():
    original = payload()
    edit = prepare_skin_unlock_edit(original, [{"code": "Knight", "index": 1}])
    with pytest.raises(OutdatedSkinDraft):
        require_skin_write_compatibility(original, [{"code": "Knight", "index": 2}], edit.candidate)


def test_prepare_confirm_verify_restore_and_backup_integrity(tmp_path):
    provider = FixedProvider(payload())
    lab = service(tmp_path, provider, write=True)
    prepared = lab.prepare_skins(
        [{"code": "Knight", "index": 1}, {"code": "Ranger", "index": 1}]
    )
    assert prepared.changed is True
    assert prepared.edit.locked_character_codes == ("Ranger",)
    summary = prepared.summary()
    assert summary["field"] == "gameData.skinLock"
    assert summary["experimental"] is True
    assert summary["validation"]["evidence_level"] == "E2"
    assert summary["validation"]["only_skins_changed"] is True
    assert summary["locked_character_codes"] == ["Ranger"]

    bundle = lab.store.load(prepared.backup.id)
    assert bundle.candidate == prepared.edit.candidate
    assert bundle.record.skin_selections == (("Knight", 1), ("Ranger", 1))

    confirmed = lab.confirm(prepared.backup.id, prepared.candidate_sha256)
    assert confirmed.persisted is True
    assert confirmed.remote_skins == 44
    assert confirmed.remote_characters is None
    assert confirmed.remote_skills is None
    uploaded = json.loads(provider.payload)
    assert uploaded["gameData"]["skinLock"]["Knight"][1]["Value"] == 1
    assert uploaded["gameData"]["skinLock"]["Ranger"][1]["Value"] == 1
    assert uploaded["gameData"]["currentSkinDatas"] == {"Knight": 1}
    assert uploaded["gameData"]["heroUnlock"]["Ranger"] is False
    assert uploaded["gameData"]["gems"] == 1000
    assert uploaded["gameData"]["fishChip"] == 3
    assert uploaded["itemData"]["materials"] == {"material_fish": 3, "material_ticket": 5}

    verified = lab.verify(prepared.backup.id)
    assert verified.matches_candidate is True
    assert verified.remote_skins == 44

    restored = lab.restore(prepared.backup.id)
    assert restored.persisted is True
    assert restored.remote_skins == 42
    restored_document = json.loads(provider.payload)
    assert restored_document["gameData"]["skinLock"] == document()["gameData"]["skinLock"]
    assert restored_document["gameData"]["currentSkinDatas"] == {"Knight": 1}

    record = prepared.backup
    with pytest.raises(BackupIntegrityError):
        lab.store.save(
            prepared.edit,
            remote_source="fake-remote",
            remote_size=record.original_size,
            remote_sha256=record.original_sha256,
            field="skins",
            original_value=42,
            new_value=44,
            skin_selections=[
                {"code": "Knight", "index": 1},
                {"code": "Knight", "index": 1},
            ],
        )


def test_no_change_backup_cannot_be_confirmed(tmp_path):
    provider = FixedProvider(payload())
    lab = service(tmp_path, provider, write=True)
    prepared = lab.prepare_skins([{"code": "Knight", "index": 0}])
    assert prepared.changed is False
    with pytest.raises(LabNoChanges):
        lab.confirm(prepared.backup.id, prepared.candidate_sha256)
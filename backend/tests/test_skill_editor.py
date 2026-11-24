import json
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.catalogs import load_character_catalog
from app.cloud import skill_editor
from app.cloud.backup_store import BackupIntegrityError, LabBackupStore
from app.cloud.lab_service import CloudLabService, LabNoChanges
from app.cloud.provider import AcquiredCloudSave, CloudSaveMetadata
from app.cloud.skill_editor import (
    IncompleteSkillStructure,
    InvalidSkillSelection,
    OutdatedSkillDraft,
    SkillCatalogMissing,
    SkillFieldMissing,
    SkillRef,
    UnknownSkillCharacter,
    UnknownSkillIndex,
    UnsupportedSkillStructure,
    prepare_skill_unlock_edit,
    read_skills,
    require_skill_write_compatibility,
    skill_catalog,
)

FIXTURE = Path(__file__).parent / "fixtures" / "cloud-save-gems.json"
CATALOG = load_character_catalog()
CODES = tuple(CATALOG["codes"])
SKILL_INDICES = {
    code: tuple(skill["index"] for skill in CATALOG["characters"][code]["skills"])
    for code in CODES
}
SKILL_NAMES = {
    (code, skill["index"]): skill["name"]
    for code in CODES
    for skill in CATALOG["characters"][code]["skills"]
}


def canonical(document: dict) -> bytes:
    return json.dumps(
        document, ensure_ascii=False, sort_keys=True, separators=(", ", ": "), allow_nan=False
    ).encode()


def skill_entries(code: str, *, unlocked=()):
    return [
        {"Key": index, "Value": index in unlocked}
        for index in SKILL_INDICES[code]
    ]


def document(*, unlocked=("Knight",), skill_unlocked=None, selected=None) -> dict:
    data = json.loads(FIXTURE.read_bytes())
    data["gameData"]["gems"] = 1000
    data["gameData"]["heroUnlock"] = {code: code in unlocked for code in CODES}
    data["gameData"]["heroLevel"] = {code: 0 for code in CODES}
    data["gameData"]["heroLevel"]["Knight"] = 2
    data["gameData"]["heroSkill"] = {
        code: selected.get(code, 0) if selected else 0 for code in CODES
    }
    data["gameData"]["heroSkillUnlock"] = {
        code: skill_entries(code, unlocked=skill_unlocked or (0,)) for code in CODES
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


def test_catalog_contains_105_skills_with_varying_counts():
    catalog = skill_catalog()
    assert catalog.total == 105
    assert len(catalog.codes) == 42
    assert len(catalog.indices["Transcendent"]) == 2
    assert len(catalog.indices["Envoy"]) == 1
    assert len(catalog.indices["Knight"]) == 3
    assert catalog.names[("Knight", 0)] == SKILL_NAMES[("Knight", 0)]


def test_reads_skills_and_selected_skill_without_touching_the_copy():
    original = payload(selected={"Knight": 1, "Envoy": 0})
    snapshot = read_skills(original)
    assert snapshot.total == 105
    assert len(snapshot.unlocked) == 42
    assert snapshot.characters_with_data == 42
    assert len(snapshot.selected) == 42
    assert SkillRef("Knight", 1) in snapshot.selected
    assert SkillRef("Envoy", 0) in snapshot.selected
    assert SkillRef("Knight", 0) not in snapshot.selected
    assert snapshot.sha256 == sha256(original).hexdigest()
    assert payload(selected={"Knight": 1, "Envoy": 0}) == original


def test_single_unlock_changes_only_the_selected_skill():
    original = payload()
    before = json.loads(original)
    edit = prepare_skill_unlock_edit(original, [{"code": "Knight", "index": 1}])
    assert edit.changed is True
    assert len(edit.original_unlocked) == 42
    assert all(ref.index == 0 for ref in edit.original_unlocked)
    assert [(ref.code, ref.index) for ref in edit.newly_unlocked] == [("Knight", 1)]
    assert edit.affected_codes == ("Knight",)
    assert edit.changed_fields == ("gameData.heroSkillUnlock.Knight[1]",)
    after = json.loads(edit.candidate)
    assert after["gameData"]["heroSkillUnlock"]["Knight"][1]["Value"] is True
    assert after["gameData"]["heroSkillUnlock"]["Knight"][0]["Value"] is True
    assert after["gameData"]["heroSkill"] == before["gameData"]["heroSkill"]
    # Todos los campos ajenos a heroSkillUnlock permanecen idénticos.
    before_without = json.loads(original)
    after_without = json.loads(edit.candidate)
    before_without["gameData"].pop("heroSkillUnlock")
    after_without["gameData"].pop("heroSkillUnlock")
    assert after_without == before_without


def test_multiple_skills_of_one_character_and_of_different_characters():
    original = payload()
    edit = prepare_skill_unlock_edit(
        original,
        [
            {"code": "Knight", "index": 1},
            {"code": "Knight", "index": 2},
            {"code": "Transcendent", "index": 1},
        ],
    )
    assert [(ref.code, ref.index) for ref in edit.newly_unlocked] == [
        ("Knight", 1),
        ("Knight", 2),
        ("Transcendent", 1),
    ]
    assert edit.affected_codes == ("Knight", "Transcendent")
    after = json.loads(edit.candidate)
    assert [entry["Value"] for entry in after["gameData"]["heroSkillUnlock"]["Knight"]] == [
        True,
        True,
        True,
    ]
    assert [entry["Value"] for entry in after["gameData"]["heroSkillUnlock"]["Transcendent"]] == [
        True,
        True,
    ]


def test_massive_unlock_preserves_previous_and_equipped_skill():
    original = payload(selected={"Knight": 2, "Envoy": 0})
    all_locked = [
        {"code": code, "index": index}
        for code in CODES
        for index in SKILL_INDICES[code]
        if index != 0
    ]
    edit = prepare_skill_unlock_edit(original, all_locked)
    assert len(all_locked) == 63
    assert edit.changed is True
    assert len(edit.new_unlocked) == 105
    assert len(edit.changed_fields) == 63
    after = json.loads(edit.candidate)
    assert after["gameData"]["heroSkill"] == {"Knight": 2, "Envoy": 0, **{
        code: 0 for code in CODES if code not in {"Knight", "Envoy"}
    }}
    assert all(
        entry["Value"] is True
        for entries in after["gameData"]["heroSkillUnlock"].values()
        for entry in entries
    )


def test_idempotent_selection_returns_the_same_bytes():
    original = payload()
    edit = prepare_skill_unlock_edit(original, [{"code": "Knight", "index": 0}])
    assert edit.changed is False
    assert edit.candidate == original
    assert edit.newly_unlocked == ()
    assert edit.changed_fields == ()


def test_rejects_invalid_unknown_and_duplicate_selections():
    original = payload()
    with pytest.raises(InvalidSkillSelection):
        prepare_skill_unlock_edit(original, [])
    with pytest.raises(InvalidSkillSelection):
        prepare_skill_unlock_edit(original, [{"code": "Knight", "index": 1}] * 2)
    with pytest.raises(UnknownSkillCharacter):
        prepare_skill_unlock_edit(original, [{"code": "NoExiste", "index": 0}])
    with pytest.raises(UnknownSkillIndex):
        prepare_skill_unlock_edit(original, [{"code": "Envoy", "index": 1}])
    with pytest.raises(UnknownSkillIndex):
        prepare_skill_unlock_edit(original, [{"code": "Knight", "index": 3}])


def test_rejects_incomplete_structures_without_creating_anything():
    original = payload()
    missing_code = json.loads(original)
    missing_code["gameData"]["heroSkillUnlock"].pop("Envoy")
    with pytest.raises(IncompleteSkillStructure):
        prepare_skill_unlock_edit(canonical(missing_code), [{"code": "Envoy", "index": 0}])

    missing_entry = json.loads(original)
    missing_entry["gameData"]["heroSkillUnlock"]["Knight"] = [
        entry for entry in missing_entry["gameData"]["heroSkillUnlock"]["Knight"]
        if entry["Key"] != 1
    ]
    with pytest.raises(IncompleteSkillStructure):
        prepare_skill_unlock_edit(canonical(missing_entry), [{"code": "Knight", "index": 1}])


def test_rejects_incompatible_skill_structures():
    original = payload()
    cases = []
    not_dict = json.loads(original)
    not_dict["gameData"]["heroSkillUnlock"] = []
    cases.append(not_dict)
    not_list = json.loads(original)
    not_list["gameData"]["heroSkillUnlock"]["Knight"] = {}
    cases.append(not_list)
    bad_key = json.loads(original)
    bad_key["gameData"]["heroSkillUnlock"]["Knight"][0]["Key"] = True
    cases.append(bad_key)
    bad_value = json.loads(original)
    bad_value["gameData"]["heroSkillUnlock"]["Knight"][0]["Value"] = 1
    cases.append(bad_value)
    duplicate = json.loads(original)
    duplicate["gameData"]["heroSkillUnlock"]["Knight"][1]["Key"] = 0
    cases.append(duplicate)
    for case in cases:
        with pytest.raises(UnsupportedSkillStructure):
            prepare_skill_unlock_edit(canonical(case), [{"code": "Knight", "index": 1}])


def test_missing_field_is_reported():
    data = json.loads(payload())
    data["gameData"].pop("heroSkillUnlock")
    with pytest.raises(SkillFieldMissing):
        prepare_skill_unlock_edit(canonical(data), [{"code": "Knight", "index": 1}])


def test_absent_and_corrupt_catalog_block_read_and_write(monkeypatch, tmp_path):
    missing = load_character_catalog(tmp_path / "missing.json")
    assert missing["available"] is False
    assert missing["error"] == "catalog_missing"
    corrupt = tmp_path / "corrupt.json"
    corrupt.write_text("{", encoding="utf-8")
    invalid = load_character_catalog(corrupt)
    assert invalid["available"] is False
    assert invalid["error"] == "catalog_invalid_json"

    monkeypatch.setattr(
        skill_editor,
        "load_character_catalog",
        lambda: {"available": False, "error": "catalog_missing", "codes": []},
    )
    with pytest.raises(SkillCatalogMissing):
        prepare_skill_unlock_edit(payload(), [{"code": "Knight", "index": 1}])
    with pytest.raises(SkillCatalogMissing):
        read_skills(payload())


def test_stale_skill_backup_selection_is_rejected():
    original = payload()
    edit = prepare_skill_unlock_edit(
        original, [{"code": "Knight", "index": 1}, {"code": "Knight", "index": 2}]
    )
    with pytest.raises(OutdatedSkillDraft):
        require_skill_write_compatibility(
            original, [{"code": "Knight", "index": 1}], edit.candidate
        )
    require_skill_write_compatibility(
        original,
        [{"code": "Knight", "index": 1}, {"code": "Knight", "index": 2}],
        edit.candidate,
    )


def test_prepare_backup_confirm_verify_and_restore(tmp_path):
    provider = FixedProvider(payload(selected={"Knight": 2}))
    lab = service(tmp_path, provider, write=True)
    prepared = lab.prepare_skills([
        {"code": "Knight", "index": 1},
        {"code": "Transcendent", "index": 1},
    ])
    assert prepared.changed is True
    assert prepared.backup.field == "skills"
    assert prepared.backup.original_value == 42
    assert prepared.backup.candidate_value == 44
    assert prepared.backup.skill_selections == (("Knight", 1), ("Transcendent", 1))
    summary = prepared.summary()
    assert summary["field"] == "gameData.heroSkillUnlock"
    assert summary["experimental"] is True
    assert summary["validation"]["only_skills_changed"] is True
    assert summary["changed_fields"] == [
        "gameData.heroSkillUnlock.Knight[1]",
        "gameData.heroSkillUnlock.Transcendent[1]",
    ]

    bundle = lab.store.load(prepared.backup.id)
    assert bundle.candidate == prepared.edit.candidate
    assert bundle.record.skill_selections == (("Knight", 1), ("Transcendent", 1))

    confirmed = lab.confirm(prepared.backup.id, prepared.candidate_sha256)
    assert confirmed.persisted is True
    assert confirmed.remote_skills == 44
    assert confirmed.remote_characters is None
    assert confirmed.remote_gems == 1000
    uploaded = json.loads(provider.payload)
    assert uploaded["gameData"]["heroSkillUnlock"]["Knight"][1]["Value"] is True
    assert uploaded["gameData"]["heroSkillUnlock"]["Transcendent"][1]["Value"] is True
    assert uploaded["gameData"]["heroSkill"] == {"Knight": 2, **{
        code: 0 for code in CODES if code != "Knight"
    }}
    assert uploaded["gameData"]["gems"] == 1000
    assert uploaded["gameData"]["fishChip"] == 3
    assert uploaded["itemData"]["materials"] == {"material_fish": 3, "material_ticket": 5}

    verified = lab.verify(prepared.backup.id)
    assert verified.matches_candidate is True
    assert verified.remote_skills == 44

    restored = lab.restore(prepared.backup.id)
    assert restored.persisted is True
    assert restored.remote_skills == 42
    restored_document = json.loads(provider.payload)
    assert restored_document["gameData"]["heroSkillUnlock"] == document()["gameData"]["heroSkillUnlock"]
    assert restored_document["gameData"]["heroSkill"] == {"Knight": 2, **{
        code: 0 for code in CODES if code != "Knight"
    }}


def test_no_change_backup_cannot_be_confirmed(tmp_path):
    provider = FixedProvider(payload())
    lab = service(tmp_path, provider, write=True)
    prepared = lab.prepare_skills([{"code": "Knight", "index": 0}])
    assert prepared.changed is False
    with pytest.raises(LabNoChanges):
        lab.confirm(prepared.backup.id, prepared.candidate_sha256)


def test_backup_record_rejects_unknown_skill_field_values(tmp_path):
    provider = FixedProvider(payload())
    lab = service(tmp_path, provider, write=True)
    prepared = lab.prepare_skills([{"code": "Knight", "index": 1}])
    record = prepared.backup
    with pytest.raises(BackupIntegrityError):
        lab.store.save(
            prepared.edit,
            remote_source="fake-remote",
            remote_size=record.original_size,
            remote_sha256=record.original_sha256,
            field="skills",
            original_value=42,
            new_value=43,
            skill_selections=[{"code": "Knight", "index": 1}, {"code": "Knight", "index": 1}],
        )
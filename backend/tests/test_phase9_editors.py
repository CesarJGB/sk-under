import json
from hashlib import sha256
from pathlib import Path

import pytest

from app.cloud.backup_store import LabBackupStore
from app.cloud.lab_service import CloudLabService
from app.cloud.blueprint_editor import (
    InvalidBlueprintPlan,
    normalize_blueprint_plan,
    prepare_blueprint_edit,
    read_blueprints,
)
from app.cloud.hero_level_editor import (
    InvalidHeroLevelPlan,
    normalize_hero_level_plan,
    prepare_hero_level_edit,
    read_hero_levels,
)
from app.cloud.pet_affinity_editor import (
    InvalidPetAffinityPlan,
    normalize_pet_affinity_plan,
    prepare_pet_affinity_edit,
    read_pet_affinity,
)
from app.cloud.unified_editor import InvalidUnifiedPlan, prepare_unified_edit

FIXTURE = Path(__file__).parent / "fixtures" / "cloud-save-gems.json"


def canonical(document: dict) -> bytes:
    return json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(", ", ": ")).encode()


def document() -> dict:
    data = json.loads(FIXTURE.read_bytes())
    data["gameData"]["heroUnlock"] = {"Knight": True, "Ranger": False}
    data["gameData"]["heroLevel"] = {"Knight": 0, "Ranger": 3, "UnknownHero": 0}
    data["statisticData"]["event2Count"] = {
        "pet_0_intimacy": 200,
        "pet_0_full_intimacy": 0,
        "pet_0_action_unlock": 0,
        "pet_2_intimacy": 200,
        "pet_2_full_intimacy": 0,
        "pet_30_intimacy": 150,
        "pet_30_full_intimacy": 0,
        "pet_27_intimacy": 240,
        "pet_full_intimacy": 1,
        "unrelated_counter": 9,
    }
    data["itemData"]["blueprints"] = {
        "blueprint_multi_room_skin_0": "Researched",
        "multi_room_skin_1": "Got",
        "legacy_unknown": "Researched",
    }
    return data


def source() -> bytes:
    return canonical(document())


def test_hero_level_reader_edit_and_current_source_restoration():
    original = source()
    snapshot = read_hero_levels(original)
    entries = {row["id"]: row for row in snapshot["entries"]}
    assert snapshot["max"] == 7
    assert entries["Knight"]["level"] == 0
    assert entries["Knight"]["unlocked"] is True
    assert entries["Ranger"]["level"] == 3
    assert "UnknownHero" not in entries

    edit = prepare_hero_level_edit(original, {"Knight": 7, "Ranger": 5})
    after = json.loads(edit.candidate)
    assert after["gameData"]["heroLevel"] == {"Knight": 7, "Ranger": 5, "UnknownHero": 0}
    assert after["gameData"]["heroUnlock"] == {"Knight": True, "Ranger": False}
    assert set(edit.changed_fields) == {"gameData.heroLevel.Knight", "gameData.heroLevel.Ranger"}
    assert edit.original == original and original == source()
    assert prepare_hero_level_edit(original, {"Knight": 7, "Ranger": 5}).candidate == edit.candidate


def test_hero_level_rejects_unknown_out_of_range_lowering_and_missing_field():
    with pytest.raises(InvalidHeroLevelPlan):
        normalize_hero_level_plan({"UnknownHero": 1})
    with pytest.raises(InvalidHeroLevelPlan):
        normalize_hero_level_plan({"Knight": 8})
    with pytest.raises(Exception):
        prepare_hero_level_edit(source(), {"Knight": -1})
    with pytest.raises(Exception):
        prepare_hero_level_edit(source(), {"Ranger": 2})
    data = document()
    del data["gameData"]["heroLevel"]
    with pytest.raises(Exception):
        prepare_hero_level_edit(canonical(data), {"Knight": 1})


def test_pet_affinity_maximizes_known_pet_and_preserves_unrelated_counters():
    original = source()
    snapshot = read_pet_affinity(original)
    entries = {row["id"]: row for row in snapshot["entries"]}
    assert entries["Cat"]["max"] == 240 and entries["Cat"]["editable"] is True
    assert entries["Pig"]["max"] == 240 and entries["Pig"]["editable"] is True
    assert entries["Cat4"]["max"] == 180 and entries["Cat4"]["intimacy"] == 150
    assert entries["Serenade"]["max"] is None and entries["Serenade"]["editable"] is False
    assert snapshot["read_only"] is False

    edit = prepare_pet_affinity_edit(original, {"Cat": 240})
    counters = json.loads(edit.candidate)["statisticData"]["event2Count"]
    assert counters["pet_0_intimacy"] == 240
    assert counters["pet_0_full_intimacy"] == 1
    assert counters["pet_0_action_unlock"] == 0
    assert counters["pet_2_intimacy"] == 200 and counters["pet_2_full_intimacy"] == 0
    assert counters["pet_30_intimacy"] == 150 and counters["pet_30_full_intimacy"] == 0
    assert counters["pet_full_intimacy"] == 1
    assert counters["unrelated_counter"] == 9
    assert set(edit.changed_fields) == {
        "statisticData.event2Count.pet_0_intimacy",
        "statisticData.event2Count.pet_0_full_intimacy",
    }
    assert edit.original == original


def test_pet_affinity_rejects_unknown_limit_lowering_and_inconsistent_full():
    with pytest.raises(InvalidPetAffinityPlan):
        normalize_pet_affinity_plan({"Serenade": 240})
    with pytest.raises(Exception):
        prepare_pet_affinity_edit(source(), {"Cat": 199})
    with pytest.raises(Exception):
        prepare_pet_affinity_edit(source(), {"Pig": 180})
    with pytest.raises(Exception):
        normalize_pet_affinity_plan({"Cat": 241})


def test_blueprints_resolve_exact_and_legacy_alias_without_touching_unknown_keys():
    original = source()
    snapshot = read_blueprints(original)
    entries = {row["id"]: row for row in snapshot["entries"]}
    assert entries["blueprint_multi_room_skin_0"]["key"] == "blueprint_multi_room_skin_0"
    assert entries["blueprint_multi_room_skin_1"]["key"] == "multi_room_skin_1"
    assert entries["blueprint_multi_room_skin_0"]["status"] == "Researched"
    assert snapshot["unmatched"] == ["legacy_unknown"]

    edit = prepare_blueprint_edit(original, {
        "blueprint_multi_room_skin_0": "Got",
        "blueprint_multi_room_skin_1": "Researched",
    })
    after = json.loads(edit.candidate)["itemData"]["blueprints"]
    assert after["blueprint_multi_room_skin_0"] == "Got"
    assert after["multi_room_skin_1"] == "Researched"
    assert after["legacy_unknown"] == "Researched"
    assert set(edit.changed_fields) == {
        "itemData.blueprints.blueprint_multi_room_skin_0",
        "itemData.blueprints.multi_room_skin_1",
    }


def test_blueprints_reject_absent_or_invalid_status():
    with pytest.raises(InvalidBlueprintPlan):
        normalize_blueprint_plan({"blueprint_not_a_real_id": "Got"})
    with pytest.raises(InvalidBlueprintPlan):
        normalize_blueprint_plan({"blueprint_multi_room_skin_0": "Unknown"})
    with pytest.raises(Exception):
        prepare_blueprint_edit(source(), {"blueprint_multi_room_skin_2": "Researched"})


def test_unified_batch_combines_unlock_levels_affinity_and_blueprints():
    original = source()
    plan = {
        "characters": ["Ranger"],
        "hero_levels": [{"code": "Knight", "level": 7}],
        "pet_affinity": [{"code": "Cat", "value": 240}],
        "blueprints": [{"id": "blueprint_multi_room_skin_0", "status": "Got"}],
    }
    edit = prepare_unified_edit(original, plan)
    assert edit.steps == ("characters", "hero_levels", "pet_affinity", "blueprints")
    assert edit.change_count == 5
    assert len(edit.changed_fields) == len(set(edit.changed_fields)) == 5
    after = json.loads(edit.candidate)
    assert after["gameData"]["heroUnlock"]["Ranger"] is True
    assert after["gameData"]["heroLevel"]["Knight"] == 7
    assert after["statisticData"]["event2Count"]["pet_0_intimacy"] == 240
    assert after["itemData"]["blueprints"]["blueprint_multi_room_skin_0"] == "Got"
    assert edit.original == original





def test_unified_service_writes_one_backup_one_upload_and_restores(tmp_path):
    from test_cloud_lab_api import FakeProvider, FakeUploader

    original = source()
    provider = FakeProvider(original)
    uploader = FakeUploader(provider)
    service = CloudLabService(
        provider, LabBackupStore(tmp_path / "backups"), uploader=uploader,
        write_enabled=True, admin_configured=True,
    )
    plan = {
        "hero_levels": [{"code": "Knight", "level": 7}],
        "pet_affinity": [{"code": "Cat", "value": 240}],
        "blueprints": [{"id": "blueprint_multi_room_skin_0", "status": "Got"}],
    }
    prepared = service.prepare_unified(plan, expected_source=sha256(original).hexdigest())
    assert prepared.backup.field == "unified"
    assert len(service.backups()) == 1
    assert len(uploader.calls) == 0
    result = service.confirm(prepared.backup.id, prepared.edit.candidate_sha256)
    assert result.persisted is True
    assert len(uploader.calls) == 1
    persisted = json.loads(provider.payload)
    assert persisted["gameData"]["heroLevel"]["Knight"] == 7
    assert persisted["statisticData"]["event2Count"]["pet_0_intimacy"] == 240
    assert persisted["itemData"]["blueprints"]["blueprint_multi_room_skin_0"] == "Got"
    restored = service.restore(prepared.backup.id)
    assert restored.persisted is True
    assert provider.payload == original


def test_unified_candidate_sha_and_plan_replay_are_stable():
    original = source()
    plan = {"hero_levels": [{"code": "Ranger", "level": 7}]}
    first = prepare_unified_edit(original, plan)
    second = prepare_unified_edit(original, plan)
    assert first.candidate_sha256 == sha256(first.candidate).hexdigest()
    assert first.candidate == second.candidate
    assert first.change_count == 1
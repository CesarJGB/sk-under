import json
from hashlib import sha256
from pathlib import Path

import pytest

from app.catalogs.kill_effects import load_kill_effect_catalog
from app.catalogs.weapon_skins import load_weapon_skin_catalog
from app.catalogs.weapons import load_weapon_catalog
from app.cloud.backup_store import LabBackupStore
from app.cloud.kill_effect_editor import (
    InvalidKillEffectSelection,
    UnknownKillEffect,
    prepare_kill_effect_unlock_edit,
    read_kill_effects,
    require_kill_effect_write_compatibility,
)
from app.cloud.unified_editor import prepare_unified_edit
from app.cloud.weapon_progression_editor import (
    InvalidWeaponSelection,
    UnknownWeapon,
    prepare_weapon_progression_edit,
    read_weapon_progression,
    require_weapon_progression_write_compatibility,
)
from app.cloud.weapon_skin_editor import (
    InvalidWeaponSkinSelection,
    UnknownWeaponSkin,
    prepare_weapon_skin_unlock_edit,
    read_weapon_skins,
    require_weapon_skin_write_compatibility,
)

FIXTURE = Path(__file__).parent / "fixtures" / "cloud-save-gems.json"
SKIN_CATALOG = load_weapon_skin_catalog()
EFFECT_CATALOG = load_kill_effect_catalog()
WEAPON_CATALOG = load_weapon_catalog()


def canonical(document: dict) -> bytes:
    return json.dumps(
        document, ensure_ascii=False, sort_keys=True, separators=(", ", ": "), allow_nan=False
    ).encode()


def document() -> dict:
    data = json.loads(FIXTURE.read_bytes())
    data["gameData"]["gems"] = 1000
    data["weaponEvolutionData"] = {
        "blindBoxOpenCount0": 0,
        "lastOpenMachineHistoryStr0": None,
        "favorWeapons": [],
        "weapons": {
            "weapon_311": {
                "Name": "weapon_311",
                "Level": 0,
                "CurrentSkinIndex": 1,
                "UnlockedSkins": ["weapon_311_s_1", "unknown_skin_9"],
            }
        },
    }
    data["miscData"] = {
        "unlockedKillEffectIds": [0, 1, 9],
        "equippedKillEffectIdByScene": [
            {"Key": 1, "Value": 1},
            {"Key": 0, "Value": 3},
        ],
        "currentReturnCount": 0,
    }
    return data


def payload() -> bytes:
    return canonical(document())


def advanced_account_document() -> dict:
    """Forma observada en la cuenta avanzada A: una arma y sin miscData."""
    data = json.loads(FIXTURE.read_bytes())
    data["weaponEvolutionData"] = {
        "blindBoxOpenCount0": 0,
        "lastOpenMachineHistoryStr0": None,
        "weapons": {
            "weapon_311": {
                "Name": "weapon_311",
                "Level": 0,
                "CurrentSkinIndex": 0,
                "UnlockedSkins": ["weapon_311_s_1"],
            }
        },
    }
    data.pop("miscData", None)
    return data


def new_account_document() -> dict:
    """Forma observada en la cuenta nueva B: dos armas y dos efectos."""
    data = json.loads(FIXTURE.read_bytes())
    data["weaponEvolutionData"] = {
        "blindBoxOpenCount0": 0,
        "favorWeapons": [],
        "weapons": {
            "weapon_363": {
                "Name": "weapon_363",
                "Level": 0,
                "CurrentSkinIndex": 0,
                "UnlockedSkins": ["weapon_363_s_1"],
            },
            "weapon_407": {
                "Name": "weapon_407",
                "Level": 0,
                "CurrentSkinIndex": 1,
                "UnlockedSkins": ["weapon_407_s_1"],
            },
        },
    }
    data["miscData"] = {
        "unlockedKillEffectIds": [0, 1],
        "equippedKillEffectIdByScene": [
            {"Key": 1, "Value": 1},
            {"Key": 0, "Value": 1},
        ],
    }
    return data


def test_catalogs_have_evidenced_counts():
    assert SKIN_CATALOG["counts"] == {"skins": 192, "weapons": 180}
    assert len(SKIN_CATALOG["ordered_skins"]) == 192
    assert EFFECT_CATALOG["counts"] == {"effects": 9}
    assert EFFECT_CATALOG["ordered_effects"] == list(range(9))
    assert EFFECT_CATALOG["unknown_ids"] == frozenset({9, 10})


def test_read_weapon_skins_preserves_unknown_ids_and_current_selection():
    snapshot = read_weapon_skins(payload())
    assert snapshot.total == 192
    assert snapshot.unlocked == ("weapon_311_s_1",)
    assert snapshot.unknown_skin_ids == ("unknown_skin_9",)
    assert snapshot.weapons_with_data == 1
    row = next(item for item in snapshot.items if item["id"] == "weapon_311_s_1")
    assert row["unlocked"] is True
    assert row["equipped"] is True
    assert row["current_skin_index"] == 1


def test_unlock_one_weapon_skin_and_create_missing_weapon_record():
    source = payload()
    edit = prepare_weapon_skin_unlock_edit(source, ["weapon_002_s_1"])
    assert edit.newly_unlocked == ("weapon_002_s_1",)
    assert edit.created_weapons == ("weapon_002",)
    assert edit.changed_fields == (
        "weaponEvolutionData.weapons.weapon_002.UnlockedSkins",
    )
    result = json.loads(edit.candidate)
    record = result["weaponEvolutionData"]["weapons"]["weapon_002"]
    assert record == {
        "Name": "weapon_002",
        "Level": 0,
        "CurrentSkinIndex": 0,
        "UnlockedSkins": ["weapon_002_s_1"],
    }
    assert result["weaponEvolutionData"]["weapons"]["weapon_311"] == {
        "Name": "weapon_311",
        "Level": 0,
        "CurrentSkinIndex": 1,
        "UnlockedSkins": ["weapon_311_s_1", "unknown_skin_9"],
    }
    require_weapon_skin_write_compatibility(source, ["weapon_002_s_1"], edit.candidate)


def test_unlock_several_and_all_weapon_skins_is_idempotent():
    source = payload()
    selected = ["weapon_002_s_1", "weapon_006_s_2", "weapon_223_s_3"]
    edit = prepare_weapon_skin_unlock_edit(source, selected)
    assert set(edit.newly_unlocked) == set(selected)
    assert len(read_weapon_skins(edit.candidate).unlocked) == 4
    assert prepare_weapon_skin_unlock_edit(source, selected).candidate == edit.candidate
    repeat = prepare_weapon_skin_unlock_edit(edit.candidate, selected)
    assert repeat.changed is False
    assert repeat.candidate == edit.candidate
    all_ids = list(SKIN_CATALOG["ordered_skins"])
    all_edit = prepare_weapon_skin_unlock_edit(source, all_ids)
    assert len(read_weapon_skins(all_edit.candidate).unlocked) == 192
    assert prepare_weapon_skin_unlock_edit(all_edit.candidate, all_ids).changed is False


def test_weapon_skin_rejects_unknown_and_duplicate_ids():
    with pytest.raises(UnknownWeaponSkin):
        prepare_weapon_skin_unlock_edit(payload(), ["weapon_999_s_1"])
    with pytest.raises(InvalidWeaponSkinSelection):
        prepare_weapon_skin_unlock_edit(payload(), ["weapon_002_s_1", "weapon_002_s_1"])


def test_read_kill_effects_keeps_unknown_ids_and_active_scenes():
    snapshot = read_kill_effects(payload())
    assert snapshot.unlocked == (0, 1)
    assert snapshot.unknown_unlocked_ids == (9,)
    assert snapshot.equipped == (
        {"scene": 1, "effect_id": 1},
        {"scene": 0, "effect_id": 3},
    )
    assert next(item for item in snapshot.items if item["id"] == 0)["is_default"] is True
    assert snapshot.summary()["evidence"] == "E3"


def test_unlock_kill_effects_preserves_unknown_and_equipped_scenes():
    source = payload()
    edit = prepare_kill_effect_unlock_edit(source, [2, 3, 8])
    assert edit.newly_unlocked == (2, 3, 8)
    result = json.loads(edit.candidate)
    assert result["miscData"]["unlockedKillEffectIds"] == [0, 1, 9, 2, 3, 8]
    assert result["miscData"]["equippedKillEffectIdByScene"] == [
        {"Key": 1, "Value": 1},
        {"Key": 0, "Value": 3},
    ]
    assert result["miscData"]["currentReturnCount"] == 0
    require_kill_effect_write_compatibility(source, [2, 3, 8], edit.candidate)
    assert prepare_kill_effect_unlock_edit(edit.candidate, [2, 3, 8]).changed is False


def test_kill_effect_rejects_unevidenced_and_duplicate_ids():
    with pytest.raises(UnknownKillEffect):
        prepare_kill_effect_unlock_edit(payload(), [9])
    with pytest.raises(UnknownKillEffect):
        prepare_kill_effect_unlock_edit(payload(), [10])
    with pytest.raises(InvalidKillEffectSelection):
        prepare_kill_effect_unlock_edit(payload(), [2, 2])


def test_unified_plan_composes_both_new_categories_and_backup_roundtrips(tmp_path):
    source = payload()
    plan = {
        "gems": 2000,
        "weapon_skins": ["weapon_002_s_1", "weapon_003_s_1"],
        "kill_effects": [2, 3],
    }
    edit = prepare_unified_edit(source, plan)
    assert edit.steps == ("gems", "weapon_skins", "kill_effects")
    assert [category.key for category in edit.categories] == [
        "gems",
        "weapon_skins",
        "kill_effects",
    ]
    assert edit.plan["weapon_skins"] == ["weapon_002_s_1", "weapon_003_s_1"]
    assert edit.plan["kill_effects"] == [2, 3]
    assert prepare_unified_edit(source, plan).candidate == edit.candidate
    result = json.loads(edit.candidate)
    assert result["gameData"]["gems"] == 2000
    assert result["miscData"]["unlockedKillEffectIds"] == [0, 1, 9, 2, 3]

    store = LabBackupStore(tmp_path / "backups")
    bundle = store.save(
        edit,
        remote_source="fake-remote",
        remote_size=len(source),
        remote_sha256=sha256(source).hexdigest(),
        field="unified",
        original_value=0,
        new_value=edit.change_count,
        unified_plan=edit.plan,
    )
    loaded = store.load(bundle.record.id)
    assert loaded.candidate == edit.candidate
    assert loaded.record.unified_plan["weapon_skins"] == ["weapon_002_s_1", "weapon_003_s_1"]
    assert loaded.record.unified_plan["kill_effects"] == [2, 3]


def test_weapon_skin_catalog_is_visible_with_empty_inventory():
    data = json.loads(FIXTURE.read_bytes())
    data["weaponEvolutionData"] = {
        "blindBoxOpenCount0": 3,
        "lastOpenMachineHistoryStr0": None,
        "weapons": {},
    }
    source = canonical(data)
    snapshot = read_weapon_skins(source)
    assert snapshot.total == 192
    assert len(snapshot.items) == 192
    assert snapshot.unlocked == ()
    assert snapshot.weapons_with_data == 0
    assert all(item["unlocked"] is False for item in snapshot.items)

    edit = prepare_weapon_skin_unlock_edit(source, ["weapon_002_s_1"])
    result = json.loads(edit.candidate)
    assert result["weaponEvolutionData"]["blindBoxOpenCount0"] == 3
    assert result["weaponEvolutionData"]["lastOpenMachineHistoryStr0"] is None
    assert result["weaponEvolutionData"]["weapons"]["weapon_002"] == {
        "Name": "weapon_002",
        "Level": 0,
        "CurrentSkinIndex": 0,
        "UnlockedSkins": ["weapon_002_s_1"],
    }


def test_weapon_skin_catalog_survives_a_missing_weapons_map():
    data = json.loads(FIXTURE.read_bytes())
    data["weaponEvolutionData"] = {"blindBoxOpenCount0": 7, "favorWeapons": ["weapon_311"]}
    source = canonical(data)
    snapshot = read_weapon_skins(source)
    assert snapshot.total == 192 and snapshot.unlocked == ()
    assert snapshot.weapons_with_data == 0

    edit = prepare_weapon_skin_unlock_edit(source, ["weapon_311_s_1"])
    result = json.loads(edit.candidate)
    assert result["weaponEvolutionData"]["blindBoxOpenCount0"] == 7
    assert result["weaponEvolutionData"]["favorWeapons"] == ["weapon_311"]
    assert result["weaponEvolutionData"]["weapons"]["weapon_311"]["UnlockedSkins"] == [
        "weapon_311_s_1"
    ]
    require_weapon_skin_write_compatibility(source, ["weapon_311_s_1"], edit.candidate)


def test_weapon_skin_existing_record_without_unlocked_list_preserves_metadata():
    data = json.loads(FIXTURE.read_bytes())
    data["weaponEvolutionData"] = {
        "weapons": {
            "weapon_311": {
                "Name": "weapon_311",
                "Level": 5,
                "CurrentSkinIndex": 0,
                "Unknown": {"keep": [1, 2]},
            }
        }
    }
    source = canonical(data)
    snapshot = read_weapon_skins(source)
    assert snapshot.total == 192 and snapshot.unlocked == ()
    assert snapshot.weapons_with_data == 1

    edit = prepare_weapon_skin_unlock_edit(source, ["weapon_311_s_1"])
    record = json.loads(edit.candidate)["weaponEvolutionData"]["weapons"]["weapon_311"]
    assert record["Name"] == "weapon_311"
    assert record["Level"] == 5
    assert record["CurrentSkinIndex"] == 0
    assert record["Unknown"] == {"keep": [1, 2]}
    assert record["UnlockedSkins"] == ["weapon_311_s_1"]


def test_kill_effect_catalog_is_visible_without_misc_data():
    source = canonical(advanced_account_document())
    snapshot = read_kill_effects(source)
    assert snapshot.total == 9
    assert len(snapshot.items) == 9
    assert snapshot.unlocked == ()
    assert snapshot.equipped == ()
    assert all(item["unlocked"] is False for item in snapshot.items)

    edit = prepare_kill_effect_unlock_edit(source, [2, 3])
    result = json.loads(edit.candidate)
    assert result["miscData"] == {"unlockedKillEffectIds": [2, 3]}
    assert result["weaponEvolutionData"]["weapons"]["weapon_311"]["UnlockedSkins"] == [
        "weapon_311_s_1"
    ]
    require_kill_effect_write_compatibility(source, [2, 3], edit.candidate)
    assert prepare_kill_effect_unlock_edit(edit.candidate, [2, 3]).changed is False


def test_kill_effect_missing_list_preserves_equipped_scenes_and_misc_fields():
    data = json.loads(FIXTURE.read_bytes())
    data["miscData"] = {
        "currentReturnCount": 4,
        "equippedKillEffectIdByScene": [{"Key": 1, "Value": 1}],
    }
    source = canonical(data)
    snapshot = read_kill_effects(source)
    assert snapshot.total == 9 and snapshot.unlocked == ()
    assert snapshot.equipped == ({"scene": 1, "effect_id": 1},)

    edit = prepare_kill_effect_unlock_edit(source, [4])
    misc = json.loads(edit.candidate)["miscData"]
    assert misc == {
        "currentReturnCount": 4,
        "equippedKillEffectIdByScene": [{"Key": 1, "Value": 1}],
        "unlockedKillEffectIds": [4],
    }


def test_unified_plan_works_on_real_advanced_and_new_account_shapes():
    advanced = canonical(advanced_account_document())
    plan = {"weapon_skins": ["weapon_002_s_1"], "kill_effects": [2]}
    advanced_edit = prepare_unified_edit(advanced, plan)
    assert advanced_edit.steps == ("weapon_skins", "kill_effects")
    advanced_result = json.loads(advanced_edit.candidate)
    assert advanced_result["miscData"] == {"unlockedKillEffectIds": [2]}
    assert "weapon_002" in advanced_result["weaponEvolutionData"]["weapons"]

    new_account = canonical(new_account_document())
    new_snapshot = read_weapon_skins(new_account)
    assert len(new_snapshot.unlocked) == 2
    assert read_kill_effects(new_account).unlocked == (0, 1)
    new_edit = prepare_unified_edit(new_account, plan)
    new_result = json.loads(new_edit.candidate)
    assert new_result["miscData"]["unlockedKillEffectIds"] == [0, 1, 2]
    assert new_result["weaponEvolutionData"]["weapons"]["weapon_407"]["CurrentSkinIndex"] == 1
    assert len(read_weapon_skins(new_edit.candidate).unlocked) == 3


def progression_document() -> dict:
    data = document()
    data["statisticData"]["object2ObtainTime"] = {
        "weapon_311": 5,
        "weapon_002": 0,
        "weapon_003": 2,
        "ring_1": 0,
        "enemy_001": 9,
        "custom_counter": 4,
        "weapon_unknown_999": 7,
    }
    data["itemData"]["forgeWeapons"] = ["weapon_003", "weapon_003", None]
    return data


def test_weapon_catalog_is_available():
    assert WEAPON_CATALOG["available"] is True
    assert WEAPON_CATALOG["counts"] == {"weapons": 995, "forgeable": 494}
    assert len(WEAPON_CATALOG["ordered_weapons"]) == 995
    assert len(WEAPON_CATALOG["forgeable_ids"]) == 494


def test_weapon_progression_reads_discovery_and_forge_state_without_writing():
    source = canonical(progression_document())
    snapshot = read_weapon_progression(source)
    assert snapshot.total == 995
    assert len(snapshot.items) == 995
    assert set(snapshot.discovered) == {"weapon_311", "weapon_003"}
    assert snapshot.forge_queue == ("weapon_003",)
    assert snapshot.unknown_weapon_ids == ("weapon_unknown_999",)
    assert snapshot.unknown_counter_count == 3
    by_id = {item["id"]: item for item in snapshot.items}
    assert by_id["weapon_311"]["discovered"] is True
    assert by_id["weapon_311"]["forge_ready"] is True
    assert by_id["weapon_002"]["count"] == 0
    assert by_id["weapon_002"]["forge_status"] == "requires_discovery"
    assert by_id["weapon_002"]["proposed_count"] == 1
    assert by_id["weapon_003"]["in_forge_queue"] is True
    assert by_id["transform_weapon_beheaded"]["forge_status"] == "not_forgeable"
    assert snapshot.summary()["evidence"] == "E2"


def test_weapon_progression_raises_only_missing_or_zero_counters_to_one():
    source = canonical(progression_document())
    edit = prepare_weapon_progression_edit(source, ["weapon_002", "weapon_004", "weapon_311"])
    result = json.loads(edit.candidate)
    counters = result["statisticData"]["object2ObtainTime"]
    assert counters["weapon_002"] == 1
    assert counters["weapon_004"] == 1
    assert counters["weapon_311"] == 5
    assert counters["weapon_003"] == 2
    assert counters["ring_1"] == 0
    assert counters["enemy_001"] == 9
    assert counters["custom_counter"] == 4
    assert result["itemData"]["forgeWeapons"] == ["weapon_003", "weapon_003", None]
    assert edit.newly_discovered == ("weapon_002", "weapon_004")
    assert edit.new_forge_ready == ("weapon_002", "weapon_004")
    assert edit.changed_fields == (
        "statisticData.object2ObtainTime.weapon_002",
        "statisticData.object2ObtainTime.weapon_004",
    )
    require_weapon_progression_write_compatibility(
        source, ["weapon_002", "weapon_004", "weapon_311"], edit.candidate
    )
    assert prepare_weapon_progression_edit(edit.candidate, ["weapon_002", "weapon_004"]).changed is False


def test_weapon_progression_creates_only_the_obtain_map_when_missing():
    data = document()
    data["statisticData"].pop("object2ObtainTime", None)
    source = canonical(data)
    snapshot = read_weapon_progression(source)
    assert snapshot.discovered == ()
    assert snapshot.forge_queue == ()

    edit = prepare_weapon_progression_edit(source, ["weapon_002"])
    result = json.loads(edit.candidate)
    assert result["statisticData"]["object2ObtainTime"] == {"weapon_002": 1}
    assert result["statisticData"]["StatisticsData"] == data["statisticData"]["StatisticsData"]
    require_weapon_progression_write_compatibility(source, ["weapon_002"], edit.candidate)


def test_weapon_progression_rejects_unknown_ids_and_invalid_counters():
    source = canonical(progression_document())
    with pytest.raises(UnknownWeapon):
        prepare_weapon_progression_edit(source, ["weapon_missing_999"])
    with pytest.raises(InvalidWeaponSelection):
        prepare_weapon_progression_edit(source, [])

    data = progression_document()
    data["statisticData"]["object2ObtainTime"]["weapon_002"] = -1
    with pytest.raises(Exception) as error:
        read_weapon_progression(canonical(data))
    assert "no es un contador" in str(error.value)


def test_unified_plan_preserves_weapon_skins_and_kill_effects_with_progression():
    source = canonical(progression_document())
    plan = {
        "weapon_progression": ["weapon_002"],
        "weapon_skins": ["weapon_002_s_1"],
        "kill_effects": [2],
    }
    edit = prepare_unified_edit(source, plan)
    assert edit.steps == ("weapon_progression", "weapon_skins", "kill_effects")
    result = json.loads(edit.candidate)
    assert result["statisticData"]["object2ObtainTime"]["weapon_002"] == 1
    assert result["weaponEvolutionData"]["weapons"]["weapon_002"]["UnlockedSkins"] == [
        "weapon_002_s_1"
    ]
    assert result["miscData"]["unlockedKillEffectIds"] == [0, 1, 9, 2]

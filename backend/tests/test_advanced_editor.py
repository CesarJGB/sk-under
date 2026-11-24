import json
import subprocess
import sys
from hashlib import sha256
from pathlib import Path

import pytest

from app.cloud.advanced_editor import (
    AdvancedFieldIncompatible,
    AdvancedFieldMissing,
    AdvancedSeasonMissing,
    InvalidAdvancedPlan,
    read_advanced_source,
    prepare_advanced_edit,
)
from app.cloud.backup_store import LabBackupStore
from app.cloud.fish_progress_editor import prepare_fish_progress_edit
from app.cloud.gems_editor import serialize_aggregate
from app.cloud.lab_service import CloudLabService
from app.cloud.provider import AcquiredCloudSave, CloudSaveMetadata

FIXTURE = Path(__file__).parent / "fixtures" / "cloud-save-gems.json"
ROOT = Path(__file__).resolve().parents[2]


def canonical(document: dict) -> bytes:
    return serialize_aggregate(document)


def battle_pass(season_id: int, level: int, *, paid: int = 0, has_buy: bool = False) -> dict:
    return {
        "Key": season_id,
        "Value": {
            "seasonID": season_id,
            "curLevel": level,
            "curExp": 4,
            "hasBuy": has_buy,
            "freeClaimedLevel": level,
            "paidClaimedLevel": paid,
        },
    }


def document() -> dict:
    data = json.loads(FIXTURE.read_bytes())
    data["gameData"]["rebornCard"] = False
    data["gameData"]["fishChip"] = 3
    data["gameData"]["petUnlock"] = {"Cat": True, "Cat1": False, "Dog": True}
    data["itemData"]["materials"] = {
        "material_ticket": 5,
        "material_fish": 3,
        "custom_unknown_material": 77,
    }
    data["itemData"]["cumulativeFishCount"] = 18
    data["itemData"]["seeds"] = {
        "plant_banboo_seed": 2,
        "custom_unknown_seed": 1,
    }
    data["seasonData"] = {"coin": 100, "seasonID": 8, "customSeasonField": "keep"}
    data["battlePassSaveData"]["seasonData"] = [
        battle_pass(6, 10, paid=9, has_buy=True),
        battle_pass(7, 50, paid=50, has_buy=True),
        battle_pass(8, 2, paid=0),
    ]
    return data


def payload() -> bytes:
    return canonical(document())


def test_batch_edit_changes_only_requested_fields_and_combines_edits():
    original = payload()
    before = document()
    plan = {
        "materials": [
            {"id": "material_ticket", "value": 12},
            {"id": "material_hopper_ticket", "value": 1},
        ],
        "seeds": [{"id": "plant_banboo_seed", "value": 8}],
        "season_coin": 250_000,
        "reborn_card": True,
        "battle_pass": {"season_id": 7, "cur_level": 55, "cur_exp": 9, "has_buy": True},
    }
    edit = prepare_advanced_edit(original, plan)
    assert edit.changed is True
    assert edit.changed_fields == (
        "itemData.materials.material_hopper_ticket",
        "itemData.materials.material_ticket",
        "itemData.seeds.plant_banboo_seed",
        "seasonData.coin",
        "gameData.rebornCard",
        "battlePassSaveData.seasonData.1.Value.curLevel",
        "battlePassSaveData.seasonData.1.Value.curExp",
    )
    after = json.loads(edit.candidate)
    # Solo se tocan las rutas autorizadas.
    assert after["itemData"]["materials"]["material_ticket"] == 12
    assert after["itemData"]["materials"]["material_hopper_ticket"] == 1
    assert after["itemData"]["materials"]["material_fish"] == 3
    assert after["itemData"]["materials"]["custom_unknown_material"] == 77
    assert after["itemData"]["seeds"]["plant_banboo_seed"] == 8
    assert after["itemData"]["seeds"]["custom_unknown_seed"] == 1
    assert after["seasonData"] == {
        "coin": 250_000,
        "seasonID": 8,
        "customSeasonField": "keep",
    }
    assert after["gameData"]["rebornCard"] is True
    assert after["gameData"]["fishChip"] == 3
    assert after["itemData"]["materials"]["material_fish"] == before["itemData"]["materials"]["material_fish"]
    # El pase 7 conserva sus recompensas y el pase 6 permanece intacto.
    seasons = {record["Value"]["seasonID"]: record["Value"] for record in after["battlePassSaveData"]["seasonData"]}
    assert seasons[7]["curLevel"] == 55
    assert seasons[7]["curExp"] == 9
    assert seasons[7]["freeClaimedLevel"] == 50
    assert seasons[7]["paidClaimedLevel"] == 50
    assert seasons[6] == before["battlePassSaveData"]["seasonData"][0]["Value"]
    assert seasons[8] == before["battlePassSaveData"]["seasonData"][2]["Value"]
    # Los campos no autorizados de los demás grupos no se alteran.
    for key in before:
        if key not in {"itemData", "seasonData", "gameData", "battlePassSaveData"}:
            assert after[key] == before[key]


def test_noop_plan_preserves_bytes():
    original = payload()
    edit = prepare_advanced_edit(
        original,
        {
            "materials": [{"id": "material_ticket", "value": 5}],
            "season_coin": 100,
            "battle_pass": {"season_id": 7, "cur_level": 50},
        },
    )
    assert edit.changed is False
    assert edit.candidate == original


def test_missing_season_coin_is_not_created():
    data = document()
    del data["seasonData"]["coin"]
    with pytest.raises(AdvancedFieldMissing):
        prepare_advanced_edit(canonical(data), {"season_coin": 10})


@pytest.mark.parametrize(
    "plan",
    [
        {"season_coin": -1},
        {"season_coin": 2_147_483_648},
        {"season_coin": True},
        {"season_coin": 1.5},
        {"reborn_card": False},
        {"materials": [{"id": "material_fish", "value": 1}]},
        {"materials": [{"id": "not_in_catalog", "value": 1}]},
        {"seeds": [{"id": "plant_banboo_seed", "value": -2}]},
        {"materials": [{"id": "material_ticket", "value": 1}, {"id": "material_ticket", "value": 2}]},
        {"battle_pass": {"season_id": 999, "cur_level": 1}},
        {"battle_pass": {"season_id": 7, "cur_level": 49}},
        {"battle_pass": {"season_id": 7, "has_buy": False}},
        {},
    ],
)
def test_rejects_invalid_or_unsafe_plans(plan):
    with pytest.raises((InvalidAdvancedPlan, AdvancedSeasonMissing)):
        prepare_advanced_edit(payload(), plan)


def test_rejects_non_integer_existing_material_without_overwriting_it():
    data = document()
    data["itemData"]["materials"]["material_ticket"] = "5"
    with pytest.raises(AdvancedFieldIncompatible):
        prepare_advanced_edit(
            canonical(data), {"materials": [{"id": "material_ticket", "value": 10}]}
        )


def test_reborn_card_requires_existing_boolean():
    data = document()
    del data["gameData"]["rebornCard"]
    with pytest.raises(AdvancedFieldMissing):
        prepare_advanced_edit(canonical(data), {"reborn_card": True})


def test_snapshot_selects_latest_battle_pass_and_preserves_unknown_ids():
    snapshot = read_advanced_source(payload())
    assert snapshot["season_coin"]["value"] == 100
    assert snapshot["reborn_card"]["available"] is True
    assert snapshot["reborn_card"]["value"] is False
    assert snapshot["battle_pass"]["selected_season_id"] == 8
    assert snapshot["battle_pass"]["active_season_id"] == 8
    assert snapshot["battle_pass"]["active_matches_selected"] is True
    materials = {row["id"]: row for row in snapshot["materials"]}
    seeds = {row["id"]: row for row in snapshot["seeds"]}
    assert materials["material_ticket"]["count"] == 5
    assert materials["material_fish"]["editable"] is False
    assert materials["custom_unknown_material"]["known"] is False
    assert materials["custom_unknown_material"]["count"] == 77
    assert seeds["custom_unknown_seed"]["known"] is False
    # Un material del catálogo ausente se ofrece como inserción compatible.
    assert materials["material_hopper_ticket"]["owned"] is False
    assert materials["material_hopper_ticket"]["insertable"] is True


def test_cumulative_threshold_reuses_phase_620_editor_and_preserves_higher_values():
    edit = prepare_fish_progress_edit(payload(), max(18, 21))
    after = json.loads(edit.candidate)
    assert after["itemData"]["cumulativeFishCount"] == 21
    # El umbral no toca el saldo ni el material espejo.
    assert after["gameData"]["fishChip"] == 3
    assert after["itemData"]["materials"]["material_fish"] == 3
    # Si el guardado ya supera el umbral, el control rápido no lo reduce.
    higher = document()
    higher["itemData"]["cumulativeFishCount"] = 30
    untouched = prepare_fish_progress_edit(canonical(higher), max(30, 21))
    assert untouched.changed is False


class FixedProvider:
    def __init__(self, value: bytes):
        self.payload = value

    def download(self, limit=8 * 1024 * 1024):
        return AcquiredCloudSave(
            CloudSaveMetadata(
                "fake-remote",
                len(self.payload),
                sha256(self.payload).hexdigest(),
                source="modern-cloud",
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


def test_service_prepare_confirm_and_restore_advanced_batch(tmp_path):
    provider = FixedProvider(payload())
    lab = CloudLabService(
        provider,
        LabBackupStore(tmp_path / "backups"),
        uploader=FakeUploader(provider),
        write_enabled=True,
        admin_configured=True,
    )
    plan = {
        "materials": [{"id": "material_ticket", "value": 9}],
        "season_coin": 500,
        "battle_pass": {"season_id": 8, "cur_level": 3},
    }
    prepared = lab.prepare_advanced(plan)
    assert prepared.backup.field == "advanced"
    assert prepared.backup.advanced_plan == {
        "materials": {"material_ticket": 9},
        "seeds": {},
        "season_coin": 500,
        "reborn_card": None,
        "battle_pass": {"season_id": 8, "cur_level": 3},
        "pets": [],
        "pet_food": {},
    }
    summary = prepared.summary()
    assert summary["field"] == "advanced"
    assert summary["experimental"] is True
    assert summary["validation"]["valid"] is True

    result = lab.confirm(prepared.backup.id, prepared.candidate_sha256)
    assert result.persisted is True
    assert result.field == (
        "itemData.materials, itemData.seeds, seasonData.coin, gameData.rebornCard, "
        "battlePassSaveData.seasonData, gameData.petUnlock, statisticData.event2Count"
    )
    loaded = lab.load()
    assert loaded.advanced["season_coin"]["value"] == 500
    assert loaded.gems == 1000

    restored = lab.restore(prepared.backup.id)
    assert restored.persisted is True
    assert lab.load().advanced["season_coin"]["value"] == 100


def test_backend_item_projection_matches_knowledge_catalogs():
    result = subprocess.run(
        [sys.executable, str(ROOT / "knowledge" / "tools" / "build_backend_items.py"), "--check"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr

def test_backend_pet_projection_matches_knowledge_catalogs():
    result = subprocess.run(
        [sys.executable, str(ROOT / "knowledge" / "tools" / "build_backend_pets.py"), "--check"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_pet_unlock_preserves_existing_and_inserts_missing_variant_dependency():
    original = payload()
    before = document()
    plan = {"pets": ["Cat1", "Rabbit1"], "pet_food": [{"id": "material_grain", "value": 500}]}
    edit = prepare_advanced_edit(original, plan)
    assert edit.changed is True
    assert edit.plan["pets"] == ["Cat", "Cat1", "Rabbit", "Rabbit1"]
    assert edit.plan["pet_food"] == {"material_grain": 500}
    assert edit.changed_fields == (
        "itemData.materials.material_grain",
        "gameData.petUnlock.Cat1",
        "gameData.petUnlock.Rabbit",
        "gameData.petUnlock.Rabbit1",
    )
    after = json.loads(edit.candidate)
    assert after["gameData"]["petUnlock"]["Cat"] is True
    assert after["gameData"]["petUnlock"]["Dog"] is True
    assert after["gameData"]["petUnlock"]["Cat1"] is True
    assert after["gameData"]["petUnlock"]["Rabbit"] is True
    assert after["gameData"]["petUnlock"]["Rabbit1"] is True
    assert after["itemData"]["materials"]["material_grain"] == 500
    assert after["itemData"]["materials"]["custom_unknown_material"] == 77
    assert before["gameData"]["petUnlock"]["Cat1"] is False

    # La reversión interna ya exige ausencia de cambios colaterales; comprobamos
    # además que el original no se mutó y que el candidato reabre estable.
    assert original == payload()
    reopened = json.loads(edit.candidate)
    assert serialize_aggregate(reopened) == edit.candidate


def test_pet_already_unlocked_and_invalid_ids_are_controlled():
    original = payload()
    edit = prepare_advanced_edit(original, {"pets": ["Cat"]})
    assert edit.changed is False
    with pytest.raises(InvalidAdvancedPlan):
        prepare_advanced_edit(original, {"pets": ["NotAPet"]})
    with pytest.raises(InvalidAdvancedPlan):
        prepare_advanced_edit(original, {"pets": ["Cat", "Cat"]})
    with pytest.raises(InvalidAdvancedPlan):
        prepare_advanced_edit(original, {"pets": ["Cat"], "pet_food": [{"id": "material_ticket", "value": 1}]})


def test_pet_food_shares_the_materials_writer_and_rejects_conflicts():
    original = payload()
    plan = {
        "materials": [{"id": "material_grain", "value": 100}],
        "pet_food": [{"id": "material_grain", "value": 100}],
    }
    edit = prepare_advanced_edit(original, plan)
    assert edit.changed_fields == ("itemData.materials.material_grain",)
    assert edit.plan["materials"] == {"material_grain": 100}
    assert edit.plan["pet_food"] == {"material_grain": 100}

    with pytest.raises(InvalidAdvancedPlan):
        prepare_advanced_edit(original, {
            "materials": [{"id": "material_battery", "value": 10}],
            "pet_food": [{"id": "material_battery", "value": 20}],
        })


def test_pet_food_rejects_out_of_range_values():
    original = payload()
    for value in (-1, 2_147_483_648):
        with pytest.raises(InvalidAdvancedPlan):
            prepare_advanced_edit(original, {"pet_food": [{"id": "material_grain", "value": value}]})


def test_pet_progression_is_read_only_and_uses_observed_event2count_keys():
    data = document()
    data["statisticData"]["event2Count"] = {
        "pet_0_intimacy": 240,
        "pet_0_full_intimacy": 1,
        "pet_0_action_unlock": 1,
        "pet_2_intimacy": 180,
        "pet_2_full_intimacy": 0,
        "pet_full_intimacy": 1,
        "unrelated_counter": 9,
    }
    snapshot = read_advanced_source(canonical(data))
    progression = snapshot["pet_progression"]
    assert progression["available"] is True
    assert progression["global_full_count"] == 1
    entries = {entry["id"]: entry for entry in progression["entries"]}
    assert entries["Cat"]["intimacy"] == 240
    assert entries["Cat"]["full"] is True
    assert entries["Pig"]["intimacy"] == 180
    assert entries["Pig"]["full"] is False
    assert entries["Cat"]["max"] is None
    assert snapshot["pets"] and snapshot["pet_skins"] and snapshot["pet_food"]
    assert {row["id"] for row in snapshot["pet_food"]} == {"material_grain", "material_battery"}
    assert len(snapshot["pets"]) == 58
    assert len(snapshot["pet_skins"]) == 12
    # El snapshot no expone ninguna operación de escritura de intimidad.
    assert snapshot["pet_policy"]["field"] == "pets"


def test_pet_and_confirmed_batch_combination_is_atomic_and_reversible():
    original = payload()
    plan = {
        "materials": [{"id": "material_ticket", "value": 20}],
        "seeds": [{"id": "plant_banboo_seed", "value": 4}],
        "season_coin": 1234,
        "reborn_card": True,
        "pets": ["Pug"],
        "pet_food": [{"id": "material_battery", "value": 250}],
    }
    edit = prepare_advanced_edit(original, plan)
    assert edit.changed_fields == (
        "itemData.materials.material_battery",
        "itemData.materials.material_ticket",
        "itemData.seeds.plant_banboo_seed",
        "seasonData.coin",
        "gameData.rebornCard",
        "gameData.petUnlock.Pug",
    )
    after = json.loads(edit.candidate)
    assert after["itemData"]["materials"]["material_battery"] == 250
    assert after["itemData"]["materials"]["material_ticket"] == 20
    assert after["itemData"]["materials"]["material_fish"] == 3
    assert after["gameData"]["petUnlock"]["Pug"] is True
    assert after["gameData"]["petUnlock"]["Cat"] is True
    assert after["gameData"]["rebornCard"] is True

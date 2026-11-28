import json
from pathlib import Path

import pytest

from app.cloud.blueprint_editor import (
    BlueprintFieldIncompatible,
    prepare_blueprint_edit,
    read_blueprints,
)
from app.cloud.decoration_editor import (
    InvalidDecorationPlan,
    prepare_decoration_edit,
    read_decorations,
)
from app.cloud.pet_affinity_editor import (
    InvalidPetAffinityPlan,
    prepare_pet_affinity_edit,
    read_pet_affinity,
)
from app.cloud.unified_editor import prepare_unified_edit

FIXTURE = Path(__file__).parent / "fixtures" / "cloud-save-gems.json"


def canonical(document: dict) -> bytes:
    return json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(", ", ": ")).encode()


def document() -> dict:
    data = json.loads(FIXTURE.read_bytes())
    data["gameData"]["heroUnlock"] = {"Knight": True, "Ranger": False}
    data["gameData"]["petUnlock"] = {"Cat": True, "Pig": True, "Dog": False, "Serenade": False}
    data["gameData"]["roomObjectLevel"] = {"Book": 2, "CatFood": 0, "Chest": 1, "Planet": 5, "Safe": 4}
    data["gameData"]["currentRoomDecorate"] = "Common"
    data["gameData"]["unlockRoomDecorate"] = []
    data["gameData"]["roomLevel"] = 1
    data["itemData"]["roomDecorateDic"] = {"ItemEggMachine": [0]}
    data["statisticData"]["event2Count"] = {"unrelated_counter": 9, "pet_2_intimacy": 200}
    data["itemData"]["blueprints"] = {
        "blueprint_multi_room_skin_0": "Researched",
        "multi_room_skin_1": "Got",
        "legacy_unknown": "Researched",
    }
    return data


def source(data: dict | None = None) -> bytes:
    return canonical(document() if data is None else data)


def integer_document() -> dict:
    data = document()
    data["itemData"]["blueprints"] = {
        "multi_room_skin_1": 1,
        "garden_skin_1": 1,
        "multi_room_skin_2": 2,
        "legacy_unknown": 1,
    }
    return data


def test_pet_affinity_creates_initial_record_for_unlocked_pet_and_restores_bytes():
    original = source()
    snapshot = read_pet_affinity(original)
    rows = {row["id"]: row for row in snapshot["entries"]}
    assert rows["Cat"]["intimacy"] == 0
    assert rows["Cat"]["present"] is False
    assert rows["Cat"]["creatable"] is True
    assert rows["Cat"]["editable"] is True
    assert rows["Serenade"]["editable"] is False
    assert rows["Dog"]["editable"] is False
    assert "desbloqueada" in rows["Dog"]["reason"].lower()

    edit = prepare_pet_affinity_edit(original, {"Cat": 120})
    counters = json.loads(edit.candidate)["statisticData"]["event2Count"]
    assert counters["pet_0_intimacy"] == 120
    assert "pet_0_full_intimacy" not in counters
    assert counters["pet_2_intimacy"] == 200
    assert counters["unrelated_counter"] == 9
    assert edit.changed_fields == ("statisticData.event2Count.pet_0_intimacy",)
    assert edit.original == original

    with pytest.raises(Exception):
        prepare_pet_affinity_edit(original, {"Serenade": 10})
    with pytest.raises(InvalidPetAffinityPlan):
        prepare_pet_affinity_edit(source(), {"Cat": 241})


def test_pet_affinity_max_creates_full_marker_and_does_not_touch_global_counter():
    original = source()
    edit = prepare_pet_affinity_edit(original, {"Cat": 240, "Pig": 240})
    counters = json.loads(edit.candidate)["statisticData"]["event2Count"]
    assert counters["pet_0_intimacy"] == 240
    assert counters["pet_0_full_intimacy"] == 1
    assert counters["pet_2_intimacy"] == 240
    assert counters["pet_2_full_intimacy"] == 1
    assert "pet_full_intimacy" not in counters


def test_blueprints_create_with_account_text_encoding_and_reject_downgrade():
    original = source()
    edit = prepare_blueprint_edit(original, {
        "blueprint_multi_room_skin_2": "Researched",
        "blueprint_multi_room_skin_1": "Researched",
    })
    after = json.loads(edit.candidate)["itemData"]["blueprints"]
    assert after["multi_room_skin_2"] == "Researched"
    assert after["multi_room_skin_1"] == "Researched"
    assert after["legacy_unknown"] == "Researched"
    assert {change.path for change in edit.changes} == {
        "itemData.blueprints.multi_room_skin_2",
        "itemData.blueprints.multi_room_skin_1",
    }
    with pytest.raises(BlueprintFieldIncompatible):
        prepare_blueprint_edit(original, {"blueprint_multi_room_skin_0": "Got"})


def test_blueprints_detect_integer_encoding_create_and_upgrade_without_mixing_types():
    original = source(integer_document())
    snapshot = read_blueprints(original)
    assert snapshot["encoding"] == "integer"
    rows = {row["id"]: row for row in snapshot["entries"]}
    assert rows["blueprint_garden_skin_1"]["status"] == "Got"
    assert rows["blueprint_multi_room_skin_2"]["status"] == "Researched"

    edit = prepare_blueprint_edit(original, {
        "blueprint_garden_skin_1": "Researched",
        "blueprint_multi_room_skin_7": "Got",
    })
    after = json.loads(edit.candidate)["itemData"]["blueprints"]
    assert after["garden_skin_1"] == 2
    assert after["multi_room_skin_7"] == 1
    assert after["legacy_unknown"] == 1
    assert all(isinstance(value, int) for value in after.values())
    assert "blueprint_multi_room_skin_7" not in after


def test_decorations_unlock_objects_raise_observed_levels_and_preserve_unknowns():
    original = source()
    snapshot = read_decorations(original)
    objects = {row["id"]: row for row in snapshot["objects"]}
    levels = {row["id"]: row for row in snapshot["levels"]}
    assert objects["ItemEggMachine"]["unlocked"] is True
    assert objects["ObjectSafe"]["editable"] is True
    assert levels["Book"]["level"] == 2 and levels["Book"]["max_observed"] == 5
    assert levels["Planet"]["editable"] is False
    assert levels["Chest"]["editable"] is True
    assert levels["Chest"]["max_observed"] == 5
    assert snapshot["room"]["selection_editable"] is False

    edit = prepare_decoration_edit(original, {
        "objects": ["ObjectSafe", "PetFood", "ItemEggMachine"],
        "levels": [{"id": "Book", "level": 5}, {"id": "Safe", "level": 4}],
    })
    after = json.loads(edit.candidate)
    assert after["itemData"]["roomDecorateDic"]["ObjectSafe"] == [0]
    assert after["itemData"]["roomDecorateDic"]["PetFood"] == [0]
    assert after["itemData"]["roomDecorateDic"]["ItemEggMachine"] == [0]
    assert after["gameData"]["roomObjectLevel"]["Book"] == 5
    assert after["gameData"]["roomObjectLevel"]["Safe"] == 4
    assert after["gameData"]["currentRoomDecorate"] == "Common"
    assert after["statisticData"]["event2Count"]["room_unlock_safe"] == 1
    assert after["statisticData"]["event2Count"]["room_unlock_pet_food"] == 1
    assert after["statisticData"]["event2Count"]["room_unlock_book"] == 1
    assert edit.changed_fields == (
        "itemData.roomDecorateDic.ObjectSafe",
        "statisticData.event2Count.room_unlock_safe",
        "itemData.roomDecorateDic.PetFood",
        "statisticData.event2Count.room_unlock_pet_food",
        "gameData.roomObjectLevel.Book",
        "statisticData.event2Count.room_unlock_book",
    )


def test_decorations_reject_unknown_and_lowering_and_noop_is_identical():
    original = source()
    with pytest.raises(InvalidDecorationPlan):
        prepare_decoration_edit(original, {"objects": ["InventedObject"]})
    with pytest.raises(InvalidDecorationPlan):
        prepare_decoration_edit(original, {"levels": {"Safe": 6}})
    with pytest.raises(Exception):
        prepare_decoration_edit(original, {"levels": {"Safe": 3}})
    noop = prepare_decoration_edit(original, {"objects": ["ItemEggMachine"], "levels": {"Safe": 4}})
    assert noop.changed is False
    assert noop.candidate == original


def test_unified_plan_combines_pets_blueprints_and_decorations_atomically():
    original = source()
    plan = {
        "characters": ["Ranger"],
        "pet_affinity": [{"code": "Cat", "value": 240}],
        "blueprints": [{"id": "blueprint_multi_room_skin_2", "status": "Researched"}],
        "decorations": {"objects": ["ObjectSafe"], "levels": [{"id": "Book", "level": 5}]},
    }
    edit = prepare_unified_edit(original, plan)
    assert edit.steps == ("characters", "pet_affinity", "blueprints", "decorations")
    after = json.loads(edit.candidate)
    assert after["gameData"]["heroUnlock"]["Ranger"] is True
    assert after["statisticData"]["event2Count"]["pet_0_intimacy"] == 240
    assert after["itemData"]["blueprints"]["multi_room_skin_2"] == "Researched"
    assert after["itemData"]["roomDecorateDic"]["ObjectSafe"] == [0]
    assert after["gameData"]["roomObjectLevel"]["Book"] == 5
    assert edit.original == original


def test_decorations_require_functional_flags_and_blueprints_beyond_possession():
    snapshot = read_decorations(source())
    objects = {row["id"]: row for row in snapshot["objects"]}
    assert objects["ItemEggMachine"]["functional"] is True
    safe = objects["ObjectSafe"]
    assert safe["unlocked"] is False and safe["functional"] is False
    assert safe["requirements"] == [{
        "kind": "flag",
        "key": "room_unlock_safe",
        "value": None,
        "met": False,
        "path": "statisticData.event2Count.room_unlock_safe",
    }]
    drink = objects["ObjectDrinkSeller"]
    assert [row["kind"] for row in drink["requirements"]] == ["blueprint"]
    assert drink["requirements"][0]["key"] == "blueprint_room_decorate_drink_seller"
    magic = objects["ObjectMagicWell"]
    assert [row["kind"] for row in magic["requirements"]] == ["flag", "blueprint"]

    data = document()
    data["itemData"]["roomDecorateDic"]["ObjectSafe"] = [0]
    partial = read_decorations(source(data))
    rows = {row["id"]: row for row in partial["objects"]}
    assert rows["ObjectSafe"]["unlocked"] is True
    assert rows["ObjectSafe"]["functional"] is False
    assert rows["ObjectSafe"]["editable"] is True


def test_decorations_unlock_creates_flags_and_blueprints_and_is_idempotent():
    original = source()
    edit = prepare_decoration_edit(original, {
        "objects": ["ObjectSafe", "ObjectDrinkSeller", "ObjectMagicWell"],
    })
    after = json.loads(edit.candidate)
    counters = after["statisticData"]["event2Count"]
    blueprints = after["itemData"]["blueprints"]
    assert after["itemData"]["roomDecorateDic"]["ObjectSafe"] == [0]
    assert counters["room_unlock_safe"] == 1
    assert counters["room_unlock_magic_area"] == 1
    assert blueprints["blueprint_room_decorate_drink_seller"] == "Researched"
    assert blueprints["blueprint_room_decorate_magic_well"] == "Researched"
    assert blueprints["legacy_unknown"] == "Researched"
    assert edit.changed_fields == (
        "itemData.roomDecorateDic.ObjectDrinkSeller",
        "itemData.blueprints.blueprint_room_decorate_drink_seller",
        "itemData.roomDecorateDic.ObjectMagicWell",
        "statisticData.event2Count.room_unlock_magic_area",
        "itemData.blueprints.blueprint_room_decorate_magic_well",
        "itemData.roomDecorateDic.ObjectSafe",
        "statisticData.event2Count.room_unlock_safe",
    )
    assert edit.original == original

    repeated = prepare_decoration_edit(edit.candidate, {
        "objects": ["ObjectSafe", "ObjectDrinkSeller", "ObjectMagicWell"],
    })
    assert repeated.changed is False
    assert repeated.candidate == edit.candidate


def test_decorations_integer_encoding_upgrades_blueprints_and_preserves_type():
    data = integer_document()
    data["itemData"]["roomDecorateDic"] = {"ObjectFishBowl": [0]}
    data["itemData"]["blueprints"]["room_decorate_fishbowl"] = 1
    original = source(data)
    edit = prepare_decoration_edit(original, {"objects": ["ObjectFishBowl"]})
    blueprints = json.loads(edit.candidate)["itemData"]["blueprints"]
    assert blueprints["room_decorate_fishbowl"] == 2
    assert blueprints["multi_room_skin_1"] == 1
    assert all(type(value) is int for value in blueprints.values())


def test_decorations_reject_incompatible_flags_and_missing_containers():
    data = document()
    data["statisticData"]["event2Count"]["room_unlock_safe"] = "yes"
    with pytest.raises(Exception):
        prepare_decoration_edit(source(data), {"objects": ["ObjectSafe"]})

    data = document()
    del data["statisticData"]["event2Count"]
    with pytest.raises(Exception):
        prepare_decoration_edit(source(data), {"objects": ["ObjectSafe"]})


def test_blueprints_create_prefixed_room_decorate_keys_without_alias():
    original = source()
    edit = prepare_blueprint_edit(
        original,
        {"blueprint_room_decorate_drink_seller": "Researched"},
    )
    blueprints = json.loads(edit.candidate)["itemData"]["blueprints"]
    assert blueprints["blueprint_room_decorate_drink_seller"] == "Researched"
    assert "room_decorate_drink_seller" not in blueprints
    repeated = prepare_blueprint_edit(
        edit.candidate,
        {"blueprint_room_decorate_drink_seller": "Researched"},
    )
    assert repeated.changed is False

    data = document()
    data["itemData"]["roomDecorateDic"]["ObjectDrinkSeller"] = [0]
    data["itemData"]["blueprints"]["room_decorate_drink_seller"] = "Unknown"
    with pytest.raises(Exception):
        prepare_decoration_edit(source(data), {"objects": ["ObjectDrinkSeller"]})


def test_decorations_level_gate_and_combined_reversal():
    original = source()
    snapshot = read_decorations(original)
    levels = {row["id"]: row for row in snapshot["levels"]}
    assert levels["Book"]["gate"] == "room_unlock_book"
    assert levels["Book"]["gate_met"] is False
    assert levels["Planet"]["gate"] is None

    edit = prepare_decoration_edit(original, {"levels": [{"id": "Chest", "level": 5}]})
    after = json.loads(edit.candidate)
    assert after["gameData"]["roomObjectLevel"]["Chest"] == 5
    assert after["statisticData"]["event2Count"]["room_unlock_cellar"] == 1
    assert after["itemData"]["roomDecorateDic"] == {"ItemEggMachine": [0]}
    assert edit.changed_fields == (
        "gameData.roomObjectLevel.Chest",
        "statisticData.event2Count.room_unlock_cellar",
    )
    assert edit.original == original


def test_unified_blueprint_and_decoration_share_required_blueprint_without_overlap():
    original = source()
    plan = {
        "blueprints": [
            {"id": "blueprint_room_decorate_drink_seller", "status": "Got"},
            {"id": "blueprint_multi_room_skin_2", "status": "Researched"},
        ],
        "decorations": {"objects": ["ObjectDrinkSeller"]},
    }
    edit = prepare_unified_edit(original, plan)
    after = json.loads(edit.candidate)
    assert edit.steps == ("blueprints", "decorations")
    assert after["itemData"]["blueprints"]["blueprint_room_decorate_drink_seller"] == "Researched"
    assert after["itemData"]["blueprints"]["multi_room_skin_2"] == "Researched"
    assert after["itemData"]["roomDecorateDic"]["ObjectDrinkSeller"] == [0]
    assert len(edit.changed_fields) == len(set(edit.changed_fields))
    # El plano compartido pertenece a Decoraciones, no se contabiliza dos veces.
    assert "itemData.blueprints.blueprint_room_decorate_drink_seller" in edit.changed_fields
    categories = {category.key: category.changes for category in edit.categories}
    assert categories == {"blueprints": 1, "decorations": 2}


def test_unified_blueprint_only_shared_removed_leaves_decoration_as_owner():
    original = source()
    plan = {
        "blueprints": [
            {"id": "blueprint_room_decorate_fishbowl", "status": "Got"},
        ],
        "decorations": {"objects": ["ObjectFishBowl"]},
    }
    edit = prepare_unified_edit(original, plan)
    after = json.loads(edit.candidate)
    assert edit.steps == ("decorations",)
    assert after["itemData"]["blueprints"]["blueprint_room_decorate_fishbowl"] == "Researched"
    assert edit.plan["blueprints"] is None
    assert edit.change_count == 2


def test_unified_all_four_decorative_blueprints_resolve_to_researched():
    original = source()
    objects = [
        "ObjectDrinkSeller",
        "ObjectFishBowl",
        "ObjectMagicWell",
        "ObjectMysteriouStatue",
    ]
    plan = {
        "blueprints": [
            {"id": "blueprint_room_decorate_drink_seller", "status": "Got"},
            {"id": "blueprint_room_decorate_fishbowl", "status": "Got"},
            {"id": "blueprint_room_decorate_magic_well", "status": "Got"},
            {"id": "blueprint_room_decorate_mysteriou_statue", "status": "Got"},
        ],
        "decorations": {"objects": objects},
    }
    edit = prepare_unified_edit(original, plan)
    after = json.loads(edit.candidate)
    assert edit.steps == ("decorations",)
    for key in (
        "blueprint_room_decorate_drink_seller",
        "blueprint_room_decorate_fishbowl",
        "blueprint_room_decorate_magic_well",
        "blueprint_room_decorate_mysteriou_statue",
    ):
        assert after["itemData"]["blueprints"][key] == "Researched"
    assert after["statisticData"]["event2Count"]["room_unlock_magic_area"] == 1


def test_decorations_facility_flags_are_explicit_and_preserve_unknown_counters():
    original = source()
    snapshot = read_decorations(original)
    facilities = {row["id"]: row for row in snapshot["facilities"]}
    assert facilities["room_unlock_garden"]["editable"] is True
    assert facilities["room_unlock_garden"]["present"] is False
    edit = prepare_decoration_edit(original, {
        "facilities": ["room_unlock_garden", "room_unlock_work_shop"],
    })
    after = json.loads(edit.candidate)["statisticData"]["event2Count"]
    assert after["room_unlock_garden"] == 1
    assert after["room_unlock_work_shop"] == 1
    assert after["unrelated_counter"] == 9
    assert edit.changed_fields == (
        "statisticData.event2Count.room_unlock_garden",
        "statisticData.event2Count.room_unlock_work_shop",
    )
    with pytest.raises(InvalidDecorationPlan):
        prepare_decoration_edit(original, {"facilities": ["room_unlock_statements_count"]})


def test_weapon_skin_equip_sets_current_index_and_restores_only_that_field():
    data = document()
    data["weaponEvolutionData"] = {
        "weapons": {
            "weapon_363": {
                "Name": "weapon_363",
                "Level": 0,
                "CurrentSkinIndex": 0,
                "UnlockedSkins": ["weapon_363_s_1"],
            },
        },
    }
    original = source(data)
    from app.cloud.weapon_skin_editor import (
        UnknownWeaponSkinEquip,
        prepare_weapon_skin_equip_edit,
        read_weapon_skins,
    )

    edit = prepare_weapon_skin_equip_edit(original, [
        {"weapon_id": "weapon_363", "skin_id": "weapon_363_s_1"},
    ])
    after = json.loads(edit.candidate)["weaponEvolutionData"]["weapons"]["weapon_363"]
    assert after["CurrentSkinIndex"] == 1
    assert after["Level"] == 0 and after["UnlockedSkins"] == ["weapon_363_s_1"]
    assert edit.changed_fields == (
        "weaponEvolutionData.weapons.weapon_363.CurrentSkinIndex",
    )
    snapshot = read_weapon_skins(edit.candidate)
    equipped = [row for row in snapshot.items if row["id"] == "weapon_363_s_1"][0]
    assert equipped["equipped"] is True

    noop = prepare_weapon_skin_equip_edit(edit.candidate, [
        {"weapon_id": "weapon_363", "skin_id": "weapon_363_s_1"},
    ])
    assert noop.changed is False
    assert noop.candidate == edit.candidate

    restore = prepare_weapon_skin_equip_edit(edit.candidate, [
        {"weapon_id": "weapon_363", "skin_id": None},
    ])
    assert json.loads(restore.candidate)["weaponEvolutionData"]["weapons"]["weapon_363"]["CurrentSkinIndex"] == 0
    with pytest.raises(UnknownWeaponSkinEquip):
        prepare_weapon_skin_equip_edit(original, [
            {"weapon_id": "weapon_407", "skin_id": "weapon_407_s_1"},
        ])


def test_unified_unlock_then_equip_weapon_skin_in_one_plan():
    data = document()
    data["weaponEvolutionData"] = {"weapons": {}}
    original = source(data)
    plan = {
        "weapon_skins": ["weapon_363_s_1"],
        "weapon_skin_equip": [
            {"weapon_id": "weapon_363", "skin_id": "weapon_363_s_1"},
        ],
    }
    edit = prepare_unified_edit(original, plan)
    assert edit.steps == ("weapon_skins", "weapon_skin_equip")
    record = json.loads(edit.candidate)["weaponEvolutionData"]["weapons"]["weapon_363"]
    assert record["UnlockedSkins"] == ["weapon_363_s_1"]
    assert record["CurrentSkinIndex"] == 1
    assert "weaponEvolutionData.weapons.weapon_363.UnlockedSkins" in edit.changed_fields
    assert "weaponEvolutionData.weapons.weapon_363.CurrentSkinIndex" in edit.changed_fields

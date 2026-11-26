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
    assert levels["Chest"]["editable"] is False
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
    assert edit.changed_fields == (
        "itemData.roomDecorateDic.ObjectSafe",
        "itemData.roomDecorateDic.PetFood",
        "gameData.roomObjectLevel.Book",
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

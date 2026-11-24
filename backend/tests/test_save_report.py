import json

from app.save_report import build_save_report, read_save_report


def aggregate() -> dict:
    return {
        "serialzedVersion": 1,
        "cloudSaveId": "privado-no-debe-salir",
        "platformId": "plataforma-privada",
        "gameData": {
            "gameVersion": 80800,
            "fishChip": 7,
            "heroUnlock": {"Knight": True, "Mage": False},
            "heroLevel": {"Knight": 2, "Mage": 0},
            "heroSkill": {"Knight": 1},
            "heroSkillUnlock": {
                "Knight": [{"Key": 0, "Value": True}, {"Key": 1, "Value": True}]
            },
            "skinLock": {"Knight": [{"Key": 0, "Value": 1}, {"Key": 1, "Value": -5}]},
            "currentSkinDatas": {"Knight": 0},
        },
        "itemData": {
            "materials": {"wood": 12, "fertilizer_basic": 3, "material_fish": 9},
            "seeds": {"seed_carrot": 4},
            "tokenTickets": {"ticket_1": 5},
            "blueprints": {"blueprint_a": "contenido-interno"},
            "itemUnlock": ["weapon_a", "weapon_b"],
            "plants": [{"plantName": "plant_a", "state": 1, "fertilized": True, "watered": False}],
            "commodities": [{"name": "item_a", "count": 2, "showBetterTable": True}],
            "forgeWeapons": [{"name": "forge_a"}],
            "cumulativeFishCount": 99,
        },
    }


def test_read_save_report_returns_sanitized_sections_and_no_private_ids():
    report = read_save_report(json.dumps(aggregate(), ensure_ascii=False).encode())
    assert report["version"] == 1
    assert report["serialzed_version"] == 1
    assert report["fish_chips"]["balance"] == 7
    assert report["fish_chips"]["status"] == "read_only"
    assert report["fish_chips"]["validation_level"] == "E4"
    assert report["fish_chips"]["write_policy"] == "confirmed_by_owner"
    assert report["fish_chips"]["transaction_validated"] is True
    assert "cloudSaveId" not in json.dumps(report)
    assert "privado-no-debe-salir" not in json.dumps(report)
    assert "plataforma-privada" not in json.dumps(report)


def test_report_lists_characters_with_catalog_names_and_read_only_status():
    report = read_save_report(json.dumps(aggregate(), ensure_ascii=False).encode())
    characters = {row["code"]: row for row in report["characters"]["items"]}
    knight = characters["Knight"]
    assert knight["name"] == "Knight"
    assert knight["unlocked"] is True
    assert knight["level"] == 2
    assert knight["level_max"] is None
    assert knight["level_status"] == "not_validated"
    assert knight["skills"][0] == {"key": 0, "unlocked": True, "name": "Dual Wield"}
    assert knight["selected_skin"] == 0
    assert knight["equipped_skin"]["name"] == "Knight"
    assert knight["skins_recorded"] == 2
    assert knight["skins_status"] == "confirmed_by_owner"
    assert report["characters"]["status"] == "read_only"


def test_report_groups_resources_without_exposing_blueprint_payloads():
    report = build_save_report(aggregate())
    groups = {row["id"]: row for row in report["resources"]["groups"]}
    assert groups["materials"]["entries"] == 3
    assert {"id": "wood", "count": 12} in groups["materials"]["items"]
    assert groups["seeds"]["items"] == [{"id": "seed_carrot", "count": 4}]
    assert groups["blueprints"]["items"] == [{"id": "blueprint_a", "type": "str", "text_length": 17}]
    assert groups["unlocked_items"]["items"] == [{"id": "weapon_a"}, {"id": "weapon_b"}]
    assert "contenido-interno" not in json.dumps(report)
    assert groups["plants"]["items"][0]["plant"] == "plant_a"
    assert groups["cumulative_fish_count"]["value"] == 99
    assert report["resources"]["status"] == "read_only"


def test_report_preserves_missing_sections_as_missing():
    document = {
        "gameData": {"gameVersion": 80800},
        "itemData": {},
    }
    report = build_save_report(document)
    groups = {row["id"]: row for row in report["resources"]["groups"]}
    assert groups["materials"]["state"] == "missing"
    assert report["fish_chips"]["balance"] is None
    assert report["characters"]["counts"]["characters"] == 42
    assert all(row["level"] == "<missing>" for row in report["characters"]["items"])
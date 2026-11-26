import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "knowledge" / "tools"
FIXTURE = ROOT / "backend" / "tests" / "fixtures" / "skdfe-mini"
CATALOGS = ROOT / "knowledge" / "catalogs"
sys.path.insert(0, str(TOOLS))

from sk_knowledge import common  # noqa: E402


def load_catalog(name):
    return common.read_json(CATALOGS / f"{name}.json")


def test_all_catalogs_match_the_documented_schema():
    schema = common.load_schema("catalog.schema.json")
    paths = sorted(CATALOGS.glob("*.json"))
    assert len(paths) == 26
    total = 0
    for path in paths:
        document = common.read_json(path)
        errors = common.validate_schema(document, schema)
        assert not errors, f"{path.name}: {errors[:5]}"
        assert document["schema"] == "sk-knowledge/catalog@1"
        assert document["game_version"] == "8.8.0"
        assert document["count"] == len(document["items"])
        assert len({item["id"] for item in document["items"]}) == document["count"]
        total += document["count"]
    assert total == 4348


def test_catalog_relations_resolve_to_known_items():
    catalogs = {path.stem: common.read_json(path) for path in CATALOGS.glob("*.json")}
    ids = {
        family: {item["id"] for item in document["items"]}
        for family, document in catalogs.items()
    }

    characters = catalogs["characters"]["items"]
    for character in characters:
        assert set(character["relations"]["character_skills"]) <= ids["character_skills"]
        assert set(character["relations"]["character_skins"]) <= ids["character_skins"]

    for pet in catalogs["pets"]["items"]:
        assert set(pet["relations"].get("skills", [])) <= ids["pet_skills"]
    for skill in catalogs["pet_skills"]["items"]:
        assert skill["relations"]["pet"] in ids["pets"]

    for skin in catalogs["weapon_skins"]["items"]:
        assert skin["relations"]["weapon"] in ids["weapons"]

    for seed in catalogs["seeds"]["items"]:
        assert seed["relations"]["plant"] in ids["plants"]
    for plant in catalogs["plants"]["items"]:
        assert plant["relations"]["seed"] in ids["seeds"]

    for boss in catalogs["bosses"]["items"]:
        assert boss["relations"]["enemy"] in ids["enemies"]

    for blueprint in catalogs["blueprints"]["items"]:
        for material in blueprint["relations"].get("research_materials", []):
            assert material["item"] in ids["materials"]


def test_backend_character_projection_matches_the_knowledge_catalog():
    backend = common.read_json(common.BACKEND_CHARACTER_CATALOG)
    knowledge = load_catalog("characters")
    by_index = {
        item["attributes"]["index"]: item for item in knowledge["items"]
    }
    assert sorted(by_index) == list(range(len(backend["characters"])))
    for entry in backend["characters"]:
        item = by_index[entry["index"]]
        assert entry["code"] == item["id"]
        assert [skill["key"] for skill in entry["skills"]] == item["relations"]["character_skills"]
        assert [skin["key"] for skin in entry["skins"]] == item["relations"]["character_skins"]
    assert sum(len(entry["skins"]) for entry in backend["characters"]) == 802
    assert sum(len(entry["skills"]) for entry in backend["characters"]) == 105


def test_pet_identity_gap_is_explicit_and_not_invented():
    pets = load_catalog("pets")["items"]
    by_id = {item["id"]: item for item in pets}
    assert by_id["Cat"]["attributes"]["numeric_id"] == 0
    assert by_id["Cat"]["name"]["en"] == "Chilly"
    assert by_id["Hide"]["attributes"]["numeric_id"] == 17
    assert by_id["Hide"]["name"] == {"en": None, "es": None, "zh_cn": None}
    assert by_id["FishChipKing"]["attributes"]["numeric_id"] == 57
    assert by_id["FishChipKing"]["name"]["en"] == "Fish Chip King"
    assert by_id["FishChipKing"]["save_refs"] == ["gameData.petUnlock.FishChipKing"]

    skins = {item["id"]: item for item in load_catalog("pet_skins")["items"]}
    assert len(skins) == 12
    assert skins["Cat1"]["attributes"]["base_pet"] == "Cat"
    assert skins["Cat1"]["relations"]["pet"] == "Cat"
    assert skins["Cat1"]["save_refs"] == ["gameData.petUnlock.Cat1"]


def test_weapon_catalog_distinguishes_visible_weapons_from_config_only_rows():
    weapons = {item["id"]: item for item in load_catalog("weapons")["items"]}
    assert weapons["weapon_000"]["attributes"]["in_weapon_catalog"] is True
    assert weapons["weapon_000"]["attributes"]["config_only"] is False
    assert weapons["ring_0"]["attributes"]["in_weapon_catalog"] is True
    assert weapons["ring_0"]["attributes"]["config_only"] is False
    assert weapons["weapon_amazing_staff"]["attributes"]["in_weapon_catalog"] is False
    assert weapons["weapon_amazing_staff"]["attributes"]["config_only"] is True
    assert weapons["weapon_amazing_staff"]["name"]["es"] == "Bastón Increíble"


def test_synthetic_source_build_is_deterministic_and_does_not_need_git(tmp_path):
    import build_catalog

    first = build_catalog.build_documents(
        FIXTURE, include_version_diffs=False, commit_override="fixture-commit"
    )
    second = build_catalog.build_documents(
        FIXTURE, include_version_diffs=False, commit_override="fixture-commit"
    )
    assert {str(path): common.canonical_json(value) for path, value in first.items()} == {
        str(path): common.canonical_json(value) for path, value in second.items()
    }
    catalogs = {
        path.name: value
        for path, value in first.items()
        if path.parent == common.CATALOGS_DIR
    }
    assert catalogs["characters.json"]["count"] == 2
    assert catalogs["weapons.json"]["count"] == 5
    assert catalogs["pets.json"]["count"] == 3
    assert catalogs["blueprints.json"]["count"] == 2
    assert catalogs["weapons.json"]["items"][0]["source"].startswith("SKDFE@fixture-commit:")
    assert tmp_path.is_dir()  # la fixture no escribe en el repositorio


def test_every_catalog_item_has_provenance_and_an_evidence_level():
    for path in CATALOGS.glob("*.json"):
        document = common.read_json(path)
        assert document["source_refs"]
        for item in document["items"]:
            assert item["evidence"] in common.EVIDENCE_LEVELS
            assert item["evidence"] in {"E1", "E2"}
            assert item["source"].startswith(("SKDFE@", "OWN@"))
            for language in ("en", "es"):
                assert language in item["name"]
from app.save_analysis import (
    MISSING,
    character_report,
    compare_documents,
    field_shapes,
    fish_chip_report,
    kind_of,
    section_summary,
    structural_diff,
    value_at,
)


def test_kind_of_does_not_confuse_bool_and_int():
    assert kind_of(True) == "bool"
    assert kind_of(1) == "int"
    assert kind_of(1.0) == "float"
    assert kind_of(None) == "null"


def test_section_summary_and_field_shapes_aggregate_list_entries():
    document = {
        "gameData": {"gems": 10, "heroLevel": {"Knight": 0, "Mage": 1}},
        "itemData": {"plants": [{"state": 1}, {"state": 1}]},
    }
    sections = {row["section"]: row for row in section_summary(document)}
    assert sections["gameData"]["entries"] == 2
    assert sections["itemData"]["entries"] == 1

    shapes = {row.path: row for row in field_shapes(document)}
    assert shapes["gameData.gems"].kind == "int"
    assert shapes["itemData.plants.[].state"].occurrences == 2
    assert shapes["itemData.plants.[].state"].distinct_values == 1


def test_field_shapes_counts_distinct_values_without_exposing_samples_by_default():
    rows = field_shapes({"a": [0, 0, 1], "b": {"c": "x"}})
    by_path = {row.path: row for row in rows}
    assert by_path["a.[]"].occurrences == 3
    assert by_path["a.[]"].distinct_values == 2
    assert by_path["a.[]"].sample is None
    assert by_path["a.[]"].as_dict() == {
        "path": "a.[]",
        "type": "int",
        "occurrences": 3,
        "distinct_values": 2,
    }


def test_value_at_and_missing_marker():
    document = {"a": {"b": [10]}}
    assert value_at(document, "a.b.0") == 10
    assert value_at(document, "a.b.1") is MISSING


def test_structural_diff_distinguishes_types_missing_and_indexed_lists():
    changes = structural_diff(
        {"a": 1, "b": [1], "c": True, "d": None},
        {"a": 2, "b": [1, 3], "c": 1, "e": None},
    )
    assert [(change.path, change.kind) for change in changes] == [
        ("a", "changed"),
        ("b.[1]", "added"),
        ("c", "type"),
        ("d", "removed"),
        ("e", "added"),
    ]
    assert changes[0].as_dict() == {"path": "a", "kind": "changed", "before": 1, "after": 2}


def test_compare_documents_omits_values_unless_requested_and_honors_ignore_prefixes():
    before = {"gameData": {"gems": 10, "lastGems": 0}, "itemData": {"x": 1}}
    after = {"gameData": {"gems": 9, "lastGems": 0}, "itemData": {"x": 2}}
    report = compare_documents(before, after, ignore=("itemData",))
    assert report["change_count"] == 1
    assert report["changes"] == [{"path": "gameData.gems", "kind": "changed"}]
    detail = compare_documents(before, after, include_values=True)
    assert detail["changes"][0]["before"] == 10
    assert detail["changed_sections"] == {"gameData": 1, "itemData": 1}


def test_fish_chip_report_does_not_conflate_fish_materials_or_season_chips():
    document = {
        "gameData": {"fishChip": 0},
        "itemData": {
            "cumulativeFishCount": 7218,
            "materials": {"material_fish": 99999999},
            "fishChipStorePurchaseHistoryIndexed": {"3_bundle_material_2": 0},
        },
        "mallReloadData": {"buyFishCount5": 0},
        "seasonData": {
            "chips": [{"chipName": "Zealot"}],
            "extraRewardChipTimesToday": 0,
        },
        "statisticData": {
            "StatisticsData": {"HallGameStatisticData": {"_buyItemUseFishChipTimes": {"Any": 999}}}
        },
    }
    report = fish_chip_report(document)
    assert report["balance_path"] == "gameData.fishChip"
    assert report["balance"] == 0
    assert report["balance_is_integer"] is True
    assert report["server_authority"] == "unknown"
    paths = {row["path"] for row in report["fields"]}
    assert "itemData.cumulativeFishCount" not in paths
    assert "itemData.materials" not in paths
    assert report["distinct_collections"]["season_chips"] == {"type": "list", "entries": 1}


def test_fish_chip_report_requires_game_data_balance():
    report = fish_chip_report({"itemData": {"cumulativeFishCount": 1}})
    assert report["balance_path"] is None
    assert report["balance_is_integer"] is False


def test_character_report_uses_catalog_only_for_names_and_keeps_missing_states():
    game = {
        "heroUnlock": {"Knight": True},
        "heroLevel": {"Knight": 3},
        "heroSkill": {"Knight": 1},
        "heroSkillUnlock": {"Knight": [{"Key": 0, "Value": True}, {"Key": 1, "Value": False}]},
        "skinLock": {"Knight": [{"Key": 0, "Value": 1}, {"Key": 1, "Value": -6}]},
        "currentSkinDatas": {"Knight": 0},
        "petUnlock": {"Cat": True},
    }
    report = character_report(
        game,
        character_codes=["Knight"],
        skin_catalog={"c0": {"c0_skin0": "Knight", "c0_skin1": "Elite Knight"}},
        skill_catalog={"Character0_skill_0_name": "Dual Wield"},
    )
    knight = report["characters"][0]
    assert knight["catalog_index"] == 0
    assert knight["unlocked"] is True
    assert knight["level"] == 3
    assert knight["selected_skill"] == 1
    assert knight["selected_skin"] == 0
    assert knight["skills"] == [
        {"key": 0, "unlocked": True, "name": "Dual Wield"},
        {"key": 1, "unlocked": False, "name": None},
    ]
    assert knight["skins"][1] == {"key": 1, "state": -6, "name": "Elite Knight"}
    assert report["counts"] == {"characters": 1, "unlocked": 1, "selected_skins": 1}


def test_character_report_accepts_a_document_without_optional_maps():
    report = character_report({})
    assert report == {"characters": [], "counts": {"characters": 0, "unlocked": 0, "selected_skins": 0}}
from pathlib import Path

import pytest

from app.cloud.resource_consistency import (
    ConsistencyUnknown, aggregate_tree, inspect_resource, plan_gems_transition, structural_diff,
)

FIXTURE = Path(__file__).parent / "fixtures" / "cloud-save-gems.json"


def test_inspect_and_reject_unknown_dependencies():
    tree = aggregate_tree(FIXTURE.read_bytes())
    assert inspect_resource(tree, "gems")["gameData.gems"] == "int"
    del tree["gameData"]["varGems"]
    with pytest.raises(ConsistencyUnknown, match="lastGems o varGems"):
        plan_gems_transition(tree, 1001)


def test_plan_preserves_existing_fields_and_does_not_require_historical_totals():
    data = {"gems": 10, "lastGems": 25, "varGems": -15}
    tree = {"serialzedVersion": 1, "gameData": data}
    assert plan_gems_transition(tree, 2) == {"gems": 2, "varGems": -23}
    assert data == {"gems": 10, "lastGems": 25, "varGems": -15}


def test_plan_rejects_a_variation_outside_int32():
    tree = {"serialzedVersion": 1, "gameData": {"gems": 0, "lastGems": -1, "varGems": 1}}
    with pytest.raises(ConsistencyUnknown, match="variación"):
        plan_gems_transition(tree, 2**31 - 1)


def test_diff_distinguishes_types_missing_and_list_entries():
    diff = structural_diff({"a": 1, "b": [1], "c": True},
                           {"a": 2, "b": [1, 3], "c": 1, "d": None})
    assert [(d["path"], d["kind"]) for d in diff] == [
        (("a",), "changed"), (("b", 1), "added"), (("c",), "type"), (("d",), "added")]


def test_reject_invalid_aggregate():
    with pytest.raises(ValueError):
        aggregate_tree(b'{}')

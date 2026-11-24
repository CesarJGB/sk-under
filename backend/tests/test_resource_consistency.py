from pathlib import Path

import pytest

from app.cloud.resource_consistency import (
    ConsistencyUnknown, aggregate_tree, inspect_resource, structural_diff, validate_gems_transition,
)

FIXTURE = Path(__file__).parent / "fixtures" / "cloud-save-gems.json"


def test_inspect_and_reject_unknown_dependencies():
    tree = aggregate_tree(FIXTURE.read_bytes())
    assert inspect_resource(tree, "gems")["gameData.gems"] == "int"
    with pytest.raises(ConsistencyUnknown):
        validate_gems_transition(tree, 1001)
    assert tree == aggregate_tree(FIXTURE.read_bytes())


def test_diff_distinguishes_types_missing_and_list_entries():
    diff = structural_diff({"a": 1, "b": [1], "c": True},
                           {"a": 2, "b": [1, 3], "c": 1, "d": None})
    assert [(d["path"], d["kind"]) for d in diff] == [
        (("a",), "changed"), (("b", 1), "added"), (("c",), "type"), (("d",), "added")]


def test_reject_invalid_aggregate():
    with pytest.raises(ValueError):
        aggregate_tree(b'{}')

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "knowledge" / "tools"
sys.path.insert(0, str(TOOLS))

import build_fields  # noqa: E402
from sk_knowledge import common  # noqa: E402


def test_fields_document_matches_schema_and_declares_every_aspect():
    document = common.read_json(common.FIELDS_DIR / "fields.json")
    assert common.validate_schema(document, common.load_schema("fields.schema.json")) == []
    assert document["schema"] == common.FIELDS_SCHEMA
    assert document["field_count"] == len(document["fields"]) == 616
    assert document["counts_by_validation_level"] == {
        "H": 0,
        "E1": 194,
        "E2": 405,
        "E3": 11,
        "E4": 6,
    }
    for field in document["fields"]:
        assert set(field["evidence"]) == set(common.EVIDENCE_ASPECTS)
        assert field["edit_policy"]
        assert field["registry_tier"] in {"legacy", "declared"}
        if field["registry_tier"] == "legacy":
            assert field["legacy_record"]


def test_legacy_projection_is_byte_identical_to_the_frozen_registry():
    document = common.read_json(common.FIELDS_DIR / "fields.json")
    projected = common.canonical_json(build_fields.projection(document))
    current = common.LEGACY_FIELD_REGISTRY.read_text(encoding="utf-8")
    assert projected == current
    assert len(build_fields.projection(document)["fields"]) == 66


def test_every_field_source_is_traceable_or_declared():
    document = common.read_json(common.FIELDS_DIR / "fields.json")
    known_prefixes = {"docs/", "backend/", "knowledge/", "propia", "discord", "skdfe"}
    for field in document["fields"]:
        assert field["sources"], field["id"]
        for source in field["sources"]:
            assert any(source == prefix or source.startswith(prefix) for prefix in known_prefixes), (
                field["id"],
                source,
            )
            if source.startswith(("docs/", "backend/", "knowledge/")):
                assert (ROOT / source).exists(), (field["id"], source)


def test_declared_fields_do_not_claim_semantics_without_evidence():
    document = common.read_json(common.FIELDS_DIR / "fields.json")
    for field in document["fields"]:
        if field["registry_tier"] == "declared":
            if field["id"] in {"gameData.currentRoomDecorate", "gameData.roomLevel"}:
                assert field["evidence"]["semantics"] == "E2", field["id"]
            else:
                assert field["evidence"]["semantics"] in {"H", "E1"}, field["id"]
            assert field["validation_level"] in {"E1", "E2"}, field["id"]
        assert field["validation_level"] in common.EVIDENCE_LEVELS


def test_field_ids_are_unique_and_normalized():
    document = common.read_json(common.FIELDS_DIR / "fields.json")
    ids = [field["id"] for field in document["fields"]]
    assert len(ids) == len(set(ids))
    for field_id in ids:
        assert field_id == common.normalize_id(field_id), field_id

def test_owner_confirmed_functions_are_e3_and_battle_pass_remains_e2():
    document = common.read_json(common.FIELDS_DIR / "fields.json")
    fields = {field["id"]: field for field in document["fields"]}
    for field_id in (
        "itemData.materials",
        "itemData.seeds",
        "seasonData.coin",
        "gameData.rebornCard",
        "itemData.cumulativeFishCount",
    ):
        field = fields[field_id]
        assert field["validation_level"] == "E3"
        assert "confirmed_by_owner" in field["edit_policy"]
        assert field["evidence"]["persistence"] == "E3"
    for field_id in (
        "battlePassSaveData.seasonData",
        "battlePassSaveData.seasonData._.Value.curLevel",
        "battlePassSaveData.seasonData._.Value.curExp",
        "battlePassSaveData.seasonData._.Value.hasBuy",
    ):
        field = fields[field_id]
        assert field["validation_level"] == "E2"
        assert "experimental" in field["edit_policy"]
    pets = fields["gameData.petUnlock"]
    assert pets["validation_level"] == "E3"
    assert "confirmed_by_owner" in pets["edit_policy"]

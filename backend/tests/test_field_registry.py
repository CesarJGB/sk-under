import json
from pathlib import Path

REGISTRY = Path(__file__).resolve().parents[2] / "docs" / "save-research" / "field-registry.json"
REQUIRED = {
    "internal_name",
    "category",
    "locations",
    "raw_types",
    "sources",
    "observed_versions",
    "known_dependencies",
    "pending_dependencies",
    "validation_level",
    "edit_policy",
    "experimental_evidence",
}
READ_ONLY = {
    "heroLevel",
    "heroSkill",
    "currentSkinDatas",
    "materials",
    "seeds",
    "tokenTickets",
    "blueprints",
    "itemUnlock",
    "plants",
    "commodities",
    "forgeWeapons",
    "specialTickets",
}


def registry() -> dict:
    return json.loads(REGISTRY.read_text(encoding="utf-8"))


def test_registry_has_unique_fields_and_known_evidence_levels():
    data = registry()
    levels = set(data["evidence_levels"])
    assert data["schema_version"] == 1
    assert levels == {"E1", "E2", "E3", "E4", "H"}
    names = [field["internal_name"] for field in data["fields"]]
    assert len(names) == len(set(names))
    assert len(names) == 66
    for field in data["fields"]:
        assert REQUIRED <= set(field), field["internal_name"]
        assert field["validation_level"] in levels, field["internal_name"]
        assert isinstance(field["known_dependencies"], list)
        assert isinstance(field["pending_dependencies"], list)


def test_report_fields_remain_read_only():
    data = registry()
    fields = {field["internal_name"]: field for field in data["fields"]}
    assert READ_ONLY <= set(fields)
    for name in READ_ONLY:
        assert fields[name]["edit_policy"].startswith("solo lectura"), name
    assert fields["fishChip"]["validation_level"] == "E4"
    assert fields["fishChip"]["edit_policy"].startswith("escritura confirmada")
    assert "Fase 6.13" in fields["fishChip"]["experimental_evidence"]
    assert "Fase 6.14" in fields["fishChip"]["experimental_evidence"]
    assert "Fase 6.16" in fields["fishChip"]["experimental_evidence"]
    assert "material_fish (confirmado" in fields["fishChip"]["known_dependencies"][0]
    assert fields["heroLevel"]["validation_level"] == "E3"
    assert fields["heroUnlock"]["validation_level"] == "E3"
    assert fields["heroUnlock"]["edit_policy"].startswith("escritura confirmada por el propietario")
    assert "confirmed_by_owner" in fields["heroUnlock"]["edit_policy"]
    assert "heroLevel" in fields["heroUnlock"]["experimental_evidence"]
    assert "Fase 6.16" in fields["heroUnlock"]["experimental_evidence"]
    assert fields["heroSkillUnlock"]["validation_level"] == "E3"
    assert fields["heroSkillUnlock"]["edit_policy"].startswith("escritura confirmada por el propietario")
    assert "confirmed_by_owner" in fields["heroSkillUnlock"]["edit_policy"]
    assert "Fase 6.17" in fields["heroSkillUnlock"]["experimental_evidence"]
    assert "Fase 6.18" in fields["heroSkillUnlock"]["experimental_evidence"]
    assert fields["skinLock"]["validation_level"] == "E3"
    assert fields["skinLock"]["edit_policy"].startswith("escritura confirmada por el propietario")
    assert "confirmed_by_owner" in fields["skinLock"]["edit_policy"]
    assert "Fase 6.18" in fields["skinLock"]["experimental_evidence"]
    assert "Fase 6.19" in fields["skinLock"]["experimental_evidence"]


def test_registry_links_exist_relative_to_documentation():
    data = registry()
    directory = REGISTRY.parent
    assert data["source_index"]["phase6-13"] == "../research/phase6-13/README.md"
    assert data["source_index"]["phase6-14"] == "../research/phase6-14/README.md"
    assert data["source_index"]["phase6-16"] == "../research/phase6-16/README.md"
    assert data["source_index"]["phase6-17"] == "../research/phase6-17/README.md"
    assert data["source_index"]["phase6-18"] == "../research/phase6-18/README.md"
    for source, target in data["source_index"].items():
        assert (directory / target).is_file(), source
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "knowledge" / "tools"
sys.path.insert(0, str(TOOLS))

import compare_versions  # noqa: E402
import generate_report  # noqa: E402
import search_knowledge  # noqa: E402
import validate_knowledge  # noqa: E402
from sk_knowledge import common  # noqa: E402


def test_search_finds_catalog_items_and_fields(capsys):
    assert search_knowledge.main(["knight", "--type", "catalogs", "--limit", "5", "--json"]) == 0
    catalogs = json.loads(capsys.readouterr().out)
    assert catalogs
    assert catalogs[0]["type"] == "catalog"
    assert catalogs[0]["data"]["id"]

    assert search_knowledge.main(["--field", "fishChip", "--type", "fields", "--json"]) == 0
    fields = json.loads(capsys.readouterr().out)
    assert any(entry["id"] == "gameData.fishChip" for entry in fields)

    assert search_knowledge.main(["--path", "gameData.hero", "--type", "fields", "--limit", "5"]) == 0
    assert "resultado" in capsys.readouterr().out


def test_search_returns_nonzero_when_there_are_no_matches(capsys):
    assert search_knowledge.main(["termino_que_no_existe_7_0", "--type", "catalogs"]) == 1
    assert "Sin resultados" in capsys.readouterr().out


def test_compare_versions_reports_known_weapon_growth():
    result = compare_versions.compare_snapshots("8.6.0", "8.8.0", "weapons")
    weapons = result["families"]["weapons"]
    assert weapons["count_before"] == 982
    assert weapons["count_after"] == 995
    assert len(weapons["added"]) == 13
    assert weapons["removed"] == []


def test_compare_catalog_files_detects_changes(tmp_path):
    current = common.read_json(common.CATALOGS_DIR / "characters.json")
    assert compare_versions.compare_catalog_files(
        common.CATALOGS_DIR / "characters.json",
        common.CATALOGS_DIR / "characters.json",
    )["families"]["characters"]["changed"] == []

    changed = json.loads(common.canonical_json(current))
    changed["items"][0]["name"]["en"] = "Changed"
    path = tmp_path / "characters.json"
    path.write_text(common.canonical_json(changed), encoding="utf-8")
    result = compare_versions.compare_catalog_files(
        common.CATALOGS_DIR / "characters.json", path
    )
    assert result["families"]["characters"]["changed"] == [changed["items"][0]["id"]]


def test_validation_passes_without_the_manifest_check(capsys):
    assert validate_knowledge.main(["--no-manifest-check", "--quiet"]) == 0
    assert capsys.readouterr().err == ""


def test_coverage_report_matches_the_generated_artifacts():
    report = generate_report.coverage(generate_report.load_all())
    assert report["fields"]["total"] == 616
    assert report["fields"]["by_level"] == {"E1": 194, "E2": 404, "E3": 12, "E4": 6}
    assert report["catalog_items"] == 4348
    assert len(report["catalogs"]) == 26
    assert report["translations"] == 8562
    assert report["dependencies"]["total"] == 49
    assert report["sources"] == 23
    assert report["versions_analyzed"] == ["8.6.0", "8.7.0", "8.8.0"]
    rendered = generate_report.render_coverage(report)
    assert "Cobertura del Save Knowledge Engine" in rendered
    assert "8.8.0" in rendered


def test_dependency_and_source_headers_match_their_lists():
    dependencies = common.read_json(common.DEPENDENCIES_DIR / "dependencies.json")
    assert dependencies["count"] == len(dependencies["dependencies"]) == 49
    assert common.validate_schema(
        dependencies, common.load_schema("dependencies.schema.json")
    ) == []
    sources = common.read_json(common.SOURCES_DIR / "sources.json")
    assert sources["count"] == len(sources["sources"]) == 23
    assert common.validate_schema(sources, common.load_schema("sources.schema.json")) == []
    for source in sources["sources"]:
        location = source["location"]
        if location.startswith(("docs/", "backend/")):
            assert (ROOT / location).exists(), location


def test_knowledge_tree_contains_no_saves_secrets_or_large_raw_exports():
    forbidden = {".sav", ".save", ".skdb", ".data", ".apk", ".xapk", ".apks"}
    patterns = [
        re.compile(r"SK_ACCESS_TOKEN\s*[=:]"),
        re.compile(r"SK_SAVE_(?:GENERAL|STATISTICS)_KEY_HEX\s*[=:]"),
        re.compile(r"SK_SAVE_IV_HEX\s*[=:]"),
        re.compile(r"BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY"),
        re.compile(r"ghp_[A-Za-z0-9]{30,}"),
        re.compile(r"github_pat_[A-Za-z0-9_]{30,}"),
    ]
    for path in common.KNOWLEDGE_DIR.rglob("*"):
        if not path.is_file():
            continue
        assert path.suffix.lower() not in forbidden, path
        assert path.stat().st_size < 2_000_000, path
        text = path.read_text(encoding="utf-8", errors="ignore")
        for pattern in patterns:
            assert pattern.search(text) is None, (path, pattern.pattern)


def test_id_normalization_is_stable_for_known_paths():
    assert common.normalize_id("gameData.heroUnlock") == "gameData.heroUnlock"
    assert common.normalize_id("weaponEvolutionData.weapons.{id}.Level") == (
        "weaponEvolutionData.weapons._.Level"
    )
    assert common.normalize_id("battlePassSaveData.seasonData[].Value.curExp") == (
        "battlePassSaveData.seasonData._.Value.curExp"
    )
    assert common.normalize_id("mallReloadData.buyFishCount{5,10}") == (
        "mallReloadData.buyFishCount"
    )
import json
import logging
from fnmatch import fnmatchcase
from pathlib import Path

import pytest

import app
from app.catalogs import (
    CATALOG_PATH,
    CharacterCatalogError,
    clear_character_catalog_cache,
    load_character_catalog,
    validate_character_catalog,
)
from app.cloud.character_editor import CharacterCatalogMissing, character_catalog_codes
from app.save_report import _load_character_catalog

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"


def test_catalog_is_bundled_inside_the_app_package():
    package = Path(app.__file__).resolve().parent
    assert CATALOG_PATH.is_file()
    assert CATALOG_PATH.is_relative_to(package)
    assert "docs" not in CATALOG_PATH.parts
    assert load_character_catalog()["available"] is True


def test_catalog_has_the_expected_content_and_unique_codes():
    catalog = load_character_catalog()
    validate_character_catalog(catalog)
    assert catalog["version"] == "8.8.0"
    assert len(catalog["codes"]) == 42
    assert catalog["codes"][:2] == ["Knight", "Ranger"]
    assert len(set(catalog["codes"])) == 42
    assert len(catalog["characters"]) == 42
    assert len(catalog["skills"]) == 105
    assert sum(len(group) for group in catalog["skins"].values()) == 802
    assert _load_character_catalog()["codes"] == catalog["codes"]


def test_missing_catalog_is_reported_and_does_not_poison_the_cache(tmp_path, caplog):
    target = tmp_path / "characters.json"
    with caplog.at_level(logging.ERROR, logger="app.catalogs"):
        missing = load_character_catalog(target)
    assert missing["available"] is False
    assert missing["error"] == "catalog_missing"
    assert missing["codes"] == []
    assert "Character catalog unavailable" in caplog.text

    target.write_bytes(CATALOG_PATH.read_bytes())
    recovered = load_character_catalog(target)
    assert recovered["available"] is True
    assert len(recovered["codes"]) == 42


def test_corrupt_catalog_is_a_controlled_error(tmp_path):
    invalid_json = tmp_path / "invalid.json"
    invalid_json.write_text("{", encoding="utf-8")
    catalog = load_character_catalog(invalid_json)
    assert catalog["available"] is False
    assert catalog["error"] == "catalog_invalid_json"
    assert catalog["codes"] == []

    invalid_structure = tmp_path / "structure.json"
    invalid_structure.write_text(
        json.dumps({"version": "8.8.0", "source": "test", "characters": []}),
        encoding="utf-8",
    )
    catalog = load_character_catalog(invalid_structure)
    assert catalog["available"] is False
    assert catalog["error"] == "catalog_invalid_structure"

    duplicated = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    duplicated["characters"][1]["code"] = duplicated["characters"][0]["code"]
    duplicate_path = tmp_path / "duplicate.json"
    duplicate_path.write_text(json.dumps(duplicated), encoding="utf-8")
    catalog = load_character_catalog(duplicate_path)
    assert catalog["available"] is False
    assert catalog["error"] == "catalog_invalid_structure"


def test_build_validation_rejects_incomplete_content(tmp_path):
    incomplete = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    incomplete["characters"] = incomplete["characters"][:-1]
    target = tmp_path / "incomplete.json"
    target.write_text(json.dumps(incomplete), encoding="utf-8")
    clear_character_catalog_cache()
    catalog = load_character_catalog(target)
    assert catalog["available"] is True
    with pytest.raises(CharacterCatalogError) as error:
        validate_character_catalog(catalog)
    assert error.value.code == "catalog_unexpected_size"


def test_missing_catalog_blocks_preparation(monkeypatch):
    empty = {
        "available": False,
        "error": "catalog_missing",
        "codes": [],
        "characters": {},
        "skins": {},
        "skills": {},
    }
    monkeypatch.setattr("app.cloud.character_editor.load_character_catalog", lambda: empty)
    with pytest.raises(CharacterCatalogMissing):
        character_catalog_codes()


def _dockerignore_includes(relative: str) -> bool:
    ignored = False
    for raw in (BACKEND / ".dockerignore").read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        negated = line.startswith("!")
        pattern = line[1:] if negated else line
        matches = fnmatchcase(relative, pattern)
        if pattern.endswith("/"):
            matches = matches or relative.startswith(pattern)
        if matches:
            ignored = not negated
    return not ignored


def test_docker_image_bundles_and_validates_the_catalog():
    catalog_relative = CATALOG_PATH.relative_to(BACKEND).as_posix()
    assert catalog_relative == "app/catalogs/characters-880.json"
    assert _dockerignore_includes(catalog_relative)
    assert _dockerignore_includes("Dockerfile")
    assert _dockerignore_includes("pyproject.toml")
    assert _dockerignore_includes("uv.lock")

    dockerfile = (BACKEND / "Dockerfile").read_text(encoding="utf-8")
    assert "COPY app/ ./app/" in dockerfile
    assert "python -m app.catalogs.verify" in dockerfile
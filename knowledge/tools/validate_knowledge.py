#!/usr/bin/env python3
"""Valida esquemas, integridad, referencias, fuentes, evidencia y secretos.

Uso:
    python3 knowledge/tools/validate_knowledge.py
    python3 knowledge/tools/validate_knowledge.py --write-manifest
    python3 knowledge/tools/validate_knowledge.py --quiet
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import build_fields  # noqa: E402
from sk_knowledge import common  # noqa: E402
from sk_knowledge.common import (  # noqa: E402
    CATALOG_SCHEMA,
    CATALOGS_DIR,
    DEPENDENCIES_SCHEMA,
    DEPENDENCIES_DIR,
    EVIDENCE_ASPECTS,
    EVIDENCE_LEVELS,
    FIELDS_SCHEMA,
    FIELDS_DIR,
    KNOWLEDGE_DIR,
    LEGACY_FIELD_REGISTRY,
    MANIFEST_PATH,
    MANIFEST_SCHEMA,
    REPO_ROOT,
    SOURCES_DIR,
    SOURCES_SCHEMA,
    TRANSLATIONS_DIR,
    VERSION_DIFFS_DIR,
    canonical_json,
    load_schema,
    read_json,
    sha256_file,
    validate_schema,
)

SAFE_SOURCE_TOKENS = {"propia", "discord", "skdfe"}
SECTION_PREFIXES = {
    "cloud",
    "gameData",
    "itemData",
    "statisticData",
    "settingData",
    "taskData",
    "seasonData",
    "mallReloadData",
    "monsterRiseData",
    "weaponEvolutionData",
    "miscData",
    "pvpData",
    "battlePassSaveData",
    "escapeSeasonData",
    "playerprefs",
    "catalog",
    "external",
}
SECRET_PATTERNS = [
    re.compile(r"SK_ACCESS_TOKEN\s*[=:]"),
    re.compile(r"SK_SAVE_(?:GENERAL|STATISTICS)_KEY_HEX\s*[=:]"),
    re.compile(r"SK_SAVE_IV_HEX\s*[=:]"),
    re.compile(r"BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY"),
    re.compile(r"ghp_[A-Za-z0-9]{30,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{30,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
]
FORBIDDEN_SUFFIXES = {".sav", ".save", ".skdb", ".data", ".apk", ".xapk", ".apks"}


class Report:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def error(self, message: str) -> None:
        self.errors.append(message)

    def warn(self, message: str) -> None:
        self.warnings.append(message)


def validate_catalogs(report: Report) -> dict[str, dict[str, Any]]:
    schema = load_schema("catalog.schema.json")
    catalogs: dict[str, dict[str, Any]] = {}
    for path in sorted(CATALOGS_DIR.glob("*.json")):
        document = read_json(path)
        for error in validate_schema(document, schema):
            report.error(f"{path.relative_to(REPO_ROOT)}: {error}")
        family = document.get("family")
        if path.stem != family:
            report.error(f"{path.name}: family {family!r} no coincide con el nombre del archivo")
        items = document.get("items", [])
        if document.get("count") != len(items):
            report.error(f"{path.name}: count={document.get('count')} pero hay {len(items)} elementos")
        ids: set[str] = set()
        for item in items:
            item_id = item.get("id")
            if item_id in ids:
                report.error(f"{path.name}: id duplicado {item_id!r}")
            ids.add(item_id)
            if item.get("evidence") not in EVIDENCE_LEVELS:
                report.error(f"{path.name}: evidencia inválida en {item_id!r}")
            source = str(item.get("source") or "")
            if not re.match(r"^SKDFE@[0-9a-f]{40}:.+$", source):
                report.error(f"{path.name}: fuente sin commit fijado en {item_id!r}: {source!r}")
        catalogs[family] = document
    return catalogs


def resolve_relation(
    catalogs: dict[str, dict[str, Any]], family: str, item_id: str | None
) -> bool:
    if not item_id:
        return True
    return item_id in {item["id"] for item in catalogs.get(family, {}).get("items", [])}


def validate_catalog_relations(
    catalogs: dict[str, dict[str, Any]], report: Report
) -> None:
    checks = {
        "character_skills": [("character", "characters")],
        "character_skins": [("character", "characters")],
        "weapon_skins": [("weapon", "weapons")],
        "seeds": [("plant", "plants")],
        "plants": [("seed", "seeds")],
        "bosses": [("enemy", "enemies")],
    }
    for family, rules in checks.items():
        for item in catalogs.get(family, {}).get("items", []):
            for relation, target_family in rules:
                target = (item.get("relations") or {}).get(relation)
                if target and not resolve_relation(catalogs, target_family, target):
                    report.error(
                        f"{family}:{item['id']} referencia {relation}={target!r} inexistente"
                    )
    for item in catalogs.get("pets", {}).get("items", []):
        for skill in (item.get("relations") or {}).get("skills", []):
            if not resolve_relation(catalogs, "pet_skills", skill):
                report.error(f"pets:{item['id']} referencia skill inexistente {skill!r}")
    for item in catalogs.get("pet_skills", {}).get("items", []):
        target = (item.get("relations") or {}).get("pet")
        if target and not resolve_relation(catalogs, "pets", target):
            report.error(f"pet_skills:{item['id']} referencia pet inexistente {target!r}")


def validate_fields(report: Report) -> dict[str, Any]:
    schema = load_schema("fields.schema.json")
    path = FIELDS_DIR / "fields.json"
    document = read_json(path)
    for error in validate_schema(document, schema):
        report.error(f"{path.relative_to(REPO_ROOT)}: {error}")
    fields = document.get("fields", [])
    if document.get("field_count") != len(fields):
        report.error(f"fields.json: field_count={document.get('field_count')} pero hay {len(fields)}")
    ids: set[str] = set()
    for field in fields:
        field_id = field.get("id")
        if field_id in ids:
            report.error(f"fields.json: id duplicado {field_id!r}")
        ids.add(field_id)
        evidence = field.get("evidence") or {}
        if set(evidence) != set(EVIDENCE_ASPECTS):
            report.error(f"fields.json:{field_id}: aspectos de evidencia incompletos")
        for aspect in EVIDENCE_ASPECTS:
            if evidence.get(aspect) not in EVIDENCE_LEVELS:
                report.error(f"fields.json:{field_id}: evidencia {aspect} inválida")
        if field.get("validation_level") not in EVIDENCE_LEVELS:
            report.error(f"fields.json:{field_id}: validation_level inválido")
        for source in field.get("sources", []):
            if source in SAFE_SOURCE_TOKENS:
                continue
            if not (REPO_ROOT / source).exists():
                report.error(f"fields.json:{field_id}: fuente inexistente {source!r}")
    expected = build_fields.projection(document)
    if canonical_json(expected) != LEGACY_FIELD_REGISTRY.read_text(encoding="utf-8"):
        report.error(
            "La proyección legacy de fields.json no coincide con docs/save-research/field-registry.json"
        )
    return document


def validate_dependencies(
    catalogs: dict[str, dict[str, Any]], fields: dict[str, Any], report: Report
) -> dict[str, Any]:
    schema = load_schema("dependencies.schema.json")
    path = DEPENDENCIES_DIR / "dependencies.json"
    document = read_json(path)
    for error in validate_schema(document, schema):
        report.error(f"{path.relative_to(REPO_ROOT)}: {error}")
    dependencies = document.get("dependencies", [])
    if document.get("count") != len(dependencies):
        report.error(f"dependencies.json: count={document.get('count')} pero hay {len(dependencies)}")
    field_ids = {field["id"] for field in fields.get("fields", [])}
    ids: set[str] = set()

    def valid_endpoint(endpoint: str) -> bool:
        if endpoint in field_ids:
            return True
        prefix = endpoint.split(".", 1)[0]
        if prefix not in SECTION_PREFIXES:
            return False
        if prefix == "catalog":
            family = endpoint.split(".", 1)[1].split(".", 1)[0]
            return family in catalogs
        if prefix == "external":
            return True
        return True

    for dependency in dependencies:
        if dependency.get("id") in ids:
            report.error(f"dependencies.json: id duplicado {dependency.get('id')!r}")
        ids.add(dependency.get("id"))
        for side in ("from", "to"):
            endpoint = dependency.get(side)
            if not isinstance(endpoint, str) or not valid_endpoint(endpoint):
                report.error(
                    f"dependencies.json:{dependency.get('id')}: {side} desconocido {endpoint!r}"
                )
    return document


def validate_sources(report: Report) -> dict[str, Any]:
    schema = load_schema("sources.schema.json")
    path = SOURCES_DIR / "sources.json"
    document = read_json(path)
    for error in validate_schema(document, schema):
        report.error(f"{path.relative_to(REPO_ROOT)}: {error}")
    sources = document.get("sources", [])
    if document.get("count") != len(sources):
        report.error(f"sources.json: count={document.get('count')} pero hay {len(sources)}")
    ids: set[str] = set()
    for source in sources:
        if source.get("id") in ids:
            report.error(f"sources.json: id duplicado {source.get('id')!r}")
        ids.add(source.get("id"))
        location = str(source.get("location") or "")
        if location.startswith(("docs/", "knowledge/", "backend/")):
            if not (REPO_ROOT / location).exists():
                report.error(f"sources.json:{source.get('id')}: ruta inexistente {location!r}")
        elif not location.startswith(("http://", "https://")):
            report.error(f"sources.json:{source.get('id')}: ubicación no reconocida {location!r}")
    return document


def validate_version_diffs(report: Report) -> dict[str, Any]:
    snapshots_path = VERSION_DIFFS_DIR / "snapshots.json"
    if not snapshots_path.is_file():
        report.error("Falta knowledge/version-diffs/snapshots.json")
        return {}
    snapshots = read_json(snapshots_path)
    versions = snapshots.get("versions", {})
    if len(versions) < 2:
        report.error("snapshots.json: se esperaban al menos dos versiones")
    for version, data in versions.items():
        commit = data.get("commit")
        if not isinstance(commit, str) or not re.fullmatch(r"[0-9a-f]{7,40}", commit):
            report.error(f"snapshots.json:{version}: commit inválido {commit!r}")
        counts = data.get("counts", {})
        ids = data.get("ids", {})
        for family, count in counts.items():
            if len(ids.get(family, [])) != count:
                report.error(f"snapshots.json:{version}:{family}: count no coincide con ids")
    for path in sorted(VERSION_DIFFS_DIR.glob("*_to_*.json")):
        document = read_json(path)
        if document.get("schema") != "sk-knowledge/version-diff@1":
            report.error(f"{path.name}: schema inesperado")
        for family, data in (document.get("families") or {}).items():
            if data.get("count_after") - data.get("count_before") != len(data.get("added", [])) - len(data.get("removed", [])):
                report.error(f"{path.name}:{family}: recuentos y diffs incoherentes")
    return snapshots


def validate_translations(catalogs: dict[str, dict[str, Any]], report: Report) -> dict[str, Any]:
    path = TRANSLATIONS_DIR / "name-index.json"
    if not path.is_file():
        report.error("Falta knowledge/translations/name-index.json")
        return {}
    document = read_json(path)
    entries = document.get("entries", [])
    if document.get("count") != len(entries):
        report.error("name-index.json: count no coincide con entries")
    known = {
        (catalog, item["id"])
        for catalog, data in catalogs.items()
        for item in data.get("items", [])
    }
    for entry in entries:
        if (entry.get("catalog"), entry.get("item_id")) not in known:
            report.error(f"name-index.json: referencia inexistente {entry!r}")
    return document


def validate_hygiene(report: Report) -> None:
    for path in sorted(KNOWLEDGE_DIR.rglob("*")):
        if not path.is_file() or "__pycache__" in path.parts:
            continue
        if path.suffix in FORBIDDEN_SUFFIXES:
            report.error(f"Archivo potencialmente privado o crudo en knowledge/: {path.relative_to(REPO_ROOT)}")
        if path.suffix in {".json", ".md", ".py", ".txt", ".csv"}:
            text = path.read_text(encoding="utf-8", errors="replace")
            for pattern in SECRET_PATTERNS:
                if pattern.search(text):
                    report.error(
                        f"Patrón sensible en {path.relative_to(REPO_ROOT)}: {pattern.pattern}"
                    )
            if path.suffix == ".csv" and path.stat().st_size > 4096:
                report.error(f"CSV crudo de gran tamaño en knowledge/: {path.relative_to(REPO_ROOT)}")


def build_manifest(
    catalogs: dict[str, dict[str, Any]],
    fields: dict[str, Any],
    dependencies: dict[str, Any],
    sources: dict[str, Any],
    snapshots: dict[str, Any],
    translations: dict[str, Any],
) -> dict[str, Any]:
    artifacts = []
    for path in sorted(KNOWLEDGE_DIR.rglob("*")):
        if not path.is_file() or "__pycache__" in path.parts or path == MANIFEST_PATH:
            continue
        relative = path.relative_to(REPO_ROOT).as_posix()
        document = None
        if path.suffix == ".json":
            try:
                document = read_json(path)
            except ValueError:
                document = None
        count = None
        kind = path.parent.name
        if isinstance(document, dict):
            if document.get("schema") == CATALOG_SCHEMA:
                count = document.get("count")
            elif document.get("schema") == FIELDS_SCHEMA:
                count = document.get("field_count")
            elif document.get("schema") in (DEPENDENCIES_SCHEMA, SOURCES_SCHEMA):
                count = document.get("count")
        artifacts.append(
            {
                "path": relative,
                "kind": kind,
                "sha256": sha256_file(path),
                "bytes": path.stat().st_size,
                "count": count,
            }
        )
    evidence_counts = Counter(
        field.get("validation_level") for field in fields.get("fields", [])
    )
    catalog_items = sum(data.get("count", 0) for data in catalogs.values())
    return {
        "schema": MANIFEST_SCHEMA,
        "schema_version": 1,
        "knowledge_version": "7.0.0",
        "game_version": "8.8.0",
        "generated_by": "knowledge/tools/validate_knowledge.py --write-manifest",
        "source_commits": {
            "skdfe": "57b9b86335c080caca55e178c8409cb67658ccf6",
            "skdfe_8.6.0": "e088a67",
            "skdfe_8.7.0": "8cfa5d5",
        },
        "counts": {
            "catalogs": len(catalogs),
            "catalog_items": catalog_items,
            "fields": len(fields.get("fields", [])),
            "legacy_fields": sum(
                1 for field in fields.get("fields", []) if field.get("registry_tier") == "legacy"
            ),
            "declared_fields": sum(
                1 for field in fields.get("fields", []) if field.get("registry_tier") == "declared"
            ),
            "fields_by_evidence": dict(sorted(evidence_counts.items())),
            "dependencies": len(dependencies.get("dependencies", [])),
            "sources": len(sources.get("sources", [])),
            "translations": len(translations.get("entries", [])),
            "versions_analyzed": len(snapshots.get("versions", {})),
            "open_questions": sum(
                len(field.get("open_questions", [])) for field in fields.get("fields", [])
            ),
        },
        "artifacts": artifacts,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-manifest", action="store_true")
    parser.add_argument("--no-manifest-check", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    report = Report()
    catalogs = validate_catalogs(report)
    validate_catalog_relations(catalogs, report)
    fields = validate_fields(report)
    dependencies = validate_dependencies(catalogs, fields, report)
    sources = validate_sources(report)
    snapshots = validate_version_diffs(report)
    translations = validate_translations(catalogs, report)
    validate_hygiene(report)

    manifest = build_manifest(
        catalogs, fields, dependencies, sources, snapshots, translations
    )
    if args.write_manifest:
        common.write_json(MANIFEST_PATH, manifest)
        if not args.quiet:
            print(f"Manifiesto escrito: {MANIFEST_PATH.relative_to(REPO_ROOT)}")
    elif not args.no_manifest_check:
        if not MANIFEST_PATH.is_file():
            report.error("Falta knowledge/manifest.json; ejecuta --write-manifest")
        else:
            current = read_json(MANIFEST_PATH)
            if current != manifest:
                report.error(
                    "manifest.json está desactualizado; ejecuta validate_knowledge.py --write-manifest"
                )

    if not args.quiet:
        counts = manifest["counts"]
        print(
            f"Catálogos: {counts['catalogs']} ({counts['catalog_items']} elementos) | "
            f"Campos: {counts['fields']} | Dependencias: {counts['dependencies']} | "
            f"Fuentes: {counts['sources']} | Traducciones: {counts['translations']}"
        )
        print("Evidencia de campos:", json.dumps(counts["fields_by_evidence"], ensure_ascii=False))
        for warning in report.warnings:
            print(f"AVISO: {warning}")
        for error in report.errors:
            print(f"ERROR: {error}", file=sys.stderr)
    if report.errors:
        return 1
    if not args.quiet:
        print("Validación correcta.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
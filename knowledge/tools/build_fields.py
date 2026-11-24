#!/usr/bin/env python3
"""Construye el registro ampliado de campos y su proyección legacy.

El registro canónico del Save Knowledge Engine es ``knowledge/fields/fields.json``.
``docs/save-research/field-registry.json`` se conserva como proyección exacta de
los 66 campos históricos para no romper el backend ni las validaciones de fases
anteriores. La proyección se comprueba con ``--check`` y solo se reescribe con
``--write-legacy``.

Uso:
    python3 knowledge/tools/build_fields.py
    python3 knowledge/tools/build_fields.py --check
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sk_knowledge import common  # noqa: E402
from sk_knowledge.common import (  # noqa: E402
    EVIDENCE_ASPECTS,
    FIELDS_SCHEMA,
    LEGACY_FIELD_REGISTRY,
    METADATA_INVENTORY,
    SCHEMA_DIFF_860_880,
    canonical_json,
    normalize_id,
    read_json,
    write_json,
)

VERSION = "8.8.0"
OVERRIDES_PATH = common.FIELDS_DIR / "overrides.json"
FIELDS_PATH = common.FIELDS_DIR / "fields.json"

TYPE_SECTIONS = {
    "CloudSaveGameData": "cloud",
    "AboGameData": "gameData",
    "ItemData": "itemData",
    "StatisticData": "statisticData",
    "SettingData": "settingData",
    "TaskDatas": "taskData",
    "SeasonData": "seasonData",
    "MallReloadData": "mallReloadData",
    "MonsterRiseData": "monsterRiseData",
    "WeaponEvolutionData": "weaponEvolutionData",
    "MiscData": "miscData",
    "PvpData": "pvpData",
    "BattlePassSaveData": "battlePassSaveData",
    "EscapeSeasonData": "escapeSeasonData",
}

CATEGORY_NAMES = {
    "estadísticas": "Estadísticas",
    "evolución de armas": "Evolución de armas",
    "fichas de pesca": "Fichas de pesca",
    "gemas": "Gemas",
    "inventario": "Inventario",
    "pase de batalla": "Pase de batalla",
    "preferencia interna": "Preferencia interna",
    "progreso y acceso": "Progreso y acceso",
    "temporada": "Temporada",
    "vestíbulo": "Vestíbulo",
}

SECTION_FILE = {
    "cloud": "cloud",
    "gameData": "game",
    "itemData": "item_data",
    "statisticData": "statistic",
    "settingData": "setting",
    "taskData": "task",
    "seasonData": "season_data",
    "mallReloadData": "mall",
    "monsterRiseData": "monsrise_data",
    "weaponEvolutionData": "weapon_evolution_data",
    "miscData": "misc_data",
    "pvpData": "pvp_data",
    "battlePassSaveData": "bp_data",
    "escapeSeasonData": "escape_season_data",
}

HELPER_FIELDS = {"_data"}
STATIC_SUFFIX = "Load"


def section_for_type(type_name: str) -> str | None:
    if type_name in TYPE_SECTIONS:
        return TYPE_SECTIONS[type_name]
    for short_name, section in TYPE_SECTIONS.items():
        if type_name.endswith(f".{short_name}"):
            return section
    return None


def is_helper(name: str) -> bool:
    return name in HELPER_FIELDS or name.endswith(STATIC_SUFFIX)


def legacy_id(field: dict[str, Any]) -> str:
    locations = field.get("locations", {})
    cloud = locations.get("cloud") or locations.get("cloud_candidate")
    if cloud:
        return normalize_id(str(cloud))
    xml = locations.get("xml") or locations.get("xml_candidate")
    if xml:
        return f"playerprefs.{normalize_id(field['internal_name'])}"
    local = locations.get("local")
    if local:
        raw = str(local)
        raw = raw.split(":", 1)[-1]
        return normalize_id(raw)
    return normalize_id(field["internal_name"])


def raw_type_text(raw_types: list[str]) -> str:
    return ", ".join(raw_types) if raw_types else "desconocido"


def structure_for_type(type_name: str | None) -> Any:
    if not type_name:
        return None
    if type_name == "generic":
        return {"kind": "generic", "resolved": False}
    if type_name in ("szarray", "array"):
        return {"kind": "array", "resolved": False}
    if type_name in ("int", "long", "float", "double", "bool", "string", "uint", "short", "byte"):
        return {"kind": "scalar", "type": type_name}
    return {"kind": "object_or_enum", "type": type_name, "resolved": False}


def legacy_evidence(field: dict[str, Any]) -> dict[str, str]:
    overall = field.get("validation_level", "H")
    known = field.get("known_dependencies") or []
    existence = "E1" if overall == "E1" else "E2"
    data_type = "H" if overall == "E1" else "E2"
    semantics = overall if overall in ("E3", "E4") else "H"
    compatibility = "E1" if overall == "E1" else "E2"
    relations = "E2" if known else "H"
    persistence = "E4" if overall == "E4" else "H"
    result = {
        "existence": existence,
        "data_type": data_type,
        "semantics": semantics,
        "version_compatibility": compatibility,
        "relations": relations,
        "persistence": persistence,
    }
    assert set(result) == set(EVIDENCE_ASPECTS)
    return result


def apply_overrides(record: dict[str, Any], override: dict[str, Any] | None) -> None:
    if not override:
        return
    for key, value in override.items():
        if key == "evidence" and isinstance(value, dict):
            record["evidence"].update(
                {k: v for k, v in value.items() if k in EVIDENCE_ASPECTS}
            )
        else:
            record[key] = value


def build_legacy_record(field: dict[str, Any], override: dict[str, Any] | None) -> dict[str, Any]:
    raw_types = list(field.get("raw_types") or [])
    record = {
        "id": legacy_id(field),
        "internal_name": field["internal_name"],
        "category": CATEGORY_NAMES.get(field["category"], field["category"]),
        "description": None,
        "locations": dict(field.get("locations") or {}),
        "raw_types": raw_types,
        "declared_type": raw_types[0] if raw_types else None,
        "metadata_token": None,
        "type_definition": None,
        "structure": structure_for_type(raw_types[0] if raw_types else None),
        "observed_values": None,
        "known_value_semantics": [],
        "initial_values": None,
        "limits": {
            "type": raw_type_text(raw_types),
            "observed": "No cuantificado en este registro.",
            "functional": "No documentado.",
        },
        "related_ids": [],
        "associated_catalog": None,
        "sources": list(field.get("sources") or []),
        "observed_versions": list(field.get("observed_versions") or []),
        "known_dependencies": list(field.get("known_dependencies") or []),
        "pending_dependencies": list(field.get("pending_dependencies") or []),
        "preserve": [],
        "evidence": legacy_evidence(field),
        "validation_level": field.get("validation_level", "H"),
        "edit_policy": field.get("edit_policy", "solo lectura"),
        "constraints": [],
        "open_questions": [],
        "experiments_required": [],
        "registry_tier": "legacy",
        "legacy_record": field,
    }
    apply_overrides(record, override)
    return record


def observed_maps() -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    """Devuelve claves observadas 8.6 y 8.8 por sección."""
    observed_86: dict[str, set[str]] = {}
    diff = read_json(SCHEMA_DIFF_860_880)
    for section in diff.get("sections", []):
        name = section.get("file")
        if not name:
            continue
        prefix = {
            "item_data": "itemData",
            "statistic": "statisticData",
            "task": "taskData",
            "season_data": "seasonData",
            "weapon_evolution_data": "weaponEvolutionData",
            "misc_data": "miscData",
            "pvp_data": "pvpData",
            "bp_data": "battlePassSaveData",
            "monsrise_data": "monsterRiseData",
        }.get(name)
        if prefix:
            observed_86[prefix] = {str(key) for key in section.get("common", [])}
    return observed_86, {}


def declared_observed(
    section: str,
    name: str,
    observed_86: dict[str, set[str]],
    observed_88: dict[str, set[str]],
) -> tuple[bool, bool]:
    return name in observed_86.get(section, set()), name in observed_88.get(section, set())


def build_declared_record(
    section: str,
    type_name: str,
    field: dict[str, Any],
    observed_86: dict[str, set[str]],
    observed_88: dict[str, set[str]],
    overrides: dict[str, Any],
) -> dict[str, Any]:
    name = field["name"]
    field_id = f"{section}.{name}"
    seen_86, seen_88 = declared_observed(section, name, observed_86, observed_88)
    observed = seen_86 or seen_88
    declared_type = field.get("type")
    record = {
        "id": field_id,
        "internal_name": name,
        "category": overrides.get("section_titles", {}).get(section, section),
        "description": None,
        "locations": {
            "cloud": (
                f"cloudSaveGameData.{name}"
                if section == "cloud"
                else f"{section}.{name}"
            )
        },
        "raw_types": [declared_type] if declared_type else [],
        "declared_type": declared_type,
        "metadata_token": field.get("token"),
        "type_definition": type_name,
        "structure": structure_for_type(declared_type),
        "observed_values": (
            {"observed_in_versions": sorted({
                *(["8.6.0"] if seen_86 else []),
                *(["8.8.0"] if seen_88 else []),
            })}
            if observed
            else None
        ),
        "known_value_semantics": [],
        "initial_values": None,
        "limits": {
            "type": declared_type or "desconocido",
            "observed": "No cuantificado." if not observed else "Clave observada; valores no cuantificados.",
            "functional": "No documentado.",
        },
        "related_ids": [],
        "associated_catalog": None,
        "sources": ["docs/research/phase5-5/metadata-880-inventory.json"],
        "observed_versions": sorted({
            *(["8.6.0"] if seen_86 else []),
            *(["8.8.0"] if seen_88 else []),
        }),
        "known_dependencies": [],
        "pending_dependencies": [],
        "preserve": [],
        "evidence": {
            "existence": "E2" if observed else "E1",
            "data_type": "E2" if observed else "E1",
            "semantics": "H",
            "version_compatibility": "E2" if seen_86 else "H",
            "relations": "H",
            "persistence": "H",
        },
        "validation_level": "E2" if observed else "E1",
        "edit_policy": "solo lectura",
        "constraints": ["Campo declarado en metadata estática; no se ha habilitado escritura."],
        "open_questions": [
            "Confirmar estructura interna y significado funcional con una muestra propia."
        ],
        "experiments_required": [
            "Comparar dos guardados propios de la misma versión y una edición controlada con respaldo."
        ],
        "registry_tier": "declared",
        "legacy_record": None,
    }
    if seen_86:
        record["sources"].append("docs/research/phase5-5/schema-diff-860-880.json")
    apply_overrides(record, overrides.get("field_overrides", {}).get(field_id))
    return record


def merge_legacy_metadata(record: dict[str, Any], declared: dict[str, Any]) -> None:
    record["metadata_token"] = declared["metadata_token"]
    record["declared_type"] = declared["declared_type"]
    record["type_definition"] = declared["type_definition"]
    if declared["declared_type"] and declared["declared_type"] not in record["raw_types"]:
        record["raw_types"].append(declared["declared_type"])
    if declared["metadata_token"]:
        record["sources"] = sorted(set(record["sources"]) | {"docs/research/phase5-5/metadata-880-inventory.json"})
    if declared["observed_versions"]:
        record["observed_versions"] = sorted(
            set(record["observed_versions"]) | set(declared["observed_versions"])
        )
    for aspect in ("existence", "data_type", "version_compatibility"):
        if declared["evidence"][aspect] == "E2":
            current = record["evidence"].get(aspect, "H")
            if current in ("H", "E1"):
                record["evidence"][aspect] = "E2"


def build_fields() -> dict[str, Any]:
    legacy = read_json(LEGACY_FIELD_REGISTRY)
    inventory = read_json(METADATA_INVENTORY)
    overrides = read_json(OVERRIDES_PATH)
    observed_86, observed_88 = observed_maps()
    observed_88["gameData"] = set(overrides.get("observed_game_data_keys", []))

    fields: list[dict[str, Any]] = []
    legacy_by_id: dict[str, dict[str, Any]] = {}
    for raw_field in legacy.get("fields", []):
        record = build_legacy_record(
            raw_field, overrides.get("field_overrides", {}).get(legacy_id(raw_field))
        )
        if record["id"] in legacy_by_id:
            raise ValueError(f"Id legacy duplicado: {record['id']}")
        legacy_by_id[record["id"]] = record
        fields.append(record)

    declared_new: list[dict[str, Any]] = []
    declared_by_id: dict[str, dict[str, Any]] = {}
    for type_info in inventory.get("types", []):
        type_name = type_info.get("name", "")
        section = section_for_type(type_name)
        if not section:
            continue
        for field in type_info.get("fields", []):
            name = str(field.get("name", ""))
            if not name or is_helper(name):
                continue
            record = build_declared_record(
                section,
                type_name,
                field,
                observed_86,
                observed_88,
                overrides,
            )
            if record["id"] in declared_by_id:
                raise ValueError(f"Id declarado duplicado: {record['id']}")
            declared_by_id[record["id"]] = record
            if record["id"] in legacy_by_id:
                merge_legacy_metadata(legacy_by_id[record["id"]], record)
            else:
                declared_new.append(record)

    declared_new.sort(key=lambda record: record["id"])
    fields.extend(declared_new)

    counts_by_level: dict[str, int] = {level: 0 for level in common.EVIDENCE_LEVELS}
    for record in fields:
        counts_by_level[record["validation_level"]] = counts_by_level.get(record["validation_level"], 0) + 1

    return {
        "schema": FIELDS_SCHEMA,
        "schema_version": 1,
        "game_version": VERSION,
        "generated_by": "knowledge/tools/build_fields.py",
        "notes": [
            "knowledge/fields/fields.json es la fuente canónica ampliada.",
            "docs/save-research/field-registry.json es una proyección exacta de los 66 campos legacy.",
            "Los campos declarados solo por metadata no prueban que una partida real los use.",
            "Los niveles de evidencia se declaran por aspecto y no se elevan sin un experimento.",
        ],
        "evidence_levels": legacy.get("evidence_levels", {}),
        "evidence_aspects": list(EVIDENCE_ASPECTS),
        "field_count": len(fields),
        "counts_by_validation_level": counts_by_level,
        "fields": fields,
    }


def projection(document: dict[str, Any]) -> dict[str, Any]:
    legacy = read_json(LEGACY_FIELD_REGISTRY)
    return {
        "schema_version": legacy["schema_version"],
        "evidence_levels": legacy["evidence_levels"],
        "source_index": legacy["source_index"],
        "fields": [
            record["legacy_record"]
            for record in document["fields"]
            if record.get("registry_tier") == "legacy" and record.get("legacy_record")
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Comprueba la proyección legacy sin escribirla.")
    parser.add_argument("--write-legacy", action="store_true", help="Reescribe la proyección legacy.")
    args = parser.parse_args(argv)

    document = build_fields()
    write_json(FIELDS_PATH, document)
    print(
        f"ESCRITO {FIELDS_PATH.relative_to(common.REPO_ROOT)}: "
        f"{document['field_count']} campos"
    )
    print("Por nivel:", ", ".join(f"{k}={v}" for k, v in document["counts_by_validation_level"].items()))

    expected = canonical_json(projection(document))
    current = LEGACY_FIELD_REGISTRY.read_text(encoding="utf-8")
    if expected != current:
        print("La proyección legacy NO coincide con docs/save-research/field-registry.json")
        if args.write_legacy:
            LEGACY_FIELD_REGISTRY.write_text(expected, encoding="utf-8", newline="\n")
            print("Proyección legacy reescrita.")
        elif args.check:
            return 1
        else:
            print("Usa --write-legacy solo si el cambio está revisado.")
    else:
        print("Proyección legacy idéntica.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
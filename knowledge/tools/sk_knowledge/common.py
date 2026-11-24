"""Rutas, serialización canónica y validación básica de esquemas."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Iterable, Mapping

PACKAGE_DIR = Path(__file__).resolve().parent
TOOLS_DIR = PACKAGE_DIR.parent
KNOWLEDGE_DIR = TOOLS_DIR.parent
REPO_ROOT = KNOWLEDGE_DIR.parent

SCHEMAS_DIR = KNOWLEDGE_DIR / "schemas"
CATALOGS_DIR = KNOWLEDGE_DIR / "catalogs"
FIELDS_DIR = KNOWLEDGE_DIR / "fields"
DEPENDENCIES_DIR = KNOWLEDGE_DIR / "dependencies"
TRANSLATIONS_DIR = KNOWLEDGE_DIR / "translations"
VERSION_DIFFS_DIR = KNOWLEDGE_DIR / "version-diffs"
EVIDENCE_DIR = KNOWLEDGE_DIR / "evidence"
SOURCES_DIR = KNOWLEDGE_DIR / "sources"
REPORTS_DIR = KNOWLEDGE_DIR / "reports"
MANIFEST_PATH = KNOWLEDGE_DIR / "manifest.json"

LEGACY_FIELD_REGISTRY = REPO_ROOT / "docs" / "save-research" / "field-registry.json"
BACKEND_CHARACTER_CATALOG = REPO_ROOT / "backend" / "app" / "catalogs" / "characters-880.json"
METADATA_INVENTORY = REPO_ROOT / "docs" / "research" / "phase5-5" / "metadata-880-inventory.json"
SCHEMA_DIFF_860_880 = REPO_ROOT / "docs" / "research" / "phase5-5" / "schema-diff-860-880.json"

CATALOG_SCHEMA = "sk-knowledge/catalog@1"
FIELDS_SCHEMA = "sk-knowledge/fields@1"
DEPENDENCIES_SCHEMA = "sk-knowledge/dependencies@1"
MANIFEST_SCHEMA = "sk-knowledge/manifest@1"
SOURCES_SCHEMA = "sk-knowledge/sources@1"
DIFF_SCHEMA = "sk-knowledge/version-diff@1"

EVIDENCE_LEVELS = ("H", "E1", "E2", "E3", "E4")
EVIDENCE_ASPECTS = (
    "existence",
    "data_type",
    "semantics",
    "version_compatibility",
    "relations",
    "persistence",
)

_ID_RE = re.compile(r"[^A-Za-z0-9_.:/{}+\-]+")
_SPACE_RE = re.compile(r"\s+")


def repo_path(*parts: str) -> Path:
    return REPO_ROOT.joinpath(*parts)


def canonical_json(value: Any) -> str:
    """Serialización determinista usada por todos los artefactos."""
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(canonical_json(value), encoding="utf-8", newline="\n")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def normalize_id(value: str) -> str:
    """Normaliza un identificador sin inventar nombres ni perder el ámbito."""
    text = _SPACE_RE.sub("_", value.strip())
    text = text.replace("[]", ".*")
    text = re.sub(r"\{[^}]+\}", "*", text)
    text = text.replace("**", "*")
    text = _ID_RE.sub("_", text)
    return text.strip("_") or "unnamed"


def normalize_lookup(value: str) -> str:
    """Clave de búsqueda tolerante a mayúsculas, espacios y separadores."""
    return _SPACE_RE.sub(" ", value.casefold().replace("_", " ").replace("-", " ")).strip()


def stringify_name(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def merge_translations(
    en: str | None, es: str | None, zh_cn: str | None = None
) -> dict[str, str | None]:
    return {"en": en or None, "es": es or None, "zh_cn": zh_cn or None}


def source_ref(commit: str, path: str, detail: str | None = None) -> dict[str, str]:
    ref = {"commit": commit, "path": path}
    if detail:
        ref["detail"] = detail
    return ref


def catalog_document(
    family: str,
    title: str,
    version: str,
    source_refs: Iterable[Mapping[str, Any] | str],
    items: list[dict[str, Any]],
    *,
    description: str | None = None,
    license_note: str | None = None,
) -> dict[str, Any]:
    refs = [dict(ref) if isinstance(ref, Mapping) else str(ref) for ref in source_refs]
    return {
        "schema": CATALOG_SCHEMA,
        "family": family,
        "title": title,
        "description": description,
        "game_version": version,
        "generated_by": "knowledge/tools/build_catalog.py",
        "source_refs": refs,
        "license_note": license_note,
        "count": len(items),
        "items": sorted(items, key=lambda item: str(item.get("id", ""))),
    }


def ensure_unique_ids(items: Iterable[Mapping[str, Any]], label: str) -> None:
    seen: set[str] = set()
    for item in items:
        item_id = str(item.get("id", ""))
        if not item_id:
            raise ValueError(f"{label}: elemento sin id")
        if item_id in seen:
            raise ValueError(f"{label}: id duplicado {item_id!r}")
        seen.add(item_id)


def _type_matches(value: Any, expected: str) -> bool:
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "null":
        return value is None
    return True


def validate_schema(value: Any, schema: Mapping[str, Any], path: str = "$") -> list[str]:
    """Validador del subconjunto de JSON Schema usado por ``knowledge/schemas``.

    Admite type, required, properties, additionalProperties, items, enum,
    pattern, minimum, minItems y minLength. No pretende ser un validador
    completo: las reglas semánticas viven en ``validate_knowledge.py``.
    """
    errors: list[str] = []
    expected = schema.get("type")
    if isinstance(expected, str) and not _type_matches(value, expected):
        return [f"{path}: se esperaba {expected} y llegó {type(value).__name__}"]
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: valor {value!r} fuera del enum permitido")
    if isinstance(value, str):
        pattern = schema.get("pattern")
        if isinstance(pattern, str) and re.fullmatch(pattern, value) is None:
            errors.append(f"{path}: {value!r} no cumple el patrón {pattern}")
        min_length = schema.get("minLength")
        if isinstance(min_length, int) and len(value) < min_length:
            errors.append(f"{path}: longitud menor que {min_length}")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        minimum = schema.get("minimum")
        if isinstance(minimum, (int, float)) and value < minimum:
            errors.append(f"{path}: valor menor que {minimum}")
    if isinstance(value, dict):
        required = schema.get("required", [])
        if isinstance(required, list):
            for key in required:
                if key not in value:
                    errors.append(f"{path}: falta la clave obligatoria {key!r}")
        properties = schema.get("properties", {})
        if isinstance(properties, dict):
            for key, child in properties.items():
                if key in value and isinstance(child, dict):
                    errors.extend(validate_schema(value[key], child, f"{path}.{key}"))
            if schema.get("additionalProperties") is False:
                for key in value:
                    if key not in properties:
                        errors.append(f"{path}: clave no permitida {key!r}")
    if isinstance(value, list):
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(value):
                errors.extend(validate_schema(item, item_schema, f"{path}[{index}]"))
        min_items = schema.get("minItems")
        if isinstance(min_items, int) and len(value) < min_items:
            errors.append(f"{path}: se esperaban al menos {min_items} elementos")
    return errors


def load_schema(name: str) -> dict[str, Any]:
    return read_json(SCHEMAS_DIR / name)
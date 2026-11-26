"""Proyección empaquetada del catálogo de planos (8.8.0).

El archivo ``blueprints-880.json`` se genera desde ``knowledge/catalogs`` con
``knowledge/tools/build_backend_blueprints.py``. El backend no mantiene listas
ni nombres paralelos: solo lee esta proyección, validada durante la construcción
de la imagen y comparada contra el catálogo en las pruebas.
"""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping

BLUEPRINTS_PATH = Path(__file__).resolve().parent / "blueprints-880.json"
EXPECTED_VERSION = "8.8.0"
EXPECTED_BLUEPRINTS = 265
EXPECTED_SCHEMA = "sk-under/backend-blueprints@1"
MAX_TEXT = 120

logger = logging.getLogger(__name__)
_last_failure: str | None = None


class BlueprintCatalogError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _safe_text(value: object, limit: int = MAX_TEXT) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.replace("\x00", "")
    text = "".join(char for char in text if char.isprintable()).strip()
    if not text:
        return None
    return text if len(text) <= limit else text[:limit] + "…"


def _empty_catalog(error: str) -> dict[str, object]:
    return {
        "available": False,
        "error": error,
        "version": None,
        "counts": {"blueprints": 0},
        "blueprint_ids": frozenset(),
        "blueprints": {},
        "ordered_blueprints": [],
    }


def _read_document(path: Path) -> Mapping[str, Any]:
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise BlueprintCatalogError(
            "blueprint_catalog_missing", f"No se encontró el catálogo de planos en {path}."
        ) from None
    except OSError as exc:
        raise BlueprintCatalogError(
            "blueprint_catalog_unreadable",
            f"No se pudo leer el catálogo de planos en {path} ({type(exc).__name__}).",
        ) from None
    try:
        document = json.loads(raw)
    except ValueError:
        raise BlueprintCatalogError(
            "blueprint_catalog_invalid_json",
            "El catálogo de planos no contiene JSON válido.",
        ) from None
    if not isinstance(document, dict):
        raise BlueprintCatalogError(
            "blueprint_catalog_invalid_structure", "El catálogo de planos debe ser un objeto JSON."
        )
    return document


def _parse_materials(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    result: list[dict[str, object]] = []
    for row in value:
        if not isinstance(row, dict):
            continue
        item_id = _safe_text(row.get("item"))
        num = row.get("num")
        if item_id is not None and type(num) is int and num >= 0:
            result.append({"item": item_id, "num": num})
    return result


def _parse_catalog(document: Mapping[str, Any]) -> dict[str, object]:
    if document.get("schema") != EXPECTED_SCHEMA:
        raise BlueprintCatalogError(
            "blueprint_catalog_invalid_structure", "El catálogo de planos declara un esquema inesperado."
        )
    if document.get("game_version") != EXPECTED_VERSION:
        raise BlueprintCatalogError(
            "blueprint_catalog_unexpected_version", "El catálogo de planos no es de la versión 8.8.0."
        )
    if document.get("counts") != {"blueprints": EXPECTED_BLUEPRINTS}:
        raise BlueprintCatalogError(
            "blueprint_catalog_unexpected_size", "Los recuentos del catálogo de planos no coinciden."
        )
    rows = document.get("blueprints")
    if not isinstance(rows, list) or len(rows) != EXPECTED_BLUEPRINTS:
        raise BlueprintCatalogError(
            "blueprint_catalog_unexpected_size", "El catálogo de planos no contiene sus 265 filas."
        )
    by_id: dict[str, dict[str, object]] = {}
    ordered: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            raise BlueprintCatalogError(
                "blueprint_catalog_invalid_structure", "El catálogo de planos contiene una fila inválida."
            )
        blueprint_id = row.get("id")
        if (
            not isinstance(blueprint_id, str)
            or not blueprint_id.startswith("blueprint_")
            or len(blueprint_id) > 120
        ):
            raise BlueprintCatalogError(
                "blueprint_catalog_invalid_structure", "Un plano declara un identificador inválido."
            )
        if blueprint_id in by_id:
            raise BlueprintCatalogError(
                "blueprint_catalog_duplicate_id", f"El catálogo repite el plano {blueprint_id}."
            )
        name = row.get("name")
        if not isinstance(name, dict):
            raise BlueprintCatalogError(
                "blueprint_catalog_invalid_structure", f"{blueprint_id} no declara nombres."
            )
        blueprint_type = row.get("blueprint_type")
        if blueprint_type is not None and type(blueprint_type) is not int:
            raise BlueprintCatalogError(
                "blueprint_catalog_invalid_structure", f"{blueprint_id} declara un tipo inválido."
            )
        by_id[blueprint_id] = {
            "id": blueprint_id,
            "name": {"en": _safe_text(name.get("en")), "es": _safe_text(name.get("es"))},
            "subcategory": _safe_text(row.get("subcategory")),
            "blueprint_type": blueprint_type,
            "target": _safe_text(row.get("target")),
            "research_materials": _parse_materials(row.get("research_materials")),
        }
        ordered.append(blueprint_id)
    return {
        "available": True,
        "error": None,
        "version": EXPECTED_VERSION,
        "counts": {"blueprints": len(by_id)},
        "blueprint_ids": frozenset(by_id),
        "blueprints": by_id,
        "ordered_blueprints": ordered,
    }


@lru_cache(maxsize=4)
def _load_cached(path: str) -> dict[str, object]:
    return _parse_catalog(_read_document(Path(path)))


def load_blueprint_catalog(path: Path | None = None) -> dict[str, object]:
    global _last_failure
    source = Path(path) if path is not None else BLUEPRINTS_PATH
    try:
        catalog = _load_cached(str(source))
    except BlueprintCatalogError as exc:
        signature = f"{source}:{exc.code}"
        if signature != _last_failure:
            logger.error("Blueprint catalog unavailable at %s (%s): %s", source, exc.code, exc)
            _last_failure = signature
        return _empty_catalog(exc.code)
    _last_failure = None
    return catalog


def clear_blueprint_catalog_cache() -> None:
    _load_cached.cache_clear()


def validate_blueprint_catalog(catalog: Mapping[str, object] | None = None) -> None:
    current = catalog if catalog is not None else load_blueprint_catalog()
    if not current.get("available"):
        raise BlueprintCatalogError(
            str(current.get("error") or "blueprint_catalog_unavailable"),
            "El catálogo de planos no está disponible.",
        )
    if current.get("version") != EXPECTED_VERSION:
        raise BlueprintCatalogError(
            "blueprint_catalog_unexpected_version", "Versión inesperada del catálogo de planos."
        )
    if current.get("counts") != {"blueprints": EXPECTED_BLUEPRINTS}:
        raise BlueprintCatalogError(
            "blueprint_catalog_unexpected_size", "Recuento inesperado del catálogo de planos."
        )
"""Proyección empaquetada de materiales y semillas editables (8.8.0).

El archivo ``items-880.json`` se genera desde ``knowledge/catalogs`` con
``knowledge/tools/build_backend_items.py``. El backend no mantiene nombres ni
listas paralelas: solo lee esta proyección, validada en la construcción de la
imagen y comparada contra los catálogos en las pruebas.
"""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping

ITEMS_PATH = Path(__file__).resolve().parent / "items-880.json"
EXPECTED_VERSION = "8.8.0"
EXPECTED_MATERIALS = 343
EXPECTED_SEEDS = 47
EXPECTED_SCHEMA = "sk-under/backend-items@1"
MAX_TEXT = 120

logger = logging.getLogger(__name__)
_last_failure: str | None = None


class ItemCatalogError(RuntimeError):
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
        "counts": {"materials": 0, "seeds": 0},
        "material_ids": frozenset(),
        "seed_ids": frozenset(),
        "materials": {},
        "seeds": {},
        "ordered_materials": [],
        "ordered_seeds": [],
    }


def _read_document(path: Path) -> Mapping[str, Any]:
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise ItemCatalogError("item_catalog_missing", f"No se encontró el catálogo de objetos en {path}.") from None
    except OSError as exc:
        raise ItemCatalogError(
            "item_catalog_unreadable",
            f"No se pudo leer el catálogo de objetos en {path} ({type(exc).__name__}).",
        ) from None
    try:
        document = json.loads(raw)
    except ValueError:
        raise ItemCatalogError("item_catalog_invalid_json", "El catálogo de objetos no contiene JSON válido.") from None
    if not isinstance(document, dict):
        raise ItemCatalogError("item_catalog_invalid_structure", "El catálogo de objetos debe ser un objeto JSON.")
    return document


def _parse_rows(document: Mapping[str, Any], key: str, expected: int) -> tuple[dict[str, dict[str, object]], list[str]]:
    rows = document.get(key)
    if not isinstance(rows, list) or len(rows) != expected:
        raise ItemCatalogError(
            "item_catalog_unexpected_size",
            f"Se esperaban {expected} elementos en {key}.",
        )
    by_id: dict[str, dict[str, object]] = {}
    ordered: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            raise ItemCatalogError("item_catalog_invalid_structure", f"{key} contiene una fila que no es un objeto.")
        item_id = row.get("id")
        if not isinstance(item_id, str) or not item_id or len(item_id) > 80:
            raise ItemCatalogError("item_catalog_invalid_structure", f"{key} contiene un identificador inválido.")
        if item_id in by_id:
            raise ItemCatalogError("item_catalog_duplicate_id", f"{key} repite el identificador {item_id}.")
        name = row.get("name")
        if not isinstance(name, dict):
            raise ItemCatalogError("item_catalog_invalid_structure", f"{item_id} no declara nombres.")
        editable = row.get("editable")
        insertable = row.get("insertable")
        if type(editable) is not bool or type(insertable) is not bool:
            raise ItemCatalogError("item_catalog_invalid_structure", f"{item_id} no declara políticas válidas.")
        subcategory = row.get("subcategory")
        if subcategory is not None and not isinstance(subcategory, str):
            raise ItemCatalogError("item_catalog_invalid_structure", f"{item_id} declara una categoría inválida.")
        reason = _safe_text(row.get("reason"))
        by_id[item_id] = {
            "id": item_id,
            "name": {"en": _safe_text(name.get("en")), "es": _safe_text(name.get("es"))},
            "subcategory": _safe_text(subcategory),
            "editable": editable,
            "insertable": insertable,
            "reason": reason,
        }
        ordered.append(item_id)
    return by_id, ordered


def _parse_catalog(document: Mapping[str, Any]) -> dict[str, object]:
    if document.get("schema") != EXPECTED_SCHEMA:
        raise ItemCatalogError("item_catalog_invalid_structure", "El catálogo de objetos declara un esquema inesperado.")
    if document.get("game_version") != EXPECTED_VERSION:
        raise ItemCatalogError("item_catalog_unexpected_version", "El catálogo de objetos no es de la versión 8.8.0.")
    counts = document.get("counts")
    if counts != {"materials": EXPECTED_MATERIALS, "seeds": EXPECTED_SEEDS}:
        raise ItemCatalogError("item_catalog_unexpected_size", "Los recuentos del catálogo de objetos no coinciden.")
    materials, ordered_materials = _parse_rows(document, "materials", EXPECTED_MATERIALS)
    seeds, ordered_seeds = _parse_rows(document, "seeds", EXPECTED_SEEDS)
    fish = materials.get("material_fish")
    if not fish or fish.get("editable") is not False or fish.get("insertable") is not False:
        raise ItemCatalogError(
            "item_catalog_invalid_structure",
            "material_fish debe estar presente y no ser editable (espejo de gameData.fishChip).",
        )
    return {
        "available": True,
        "error": None,
        "version": EXPECTED_VERSION,
        "counts": {"materials": len(materials), "seeds": len(seeds)},
        "material_ids": frozenset(materials),
        "seed_ids": frozenset(seeds),
        "materials": materials,
        "seeds": seeds,
        "ordered_materials": ordered_materials,
        "ordered_seeds": ordered_seeds,
    }


@lru_cache(maxsize=4)
def _load_cached(path: str) -> dict[str, object]:
    return _parse_catalog(_read_document(Path(path)))


def load_item_catalog(path: Path | None = None) -> dict[str, object]:
    global _last_failure
    source = Path(path) if path is not None else ITEMS_PATH
    try:
        catalog = _load_cached(str(source))
    except ItemCatalogError as exc:
        signature = f"{source}:{exc.code}"
        if signature != _last_failure:
            logger.error("Item catalog unavailable at %s (%s): %s", source, exc.code, exc)
            _last_failure = signature
        return _empty_catalog(exc.code)
    _last_failure = None
    return catalog


def clear_item_catalog_cache() -> None:
    _load_cached.cache_clear()


def validate_item_catalog(catalog: Mapping[str, object] | None = None) -> None:
    current = catalog if catalog is not None else load_item_catalog()
    if not current.get("available"):
        raise ItemCatalogError(
            str(current.get("error") or "item_catalog_unavailable"),
            "El catálogo de materiales y semillas no está disponible.",
        )
    if current.get("version") != EXPECTED_VERSION:
        raise ItemCatalogError("item_catalog_unexpected_version", "Versión inesperada del catálogo de objetos.")
    if current.get("counts") != {"materials": EXPECTED_MATERIALS, "seeds": EXPECTED_SEEDS}:
        raise ItemCatalogError("item_catalog_unexpected_size", "Recuento inesperado del catálogo de objetos.")
    materials = current.get("materials")
    seeds = current.get("seeds")
    if not isinstance(materials, dict) or not isinstance(seeds, dict):
        raise ItemCatalogError("item_catalog_invalid_structure", "El catálogo de objetos no expone sus mapas.")
    if "material_fish" not in materials:
        raise ItemCatalogError("item_catalog_unexpected_content", "Falta material_fish en el catálogo.")
    if not any(item_id.startswith("plant_") and item_id.endswith("_seed") for item_id in seeds):
        raise ItemCatalogError("item_catalog_unexpected_content", "No hay semillas válidas en el catálogo.")

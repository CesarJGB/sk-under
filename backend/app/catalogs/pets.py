"""Proyección empaquetada de mascotas y sus variantes (8.8.0).

El archivo ``pets-880.json`` se genera desde ``knowledge/catalogs`` con
``knowledge/tools/build_backend_pets.py``. El backend no mantiene listas ni
nombres paralelos: solo lee esta proyección, validada en las pruebas.
"""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping

PETS_PATH = Path(__file__).resolve().parent / "pets-880.json"
EXPECTED_VERSION = "8.8.0"
EXPECTED_PETS = 58
EXPECTED_SKINS = 12
EXPECTED_SCHEMA = "sk-under/backend-pets@1"
MAX_TEXT = 120

logger = logging.getLogger(__name__)
_last_failure: str | None = None


class PetCatalogError(RuntimeError):
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
        "counts": {"pets": 0, "pet_skins": 0},
        "pet_ids": frozenset(),
        "skin_ids": frozenset(),
        "pets": {},
        "pet_skins": {},
        "ordered_pets": [],
        "ordered_skins": [],
    }


def _read_document(path: Path) -> Mapping[str, Any]:
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise PetCatalogError("pet_catalog_missing", f"No se encontró el catálogo de mascotas en {path}.") from None
    except OSError as exc:
        raise PetCatalogError(
            "pet_catalog_unreadable",
            f"No se pudo leer el catálogo de mascotas en {path} ({type(exc).__name__}).",
        ) from None
    try:
        document = json.loads(raw)
    except ValueError:
        raise PetCatalogError("pet_catalog_invalid_json", "El catálogo de mascotas no contiene JSON válido.") from None
    if not isinstance(document, dict):
        raise PetCatalogError("pet_catalog_invalid_structure", "El catálogo de mascotas debe ser un objeto JSON.")
    return document


def _parse_pet(row: object) -> dict[str, object]:
    if not isinstance(row, dict):
        raise PetCatalogError("pet_catalog_invalid_structure", "La lista de mascotas contiene una fila inválida.")
    pet_id = row.get("id")
    if not isinstance(pet_id, str) or not pet_id or len(pet_id) > 80:
        raise PetCatalogError("pet_catalog_invalid_structure", "Una mascota declara un identificador inválido.")
    numeric_id = row.get("numeric_id")
    if type(numeric_id) is not int or numeric_id < 0:
        raise PetCatalogError("pet_catalog_invalid_structure", f"{pet_id} declara un numeric_id inválido.")
    name = row.get("name")
    if not isinstance(name, dict):
        raise PetCatalogError("pet_catalog_invalid_structure", f"{pet_id} no declara nombres.")
    save_ref = row.get("save_ref")
    if save_ref is not None and not isinstance(save_ref, str):
        raise PetCatalogError("pet_catalog_invalid_structure", f"{pet_id} declara una ruta inválida.")
    return {
        "id": pet_id,
        "numeric_id": numeric_id,
        "name": {"en": _safe_text(name.get("en")), "es": _safe_text(name.get("es"))},
        "save_ref": _safe_text(save_ref),
    }


def _parse_skin(row: object) -> dict[str, object]:
    if not isinstance(row, dict):
        raise PetCatalogError("pet_catalog_invalid_structure", "La lista de skins contiene una fila inválida.")
    skin_id = row.get("id")
    pet_code = row.get("pet_code")
    base_pet = row.get("base_pet")
    skin_index = row.get("skin_index")
    if not isinstance(skin_id, str) or not skin_id or len(skin_id) > 80:
        raise PetCatalogError("pet_catalog_invalid_structure", "Una skin declara un identificador inválido.")
    if not isinstance(pet_code, str) or not isinstance(base_pet, str):
        raise PetCatalogError("pet_catalog_invalid_structure", f"{skin_id} no declara su mascota.")
    if type(skin_index) is not int or skin_index < 0:
        raise PetCatalogError("pet_catalog_invalid_structure", f"{skin_id} declara un índice inválido.")
    name = row.get("name")
    if not isinstance(name, dict):
        raise PetCatalogError("pet_catalog_invalid_structure", f"{skin_id} no declara nombres.")
    save_ref = row.get("save_ref")
    if save_ref is not None and not isinstance(save_ref, str):
        raise PetCatalogError("pet_catalog_invalid_structure", f"{skin_id} declara una ruta inválida.")
    return {
        "id": skin_id,
        "pet_code": pet_code,
        "base_pet": base_pet,
        "skin_index": skin_index,
        "name": {"en": _safe_text(name.get("en")), "es": _safe_text(name.get("es"))},
        "save_ref": _safe_text(save_ref),
    }


def _parse_catalog(document: Mapping[str, Any]) -> dict[str, object]:
    if document.get("schema") != EXPECTED_SCHEMA:
        raise PetCatalogError("pet_catalog_invalid_structure", "El catálogo de mascotas declara un esquema inesperado.")
    if document.get("game_version") != EXPECTED_VERSION:
        raise PetCatalogError("pet_catalog_unexpected_version", "El catálogo de mascotas no es de la versión 8.8.0.")
    counts = document.get("counts")
    if counts != {"pets": EXPECTED_PETS, "pet_skins": EXPECTED_SKINS}:
        raise PetCatalogError("pet_catalog_unexpected_size", "Los recuentos del catálogo de mascotas no coinciden.")
    pet_rows = document.get("pets")
    skin_rows = document.get("pet_skins")
    if not isinstance(pet_rows, list) or not isinstance(skin_rows, list):
        raise PetCatalogError("pet_catalog_invalid_structure", "El catálogo de mascotas no contiene sus listas.")
    pets: dict[str, dict[str, object]] = {}
    ordered_pets: list[str] = []
    for row in pet_rows:
        pet = _parse_pet(row)
        pet_id = str(pet["id"])
        if pet_id in pets:
            raise PetCatalogError("pet_catalog_duplicate_id", f"El catálogo repite la mascota {pet_id}.")
        pets[pet_id] = pet
        ordered_pets.append(pet_id)
    skins: dict[str, dict[str, object]] = {}
    ordered_skins: list[str] = []
    for row in skin_rows:
        skin = _parse_skin(row)
        skin_id = str(skin["id"])
        if skin_id in skins:
            raise PetCatalogError("pet_catalog_duplicate_id", f"El catálogo repite la skin {skin_id}.")
        if skin["pet_code"] not in pets:
            raise PetCatalogError("pet_catalog_invalid_structure", f"La skin {skin_id} apunta a una mascota ausente.")
        if skin["base_pet"] not in pets:
            raise PetCatalogError("pet_catalog_invalid_structure", f"La skin {skin_id} apunta a una mascota base ausente.")
        skins[skin_id] = skin
        ordered_skins.append(skin_id)
    if len(pets) != EXPECTED_PETS or len(skins) != EXPECTED_SKINS:
        raise PetCatalogError("pet_catalog_unexpected_size", "Los recuentos del catálogo de mascotas no coinciden.")
    return {
        "available": True,
        "error": None,
        "version": EXPECTED_VERSION,
        "counts": {"pets": len(pets), "pet_skins": len(skins)},
        "pet_ids": frozenset(pets),
        "skin_ids": frozenset(skins),
        "pets": pets,
        "pet_skins": skins,
        "ordered_pets": ordered_pets,
        "ordered_skins": ordered_skins,
    }


@lru_cache(maxsize=4)
def _load_cached(path: str) -> dict[str, object]:
    return _parse_catalog(_read_document(Path(path)))


def load_pet_catalog(path: Path | None = None) -> dict[str, object]:
    global _last_failure
    source = Path(path) if path is not None else PETS_PATH
    try:
        catalog = _load_cached(str(source))
    except PetCatalogError as exc:
        signature = f"{source}:{exc.code}"
        if signature != _last_failure:
            logger.error("Pet catalog unavailable at %s (%s): %s", source, exc.code, exc)
            _last_failure = signature
        return _empty_catalog(exc.code)
    _last_failure = None
    return catalog


def clear_pet_catalog_cache() -> None:
    _load_cached.cache_clear()


def validate_pet_catalog(catalog: Mapping[str, object] | None = None) -> None:
    current = catalog if catalog is not None else load_pet_catalog()
    if not current.get("available"):
        raise PetCatalogError(
            str(current.get("error") or "pet_catalog_unavailable"),
            "El catálogo de mascotas no está disponible.",
        )
    if current.get("version") != EXPECTED_VERSION:
        raise PetCatalogError("pet_catalog_unexpected_version", "Versión inesperada del catálogo de mascotas.")
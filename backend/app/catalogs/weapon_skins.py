"""Proyección empaquetada de skins de arma (8.8.0).

El archivo ``weapon-skins-880.json`` se genera desde ``knowledge/catalogs`` con
``knowledge/tools/build_backend_customization.py``. Solo contiene la relación
factual entre arma, índice y nombre; la disponibilidad se decide con la partida.
"""

from __future__ import annotations

import json
import logging
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping

WEAPON_SKINS_PATH = Path(__file__).resolve().parent / "weapon-skins-880.json"
from .version import CATALOG_VERSION

EXPECTED_VERSION = CATALOG_VERSION
EXPECTED_SKINS = 192
EXPECTED_WEAPONS = 180
EXPECTED_SCHEMA = "sk-under/backend-weapon-skins@1"
MAX_TEXT = 120
WEAPON_SKIN_ID = re.compile(r"^weapon_[a-z0-9_]+_s_[1-9][0-9]*$")
WEAPON_ID = re.compile(r"^weapon_[a-z0-9_]+$")

logger = logging.getLogger(__name__)
_last_failure: str | None = None


class WeaponSkinCatalogError(RuntimeError):
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
        "counts": {"skins": 0, "weapons": 0},
        "skin_ids": frozenset(),
        "skins": {},
        "ordered_skins": [],
        "weapon_ids": frozenset(),
        "weapon_skins": {},
        "weapons": {},
    }


def _read_document(path: Path) -> Mapping[str, Any]:
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise WeaponSkinCatalogError(
            "weapon_skin_catalog_missing",
            f"No se encontró el catálogo de skins de arma en {path}.",
        ) from None
    except OSError as exc:
        raise WeaponSkinCatalogError(
            "weapon_skin_catalog_unreadable",
            f"No se pudo leer el catálogo de skins de arma en {path} ({type(exc).__name__}).",
        ) from None
    try:
        document = json.loads(raw)
    except ValueError:
        raise WeaponSkinCatalogError(
            "weapon_skin_catalog_invalid_json",
            "El catálogo de skins de arma no contiene JSON válido.",
        ) from None
    if not isinstance(document, dict):
        raise WeaponSkinCatalogError(
            "weapon_skin_catalog_invalid_structure",
            "El catálogo de skins de arma debe ser un objeto JSON.",
        )
    return document


def _parse_names(value: object, skin_id: str) -> dict[str, str | None]:
    if not isinstance(value, dict):
        raise WeaponSkinCatalogError(
            "weapon_skin_catalog_invalid_structure", f"{skin_id} no declara nombres."
        )
    return {"en": _safe_text(value.get("en")), "es": _safe_text(value.get("es"))}


def _parse_catalog(document: Mapping[str, Any]) -> dict[str, object]:
    if document.get("schema") != EXPECTED_SCHEMA:
        raise WeaponSkinCatalogError(
            "weapon_skin_catalog_invalid_structure",
            "El catálogo de skins de arma declara un esquema inesperado.",
        )
    if document.get("game_version") != EXPECTED_VERSION:
        raise WeaponSkinCatalogError(
            "weapon_skin_catalog_unexpected_version",
            "El catálogo de skins de arma no es de la versión 8.8.0.",
        )
    if document.get("counts") != {"skins": EXPECTED_SKINS, "weapons": EXPECTED_WEAPONS}:
        raise WeaponSkinCatalogError(
            "weapon_skin_catalog_unexpected_size",
            "Los recuentos del catálogo de skins de arma no coinciden.",
        )
    rows = document.get("weapon_skins")
    if not isinstance(rows, list) or len(rows) != EXPECTED_SKINS:
        raise WeaponSkinCatalogError(
            "weapon_skin_catalog_unexpected_size",
            "El catálogo de skins de arma no contiene sus 192 filas.",
        )
    by_id: dict[str, dict[str, object]] = {}
    ordered: list[str] = []
    by_weapon: dict[str, list[str]] = {}
    weapons: dict[str, dict[str, object]] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise WeaponSkinCatalogError(
                "weapon_skin_catalog_invalid_structure",
                "El catálogo de skins de arma contiene una fila inválida.",
            )
        skin_id = row.get("id")
        weapon_id = row.get("weapon_id")
        skin_index = row.get("skin_index")
        if not isinstance(skin_id, str) or not WEAPON_SKIN_ID.fullmatch(skin_id):
            raise WeaponSkinCatalogError(
                "weapon_skin_catalog_invalid_structure",
                "Una skin de arma declara un identificador inválido.",
            )
        if not isinstance(weapon_id, str) or not WEAPON_ID.fullmatch(weapon_id):
            raise WeaponSkinCatalogError(
                "weapon_skin_catalog_invalid_structure",
                f"{skin_id} declara un arma inválida.",
            )
        if type(skin_index) is not int or skin_index < 1:
            raise WeaponSkinCatalogError(
                "weapon_skin_catalog_invalid_structure",
                f"{skin_id} declara un índice inválido.",
            )
        if skin_id in by_id:
            raise WeaponSkinCatalogError(
                "weapon_skin_catalog_duplicate_id",
                f"El catálogo repite la skin de arma {skin_id}.",
            )
        name = _parse_names(row.get("name"), skin_id)
        weapon_name = _parse_names(row.get("weapon_name"), weapon_id)
        entry = {
            "id": skin_id,
            "name": name,
            "weapon_id": weapon_id,
            "weapon_name": weapon_name,
            "skin_index": skin_index,
        }
        by_id[skin_id] = entry
        ordered.append(skin_id)
        by_weapon.setdefault(weapon_id, []).append(skin_id)
        weapons.setdefault(
            weapon_id, {"id": weapon_id, "name": weapon_name, "skin_ids": []}
        )["skin_ids"].append(skin_id)  # type: ignore[index]
    if len(weapons) != EXPECTED_WEAPONS:
        raise WeaponSkinCatalogError(
            "weapon_skin_catalog_unexpected_size",
            "El catálogo de skins de arma no contiene sus 180 armas.",
        )
    for weapon_id, ids in by_weapon.items():
        indices = [int(by_id[skin_id]["skin_index"]) for skin_id in ids]
        if len(indices) != len(set(indices)):
            raise WeaponSkinCatalogError(
                "weapon_skin_catalog_duplicate_index",
                f"El arma {weapon_id} repite un índice de skin.",
            )
    return {
        "available": True,
        "error": None,
        "version": EXPECTED_VERSION,
        "counts": {"skins": len(by_id), "weapons": len(weapons)},
        "skin_ids": frozenset(by_id),
        "skins": by_id,
        "ordered_skins": ordered,
        "weapon_ids": frozenset(weapons),
        "weapon_skins": by_weapon,
        "weapons": weapons,
    }


@lru_cache(maxsize=4)
def _load_cached(path: str) -> dict[str, object]:
    return _parse_catalog(_read_document(Path(path)))


def load_weapon_skin_catalog(path: Path | None = None) -> dict[str, object]:
    global _last_failure
    source = Path(path) if path is not None else WEAPON_SKINS_PATH
    try:
        catalog = _load_cached(str(source))
    except WeaponSkinCatalogError as exc:
        signature = f"{source}:{exc.code}"
        if signature != _last_failure:
            logger.error(
                "Weapon skin catalog unavailable at %s (%s): %s", source, exc.code, exc
            )
            _last_failure = signature
        return _empty_catalog(exc.code)
    _last_failure = None
    return catalog


def clear_weapon_skin_catalog_cache() -> None:
    _load_cached.cache_clear()


def validate_weapon_skin_catalog(catalog: Mapping[str, object] | None = None) -> None:
    current = catalog if catalog is not None else load_weapon_skin_catalog()
    if not current.get("available"):
        raise WeaponSkinCatalogError(
            str(current.get("error") or "weapon_skin_catalog_unavailable"),
            "El catálogo de skins de arma no está disponible.",
        )
    if current.get("version") != EXPECTED_VERSION:
        raise WeaponSkinCatalogError(
            "weapon_skin_catalog_unexpected_version",
            "Versión inesperada del catálogo de skins de arma.",
        )
    if current.get("counts") != {"skins": EXPECTED_SKINS, "weapons": EXPECTED_WEAPONS}:
        raise WeaponSkinCatalogError(
            "weapon_skin_catalog_unexpected_size",
            "Recuento inesperado del catálogo de skins de arma.",
        )
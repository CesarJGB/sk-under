"""Proyección empaquetada del catálogo de armas (8.8.0).

``weapons-880.json`` se genera desde ``knowledge/catalogs/weapons.json`` con
``knowledge/tools/build_backend_weapons.py``. Solo contiene armas visibles en la
colección del jugador (se excluyen las variantes ``config_only``) y los
atributos factuales usados para etiquetar la disponibilidad de forja.
"""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping

WEAPONS_PATH = Path(__file__).resolve().parent / "weapons-880.json"
from .version import CATALOG_VERSION

EXPECTED_VERSION = CATALOG_VERSION
EXPECTED_WEAPONS = 995
EXPECTED_FORGEABLE = 494
EXPECTED_SCHEMA = "sk-under/backend-weapons@1"
MAX_TEXT = 120

logger = logging.getLogger(__name__)
_last_failure: str | None = None


class WeaponCatalogError(RuntimeError):
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
        "counts": {"weapons": 0, "forgeable": 0},
        "weapon_ids": frozenset(),
        "forgeable_ids": frozenset(),
        "weapons": {},
        "ordered_weapons": [],
        "subcategories": {},
    }


def _read_document(path: Path) -> Mapping[str, Any]:
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise WeaponCatalogError(
            "weapon_catalog_missing", f"No se encontró el catálogo de armas en {path}."
        ) from None
    except OSError as exc:
        raise WeaponCatalogError(
            "weapon_catalog_unreadable",
            f"No se pudo leer el catálogo de armas en {path} ({type(exc).__name__}).",
        ) from None
    try:
        document = json.loads(raw)
    except ValueError:
        raise WeaponCatalogError(
            "weapon_catalog_invalid_json",
            "El catálogo de armas no contiene JSON válido.",
        ) from None
    if not isinstance(document, dict):
        raise WeaponCatalogError(
            "weapon_catalog_invalid_structure", "El catálogo de armas debe ser un objeto JSON."
        )
    return document


def _parse_names(value: object, weapon_id: str) -> dict[str, str | None]:
    if not isinstance(value, dict):
        raise WeaponCatalogError(
            "weapon_catalog_invalid_structure", f"{weapon_id} no declara nombres."
        )
    return {"en": _safe_text(value.get("en")), "es": _safe_text(value.get("es"))}


def _parse_tags(value: object, weapon_id: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise WeaponCatalogError(
            "weapon_catalog_invalid_structure", f"{weapon_id} declara etiquetas inválidas."
        )
    tags: list[str] = []
    for tag in value:
        text = _safe_text(tag, 60)
        if text is None:
            raise WeaponCatalogError(
                "weapon_catalog_invalid_structure", f"{weapon_id} contiene una etiqueta inválida."
            )
        if text not in tags:
            tags.append(text)
    return tags


REQUIREMENT_STATUSES = frozenset(
    {
        "not_forgeable",
        "standard_level",
        "observed_fusion_exception",
        "pending_fusion_research",
        "pending_level_research",
    }
)
UNLOCK_METHODS = frozenset({"not_forgeable", "obtain_counter", "fusion"})


def _optional_count(value: object) -> int | None:
    return value if type(value) is int and value >= 1 else None


def _parse_requirement(row: Mapping[str, Any], weapon_id: str, forgeable: bool) -> dict[str, object]:
    status = row.get("requirement_status")
    if status not in REQUIREMENT_STATUSES:
        raise WeaponCatalogError(
            "weapon_catalog_invalid_structure",
            f"{weapon_id} declara un estado de requisito inválido.",
        )
    required = _optional_count(row.get("required_obtains"))
    recommended = _optional_count(row.get("recommended_obtains"))
    if not forgeable:
        if required is not None or recommended is not None:
            raise WeaponCatalogError(
                "weapon_catalog_invalid_structure",
                f"{weapon_id} no es forjable pero declara un contador objetivo.",
            )
    elif recommended is None:
        raise WeaponCatalogError(
            "weapon_catalog_invalid_structure",
            f"{weapon_id} es forjable pero no declara un contador objetivo.",
        )
    if required is not None and recommended is not None and required > recommended:
        raise WeaponCatalogError(
            "weapon_catalog_invalid_structure",
            f"{weapon_id} declara un requisito mayor que su objetivo seguro.",
        )
    unlock_method = row.get("unlock_method")
    if unlock_method not in UNLOCK_METHODS:
        raise WeaponCatalogError(
            "weapon_catalog_invalid_structure",
            f"{weapon_id} declara un método de desbloqueo inválido.",
        )
    if (unlock_method == "not_forgeable") != (not forgeable):
        raise WeaponCatalogError(
            "weapon_catalog_invalid_structure",
            f"{weapon_id} declara un método de desbloqueo incoherente.",
        )
    if unlock_method == "fusion" and row.get("requirement_basis") not in {
        "fusion_target",
        "fusion_target_level_proxy",
        "fusion_target_unknown_level",
    }:
        raise WeaponCatalogError(
            "weapon_catalog_invalid_structure",
            f"{weapon_id} declara fusión sin base de fusión.",
        )
    basis = row.get("requirement_basis")
    if not isinstance(basis, str) or not basis or len(basis) > 80:
        raise WeaponCatalogError(
            "weapon_catalog_invalid_structure",
            f"{weapon_id} declara una base de requisito inválida.",
        )
    evidence = row.get("requirement_evidence")
    if evidence not in {"E1", "E2", "E3", "E4"}:
        raise WeaponCatalogError(
            "weapon_catalog_invalid_structure",
            f"{weapon_id} declara una evidencia de requisito inválida.",
        )
    source = _safe_text(row.get("requirement_source"), 240)
    if source is None:
        raise WeaponCatalogError(
            "weapon_catalog_invalid_structure",
            f"{weapon_id} no declara la fuente de su requisito.",
        )
    additional = row.get("additional_requirements")
    if not isinstance(additional, list):
        raise WeaponCatalogError(
            "weapon_catalog_invalid_structure",
            f"{weapon_id} declara requisitos adicionales inválidos.",
        )
    additional_requirements: list[str] = []
    for value in additional:
        text = _safe_text(value, 120)
        if text is None:
            raise WeaponCatalogError(
                "weapon_catalog_invalid_structure",
                f"{weapon_id} contiene un requisito adicional inválido.",
            )
        if text not in additional_requirements:
            additional_requirements.append(text)
    return {
        "required_obtains": required,
        "recommended_obtains": recommended,
        "requirement_status": status,
        "requirement_basis": basis,
        "unlock_method": unlock_method,
        "requirement_evidence": evidence,
        "additional_requirements": additional_requirements,
        "requirement_source": source,
    }


def _parse_catalog(document: Mapping[str, Any]) -> dict[str, object]:
    if document.get("schema") != EXPECTED_SCHEMA:
        raise WeaponCatalogError(
            "weapon_catalog_invalid_structure",
            "El catálogo de armas declara un esquema inesperado.",
        )
    if document.get("game_version") != EXPECTED_VERSION:
        raise WeaponCatalogError(
            "weapon_catalog_unexpected_version", "El catálogo de armas no es de la versión 8.8.0."
        )
    if document.get("counts") != {
        "weapons": EXPECTED_WEAPONS,
        "forgeable": EXPECTED_FORGEABLE,
    }:
        raise WeaponCatalogError(
            "weapon_catalog_unexpected_size", "Los recuentos del catálogo de armas no coinciden."
        )
    rows = document.get("weapons")
    if not isinstance(rows, list) or len(rows) != EXPECTED_WEAPONS:
        raise WeaponCatalogError(
            "weapon_catalog_unexpected_size", "El catálogo de armas no contiene sus 995 filas."
        )
    by_id: dict[str, dict[str, object]] = {}
    ordered: list[str] = []
    forgeable: list[str] = []
    subcategories: dict[str, list[str]] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise WeaponCatalogError(
                "weapon_catalog_invalid_structure", "El catálogo de armas contiene una fila inválida."
            )
        weapon_id = row.get("id")
        if not isinstance(weapon_id, str) or not weapon_id or len(weapon_id) > MAX_TEXT:
            raise WeaponCatalogError(
                "weapon_catalog_invalid_structure",
                "Un arma declara un identificador inválido.",
            )
        if weapon_id in by_id:
            raise WeaponCatalogError(
                "weapon_catalog_duplicate_id", f"El catálogo repite el arma {weapon_id}."
            )
        subcategory = _safe_text(row.get("subcategory"))
        level = row.get("level")
        drop_level = row.get("drop_level")
        can_forge = row.get("forgeable") is True
        entry = {
            "id": weapon_id,
            "name": _parse_names(row.get("name"), weapon_id),
            "subcategory": subcategory,
            "level": level if type(level) is int else None,
            "forgeable": can_forge,
            "drop_level": drop_level if type(drop_level) is int else None,
            "in_weapon_catalog": row.get("in_weapon_catalog") is True,
            "tags": _parse_tags(row.get("tags"), weapon_id),
            **_parse_requirement(row, weapon_id, can_forge),
        }
        by_id[weapon_id] = entry
        ordered.append(weapon_id)
        if can_forge:
            forgeable.append(weapon_id)
        if subcategory is not None:
            subcategories.setdefault(subcategory, []).append(weapon_id)
    if len(forgeable) != EXPECTED_FORGEABLE:
        raise WeaponCatalogError(
            "weapon_catalog_unexpected_size",
            "El catálogo de armas no contiene sus 494 armas forjables.",
        )
    return {
        "available": True,
        "error": None,
        "version": EXPECTED_VERSION,
        "counts": {"weapons": len(by_id), "forgeable": len(forgeable)},
        "weapon_ids": frozenset(by_id),
        "forgeable_ids": frozenset(forgeable),
        "weapons": by_id,
        "ordered_weapons": ordered,
        "subcategories": subcategories,
    }


@lru_cache(maxsize=4)
def _load_cached(path: str) -> dict[str, object]:
    return _parse_catalog(_read_document(Path(path)))


def load_weapon_catalog(path: Path | None = None) -> dict[str, object]:
    global _last_failure
    source = Path(path) if path is not None else WEAPONS_PATH
    try:
        catalog = _load_cached(str(source))
    except WeaponCatalogError as exc:
        signature = f"{source}:{exc.code}"
        if signature != _last_failure:
            logger.error("Weapon catalog unavailable at %s (%s): %s", source, exc.code, exc)
            _last_failure = signature
        return _empty_catalog(exc.code)
    _last_failure = None
    return catalog


def clear_weapon_catalog_cache() -> None:
    _load_cached.cache_clear()


def validate_weapon_catalog(catalog: Mapping[str, object] | None = None) -> None:
    current = catalog if catalog is not None else load_weapon_catalog()
    if not current.get("available"):
        raise WeaponCatalogError(
            str(current.get("error") or "weapon_catalog_unavailable"),
            "El catálogo de armas no está disponible.",
        )
    if current.get("version") != EXPECTED_VERSION:
        raise WeaponCatalogError(
            "weapon_catalog_unexpected_version", "Versión inesperada del catálogo de armas."
        )
    if current.get("counts") != {
        "weapons": EXPECTED_WEAPONS,
        "forgeable": EXPECTED_FORGEABLE,
    }:
        raise WeaponCatalogError(
            "weapon_catalog_unexpected_size", "Recuento inesperado del catálogo de armas."
        )
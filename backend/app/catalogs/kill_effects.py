"""Proyección empaquetada de efectos de eliminación (8.8.0).

Los identificadores 1-8 están respaldados por los prefabs y controladores de la
APK 8.8.0. El identificador 0 es el efecto predeterminado. Los valores 9 y 10 se
observaron en una partida 8.6.0 pero no tienen nombre ni recurso localizado; se
exponen como desconocidos y nunca se ofrecen para desbloquear.
"""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping

KILL_EFFECTS_PATH = Path(__file__).resolve().parent / "kill-effects-880.json"
EXPECTED_VERSION = "8.8.0"
EXPECTED_EFFECTS = 9
EXPECTED_SCHEMA = "sk-under/backend-kill-effects@1"
EXPECTED_UNKNOWN = (9, 10)
MAX_TEXT = 120

logger = logging.getLogger(__name__)
_last_failure: str | None = None


class KillEffectCatalogError(RuntimeError):
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
        "counts": {"effects": 0},
        "effect_ids": frozenset(),
        "effects": {},
        "ordered_effects": [],
        "unknown_ids": frozenset(EXPECTED_UNKNOWN),
    }


def _read_document(path: Path) -> Mapping[str, Any]:
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise KillEffectCatalogError(
            "kill_effect_catalog_missing",
            f"No se encontró el catálogo de efectos de eliminación en {path}.",
        ) from None
    except OSError as exc:
        raise KillEffectCatalogError(
            "kill_effect_catalog_unreadable",
            f"No se pudo leer el catálogo de efectos de eliminación en {path} ({type(exc).__name__}).",
        ) from None
    try:
        document = json.loads(raw)
    except ValueError:
        raise KillEffectCatalogError(
            "kill_effect_catalog_invalid_json",
            "El catálogo de efectos de eliminación no contiene JSON válido.",
        ) from None
    if not isinstance(document, dict):
        raise KillEffectCatalogError(
            "kill_effect_catalog_invalid_structure",
            "El catálogo de efectos de eliminación debe ser un objeto JSON.",
        )
    return document


def _names(value: object, effect_id: int) -> dict[str, str | None]:
    if not isinstance(value, dict):
        raise KillEffectCatalogError(
            "kill_effect_catalog_invalid_structure",
            f"El efecto {effect_id} no declara nombres.",
        )
    return {"en": _safe_text(value.get("en")), "es": _safe_text(value.get("es"))}


def _parse_catalog(document: Mapping[str, Any]) -> dict[str, object]:
    if document.get("schema") != EXPECTED_SCHEMA:
        raise KillEffectCatalogError(
            "kill_effect_catalog_invalid_structure",
            "El catálogo de efectos de eliminación declara un esquema inesperado.",
        )
    if document.get("game_version") != EXPECTED_VERSION:
        raise KillEffectCatalogError(
            "kill_effect_catalog_unexpected_version",
            "El catálogo de efectos de eliminación no es de la versión 8.8.0.",
        )
    if document.get("counts") != {"effects": EXPECTED_EFFECTS}:
        raise KillEffectCatalogError(
            "kill_effect_catalog_unexpected_size",
            "El recuento del catálogo de efectos de eliminación no coincide.",
        )
    if tuple(document.get("observed_unknown_ids") or ()) != EXPECTED_UNKNOWN:
        raise KillEffectCatalogError(
            "kill_effect_catalog_invalid_structure",
            "Los identificadores observados sin catálogo no coinciden.",
        )
    rows = document.get("effects")
    if not isinstance(rows, list) or len(rows) != EXPECTED_EFFECTS:
        raise KillEffectCatalogError(
            "kill_effect_catalog_unexpected_size",
            "El catálogo de efectos de eliminación no contiene sus 9 filas.",
        )
    by_id: dict[int, dict[str, object]] = {}
    ordered: list[int] = []
    for row in rows:
        if not isinstance(row, dict):
            raise KillEffectCatalogError(
                "kill_effect_catalog_invalid_structure",
                "El catálogo de efectos de eliminación contiene una fila inválida.",
            )
        effect_id = row.get("id")
        if type(effect_id) is not int or not 0 <= effect_id < EXPECTED_EFFECTS:
            raise KillEffectCatalogError(
                "kill_effect_catalog_invalid_structure",
                "Un efecto de eliminación declara un identificador inválido.",
            )
        if effect_id in by_id:
            raise KillEffectCatalogError(
                "kill_effect_catalog_duplicate_id",
                f"El catálogo repite el efecto de eliminación {effect_id}.",
            )
        item_id = row.get("item_id")
        if item_id is not None and (
            not isinstance(item_id, str)
            or not item_id.startswith("customization_kill_effect_")
        ):
            raise KillEffectCatalogError(
                "kill_effect_catalog_invalid_structure",
                f"El efecto {effect_id} declara un objeto inválido.",
            )
        acquisition = row.get("acquisition")
        if acquisition is not None and not isinstance(acquisition, str):
            raise KillEffectCatalogError(
                "kill_effect_catalog_invalid_structure",
                f"El efecto {effect_id} declara una adquisición inválida.",
            )
        by_id[effect_id] = {
            "id": effect_id,
            "item_id": item_id,
            "name": _names(row.get("name"), effect_id),
            "icon": _safe_text(row.get("icon"), 240),
            "acquisition": _safe_text(acquisition),
            "evidence": _safe_text(row.get("evidence")),
        }
        ordered.append(effect_id)
    if sorted(ordered) != list(range(EXPECTED_EFFECTS)):
        raise KillEffectCatalogError(
            "kill_effect_catalog_unexpected_ids",
            "El catálogo no contiene los identificadores 0-8.",
        )
    return {
        "available": True,
        "error": None,
        "version": EXPECTED_VERSION,
        "counts": {"effects": len(by_id)},
        "effect_ids": frozenset(by_id),
        "effects": by_id,
        "ordered_effects": sorted(ordered),
        "unknown_ids": frozenset(EXPECTED_UNKNOWN),
    }


@lru_cache(maxsize=4)
def _load_cached(path: str) -> dict[str, object]:
    return _parse_catalog(_read_document(Path(path)))


def load_kill_effect_catalog(path: Path | None = None) -> dict[str, object]:
    global _last_failure
    source = Path(path) if path is not None else KILL_EFFECTS_PATH
    try:
        catalog = _load_cached(str(source))
    except KillEffectCatalogError as exc:
        signature = f"{source}:{exc.code}"
        if signature != _last_failure:
            logger.error(
                "Kill effect catalog unavailable at %s (%s): %s", source, exc.code, exc
            )
            _last_failure = signature
        return _empty_catalog(exc.code)
    _last_failure = None
    return catalog


def clear_kill_effect_catalog_cache() -> None:
    _load_cached.cache_clear()


def validate_kill_effect_catalog(catalog: Mapping[str, object] | None = None) -> None:
    current = catalog if catalog is not None else load_kill_effect_catalog()
    if not current.get("available"):
        raise KillEffectCatalogError(
            str(current.get("error") or "kill_effect_catalog_unavailable"),
            "El catálogo de efectos de eliminación no está disponible.",
        )
    if current.get("version") != EXPECTED_VERSION:
        raise KillEffectCatalogError(
            "kill_effect_catalog_unexpected_version",
            "Versión inesperada del catálogo de efectos de eliminación.",
        )
    if current.get("counts") != {"effects": EXPECTED_EFFECTS}:
        raise KillEffectCatalogError(
            "kill_effect_catalog_unexpected_size",
            "Recuento inesperado del catálogo de efectos de eliminación.",
        )
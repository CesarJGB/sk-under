"""Catálogo saneado de personajes empaquetado con el backend.

El archivo ``characters-880.json`` es la única fuente de verdad del catálogo.
Vive dentro del paquete ``app`` para que la imagen de producción lo copie con
``COPY app/ ./app/`` y para que su ruta no dependa del directorio de trabajo ni
de la estructura documental del repositorio.

El cargador no memoriza fallos: si el archivo falta o está corrupto devuelve un
resultado vacío con un diagnóstico, pero el siguiente intento vuelve a leer el
disco. Así un catálogo reparado o montado después no queda oculto por una caché
de error.
"""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping

CATALOG_PATH = Path(__file__).resolve().parent / "characters-880.json"
from .version import CATALOG_VERSION

EXPECTED_VERSION = CATALOG_VERSION
EXPECTED_CHARACTERS = 42
EXPECTED_SKILLS = 105
EXPECTED_SKINS = 802
MAX_TEXT = 120

logger = logging.getLogger(__name__)

_last_failure: str | None = None


class CharacterCatalogError(RuntimeError):
    """Problema controlado del catálogo local de personajes."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _safe_text(value: object, limit: int = MAX_TEXT) -> str:
    text = "" if value is None else str(value)
    text = text.replace("\x00", "")
    text = "".join(char for char in text if char.isprintable())
    return text if len(text) <= limit else text[:limit] + "…"


def _empty_catalog(error: str) -> dict[str, object]:
    return {
        "available": False,
        "error": error,
        "version": None,
        "source": None,
        "codes": [],
        "characters": {},
        "skins": {},
        "skills": {},
    }


def _read_document(path: Path) -> Mapping[str, Any]:
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise CharacterCatalogError(
            "catalog_missing", f"No se encontró el catálogo de personajes en {path}."
        ) from None
    except OSError as exc:
        raise CharacterCatalogError(
            "catalog_unreadable",
            f"No se pudo leer el catálogo de personajes en {path} ({type(exc).__name__}).",
        ) from None
    try:
        document = json.loads(raw)
    except ValueError:
        raise CharacterCatalogError(
            "catalog_invalid_json", f"El catálogo de personajes en {path} no contiene JSON válido."
        ) from None
    if not isinstance(document, dict):
        raise CharacterCatalogError(
            "catalog_invalid_structure", "El catálogo de personajes debe ser un objeto JSON."
        )
    return document


def _parse_catalog(document: Mapping[str, Any]) -> dict[str, object]:
    version = document.get("version")
    source = document.get("source")
    if not isinstance(version, str) or not version:
        raise CharacterCatalogError(
            "catalog_invalid_structure", "El catálogo no declara una versión válida."
        )
    if not isinstance(source, str) or not source:
        raise CharacterCatalogError(
            "catalog_invalid_structure", "El catálogo no declara una fuente válida."
        )
    characters = document.get("characters")
    if not isinstance(characters, list) or not characters:
        raise CharacterCatalogError(
            "catalog_invalid_structure", "El catálogo no contiene una lista de personajes."
        )

    by_code: dict[str, dict[str, object]] = {}
    skins: dict[str, dict[str, str]] = {}
    skills: dict[str, str] = {}
    codes: list[str] = []
    indices: set[int] = set()
    for entry in characters:
        if not isinstance(entry, dict):
            raise CharacterCatalogError(
                "catalog_invalid_structure", "El catálogo contiene un personaje que no es un objeto."
            )
        index = entry.get("index")
        code = entry.get("code")
        if type(index) is not int or index < 0:
            raise CharacterCatalogError(
                "catalog_invalid_structure", "El catálogo contiene un índice de personaje inválido."
            )
        if index in indices:
            raise CharacterCatalogError(
                "catalog_invalid_structure", f"El catálogo repite el índice de personaje {index}."
            )
        if not isinstance(code, str) or not code:
            raise CharacterCatalogError(
                "catalog_invalid_structure", "El catálogo contiene un código de personaje inválido."
            )
        if code in by_code:
            raise CharacterCatalogError(
                "catalog_invalid_structure", f"El catálogo repite el código de personaje {code}."
            )
        skills_raw = entry.get("skills", [])
        skins_raw = entry.get("skins", [])
        if not isinstance(skills_raw, list) or not isinstance(skins_raw, list):
            raise CharacterCatalogError(
                "catalog_invalid_structure",
                f"El personaje {code} no declara listas válidas de habilidades y skins.",
            )
        group = f"c{index}"
        skins[group] = {}
        for skin in skins_raw:
            if not isinstance(skin, dict):
                raise CharacterCatalogError(
                    "catalog_invalid_structure", f"El personaje {code} contiene una skin inválida."
                )
            key = skin.get("key")
            name = skin.get("name")
            if not isinstance(key, str) or not key or not isinstance(name, str):
                raise CharacterCatalogError(
                    "catalog_invalid_structure", f"El personaje {code} contiene una skin inválida."
                )
            if key in skins[group]:
                raise CharacterCatalogError(
                    "catalog_invalid_structure", f"El personaje {code} repite la skin {key}."
                )
            skins[group][key] = _safe_text(name)
        for skill in skills_raw:
            if not isinstance(skill, dict):
                raise CharacterCatalogError(
                    "catalog_invalid_structure",
                    f"El personaje {code} contiene una habilidad inválida.",
                )
            key = skill.get("key")
            name = skill.get("name")
            if not isinstance(key, str) or not key or not isinstance(name, str):
                raise CharacterCatalogError(
                    "catalog_invalid_structure",
                    f"El personaje {code} contiene una habilidad inválida.",
                )
            if key in skills:
                raise CharacterCatalogError(
                    "catalog_invalid_structure", f"El catálogo repite la habilidad {key}."
                )
            skills[key] = _safe_text(name)
        indices.add(index)
        codes.append(code)
        by_code[code] = entry

    return {
        "available": True,
        "error": None,
        "version": version,
        "source": source,
        "codes": codes,
        "characters": by_code,
        "skins": skins,
        "skills": skills,
    }


@lru_cache(maxsize=4)
def _load_cached(path: str) -> dict[str, object]:
    """Carga y memoriza solo un catálogo válido; los fallos no se cachean."""
    return _parse_catalog(_read_document(Path(path)))


def _log_failure(path: Path, error: CharacterCatalogError) -> None:
    global _last_failure
    signature = f"{path}:{error.code}"
    if signature != _last_failure:
        logger.error("Character catalog unavailable at %s (%s): %s", path, error.code, error)
        _last_failure = signature


def load_character_catalog(path: Path | None = None) -> dict[str, object]:
    """Devuelve el catálogo empaquetado o un resultado vacío con diagnóstico.

    ``path`` solo existe para pruebas y verificación; el backend siempre usa
    :data:`CATALOG_PATH`, resuelto a partir de la ubicación de este módulo.
    """
    global _last_failure
    source = Path(path) if path is not None else CATALOG_PATH
    try:
        catalog = _load_cached(str(source))
    except CharacterCatalogError as exc:
        _log_failure(source, exc)
        return _empty_catalog(exc.code)
    _last_failure = None
    return catalog


def clear_character_catalog_cache() -> None:
    """Limpia la caché de lecturas válidas; útil para pruebas."""
    _load_cached.cache_clear()


def validate_character_catalog(catalog: Mapping[str, object] | None = None) -> None:
    """Valida la estructura y el contenido esperado durante la construcción.

    Se ejecuta en ``RUN python -m app.catalogs.verify`` dentro de la imagen.
    """
    current = catalog if catalog is not None else load_character_catalog()
    if not current.get("available"):
        raise CharacterCatalogError(
            str(current.get("error") or "catalog_unavailable"),
            "El catálogo de personajes no está disponible o no se pudo interpretar.",
        )
    if current.get("version") != EXPECTED_VERSION:
        raise CharacterCatalogError(
            "catalog_unexpected_version",
            f"Se esperaba la versión {EXPECTED_VERSION} y se encontró {current.get('version')!r}.",
        )
    codes = current.get("codes")
    characters = current.get("characters")
    skills = current.get("skills")
    skins = current.get("skins")
    if not isinstance(codes, list) or not isinstance(characters, dict):
        raise CharacterCatalogError(
            "catalog_invalid_structure", "El catálogo no expone los códigos o personajes esperados."
        )
    if len(codes) != EXPECTED_CHARACTERS or len(characters) != EXPECTED_CHARACTERS:
        raise CharacterCatalogError(
            "catalog_unexpected_size",
            f"Se esperaban {EXPECTED_CHARACTERS} personajes y hay {len(codes)}.",
        )
    if len(set(codes)) != EXPECTED_CHARACTERS:
        raise CharacterCatalogError(
            "catalog_duplicate_codes", "El catálogo contiene códigos de personaje repetidos."
        )
    if not isinstance(skills, dict) or len(skills) != EXPECTED_SKILLS:
        raise CharacterCatalogError(
            "catalog_unexpected_skills",
            f"Se esperaban {EXPECTED_SKILLS} habilidades y hay "
            f"{len(skills) if isinstance(skills, dict) else 'un valor inválido'}.",
        )
    if not isinstance(skins, dict) or sum(
        len(group) for group in skins.values() if isinstance(group, dict)
    ) != EXPECTED_SKINS:
        raise CharacterCatalogError(
            "catalog_unexpected_skins", f"Se esperaban {EXPECTED_SKINS} skins."
        )
    required = {"Knight", "Ranger", "CostumePrince", "LadyChef"}
    if not required.issubset(set(codes)):
        raise CharacterCatalogError(
            "catalog_unexpected_content", "Faltan códigos obligatorios en el catálogo de personajes."
        )
    if codes[0] != "Knight" or codes[-1] != "LadyChef":
        raise CharacterCatalogError(
            "catalog_unexpected_content", "El orden de los personajes no coincide con el observado."
        )
#!/usr/bin/env python3
"""Generate the backend projection of the 8.8.0 weapon catalog.

The backend only needs stable identifiers, localized names and the factual
attributes that decide whether a weapon belongs to the player-visible catalog
and whether it can appear in the forge. ``--check`` detects drift in tests/CI.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WEAPONS = ROOT / "knowledge" / "catalogs" / "weapons.json"
OUTPUT = ROOT / "backend" / "app" / "catalogs" / "weapons-880.json"

SCHEMA = "sk-under/backend-weapons@1"
EXPECTED_WEAPONS = 995
EXPECTED_FORGEABLE = 494
MAX_TEXT = 120

# ``UIForge.IsUnlockedByObtainTime`` compara el contador de
# ``statisticData.object2ObtainTime`` con ``UIForge.UnlockCountDict[level]``.
# El diccionario usa 2/3/4/6/6 para los niveles 0..4 y cae en 8 para claves
# ausentes (niveles 5, 6 o superiores). La tabla pública coincide con esos
# umbrales. Sigue siendo evidencia E2 hasta la validación física por arma.
FORGE_OBTAINS_BY_LEVEL = {0: 2, 1: 3, 2: 4, 3: 6, 4: 6, 5: 8, 6: 8}
DEFAULT_FORGE_OBTAINS = 8

# Excepciones observadas físicamente. ``weapon_337`` es un objetivo de fusión
# (UZI + Flor de cerezo) y el juego mostró 1/2, no 1/6.
FORGE_OBSERVED_OVERRIDES = {
    "weapon_337": {
        "required_obtains": 2,
        "requirement_status": "observed_fusion_exception",
        "requirement_evidence": "E3",
        "source": "Validación física Android 8.8.0.13 + weapons.txt FusionList",
    }
}


class ProjectionError(RuntimeError):
    pass


def _load(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise ProjectionError(f"No se pudo leer {path}: {error}") from error
    if not isinstance(value, dict) or not isinstance(value.get("items"), list):
        raise ProjectionError(f"Catálogo inválido: {path}")
    return value


def _text(value: object, limit: int = MAX_TEXT) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.replace("\x00", "")
    text = "".join(char for char in text if char.isprintable()).strip()
    if not text:
        return None
    return text if len(text) <= limit else text[:limit] + "…"


def _name(item: dict) -> dict[str, str | None]:
    name = item.get("name")
    if not isinstance(name, dict):
        name = {}
    return {key: _text(name.get(key)) for key in ("en", "es")}


def _tags(attributes: dict) -> list[str]:
    value = attributes.get("tags")
    if not isinstance(value, list):
        return []
    tags: list[str] = []
    for tag in value:
        text = _text(tag, 60)
        if text is not None and text not in tags:
            tags.append(text)
    return tags


def _fusion_targets(items: list[dict]) -> set[str]:
    targets: set[str] = set()
    for item in items:
        relations = item.get("relations")
        relations = relations if isinstance(relations, dict) else {}
        values = relations.get("fusion_targets")
        if not isinstance(values, list):
            continue
        for value in values:
            if isinstance(value, str) and value:
                targets.add(value)
    return targets


def _forge_requirement(weapon_id: str, level: object, forgeable: bool, fusion: bool) -> dict:
    if not forgeable:
        return {
            "required_obtains": None,
            "recommended_obtains": None,
            "requirement_status": "not_forgeable",
            "requirement_basis": "catalog_not_forgeable",
            "unlock_method": "not_forgeable",
            "requirement_evidence": "E1",
            "additional_requirements": [],
            "requirement_source": "knowledge/catalogs/weapons.json attributes.forgeable",
        }
    observed = FORGE_OBSERVED_OVERRIDES.get(weapon_id)
    if observed is not None:
        return {
            "required_obtains": observed["required_obtains"],
            "recommended_obtains": observed["required_obtains"],
            "requirement_status": observed["requirement_status"],
            "requirement_basis": "fusion_target",
            "unlock_method": "fusion",
            "requirement_evidence": observed["requirement_evidence"],
            "additional_requirements": [],
            "requirement_source": observed["source"],
        }
    if fusion:
        # El umbral se consulta por TbWeapons.Level. Para los objetivos de
        # fusión usamos el nivel de prefab como proxy (Aurora nivel 3 -> 6) y
        # marcamos el requisito como provisional: weapon_337 demuestra que
        # ambos niveles pueden divergir. Aun así el valor aplicado es el
        # mínimo estándar, nunca un 8 arbitrario.
        if type(level) is int and level in FORGE_OBTAINS_BY_LEVEL:
            required = FORGE_OBTAINS_BY_LEVEL[level]
            return {
                "required_obtains": required,
                "recommended_obtains": required,
                "requirement_status": "pending_fusion_research",
                "requirement_basis": "fusion_target_level_proxy",
                "unlock_method": "fusion",
                "requirement_evidence": "E2",
                "additional_requirements": [],
                "requirement_source": (
                    "UIForge.UnlockCountDict[nivel de prefab como proxy]; "
                    "nivel TbWeapons.Level pendiente; weapon_337 validado E3"
                ),
            }
        return {
            "required_obtains": None,
            "recommended_obtains": DEFAULT_FORGE_OBTAINS,
            "requirement_status": "pending_level_research",
            "requirement_basis": "fusion_target_unknown_level",
            "unlock_method": "fusion",
            "requirement_evidence": "E2",
            "additional_requirements": [],
            "requirement_source": (
                "UIForge.GetWeaponUnlockCount fallback 8; "
                "nivel de fusión desconocido"
            ),
        }
    if type(level) is int and level in FORGE_OBTAINS_BY_LEVEL:
        required = FORGE_OBTAINS_BY_LEVEL[level]
        return {
            "required_obtains": required,
            "recommended_obtains": required,
            "requirement_status": "standard_level",
            "requirement_basis": "level",
            "unlock_method": "obtain_counter",
            "requirement_evidence": "E2",
            "additional_requirements": [],
            "requirement_source": (
                "UIForge.UnlockCountDict 0..4 = 2/3/4/6/6; "
                "GetWeaponUnlockCount fallback 8; wiki Forge Table"
            ),
        }
    return {
        "required_obtains": None,
        "recommended_obtains": DEFAULT_FORGE_OBTAINS,
        "requirement_status": "pending_level_research",
        "requirement_basis": "unknown_level",
        "unlock_method": "obtain_counter",
        "requirement_evidence": "E2",
        "additional_requirements": [],
        "requirement_source": "Nivel desconocido; fallback 8 de UIForge.GetWeaponUnlockCount",
    }


def build() -> dict:
    document = _load(WEAPONS)
    if document.get("game_version") != "8.8.0":
        raise ProjectionError("El catálogo de armas no es de la versión 8.8.0")
    items = document["items"]
    fusion_targets = _fusion_targets(items)
    rows = []
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            raise ProjectionError("Fila de arma inválida")
        attributes = item.get("attributes")
        attributes = attributes if isinstance(attributes, dict) else {}
        if attributes.get("config_only") is not False:
            continue
        weapon_id = item.get("id")
        if not isinstance(weapon_id, str) or not weapon_id:
            raise ProjectionError("Arma con identificador inválido")
        if weapon_id in seen:
            raise ProjectionError(f"Arma repetida: {weapon_id}")
        seen.add(weapon_id)
        level = attributes.get("level") if type(attributes.get("level")) is int else None
        forgeable = attributes.get("forgeable") is True
        requirement = _forge_requirement(
            weapon_id, level, forgeable, weapon_id in fusion_targets
        )
        rows.append(
            {
                "id": weapon_id,
                "name": _name(item),
                "subcategory": _text(item.get("subcategory")),
                "level": level,
                "forgeable": forgeable,
                "drop_level": attributes.get("drop_level")
                if type(attributes.get("drop_level")) is int
                else None,
                "in_weapon_catalog": attributes.get("in_weapon_catalog") is True,
                "tags": _tags(attributes),
                **requirement,
            }
        )
    forgeable = sum(1 for row in rows if row["forgeable"])
    if len(rows) != EXPECTED_WEAPONS or forgeable != EXPECTED_FORGEABLE:
        raise ProjectionError(
            "La proyección de armas no coincide: "
            f"{len(rows)} armas, {forgeable} forjables"
        )
    return {
        "schema": SCHEMA,
        "game_version": "8.8.0",
        "generated_by": "knowledge/tools/build_backend_weapons.py",
        "source_refs": {"weapons": "knowledge/catalogs/weapons.json"},
        "counts": {"weapons": len(rows), "forgeable": forgeable},
        "weapons": rows,
    }


def render(document: dict) -> str:
    return json.dumps(document, ensure_ascii=False, indent=2) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    expected = render(build())
    if args.check:
        try:
            current = OUTPUT.read_text(encoding="utf-8")
        except OSError as error:
            raise SystemExit(f"Falta la proyección {OUTPUT}: {error}")
        if current != expected:
            raise SystemExit(f"La proyección {OUTPUT} está desactualizada")
        print(f"{OUTPUT} está actualizado")
        return 0
    OUTPUT.write_text(expected, encoding="utf-8")
    print(f"Escrito {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
#!/usr/bin/env python3
"""Generate the backend projections for weapon skins and kill effects.

The backend does not keep a second catalog: these projections are derived from
``knowledge/catalogs`` and are packaged inside ``backend/app/catalogs``. Use
``--check`` to detect drift without rewriting the files.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WEAPON_SKINS = ROOT / "knowledge" / "catalogs" / "weapon_skins.json"
WEAPONS = ROOT / "knowledge" / "catalogs" / "weapons.json"
SPECIAL_ITEMS = ROOT / "knowledge" / "catalogs" / "special_items.json"
SKINS_OUTPUT = ROOT / "backend" / "app" / "catalogs" / "weapon-skins-880.json"
EFFECTS_OUTPUT = ROOT / "backend" / "app" / "catalogs" / "kill-effects-880.json"

SKINS_SCHEMA = "sk-under/backend-weapon-skins@1"
EFFECTS_SCHEMA = "sk-under/backend-kill-effects@1"
GAME_VERSION = "8.8.0"
EXPECTED_SKINS = 192
EXPECTED_WEAPONS = 180
EXPECTED_EFFECTS = 9
OBSERVED_UNKNOWN_EFFECTS = (9, 10)

# Localized strings evidenced by I2language.csv keys
# customization_kill_effect_{N}_name. Only 0-3 have rows in the available dump.
EFFECT_NAMES = {
    0: {"en": "Default", "es": "Predeterminado"},
    1: {"en": "Starlight Sparkle", "es": "Destello estelar"},
    2: {"en": "Zap!", "es": "¡Zas!"},
    3: {"en": "Bring It On", "es": "¡Adelante!"},
}
EFFECT_ITEM_IDS = {number: f"customization_kill_effect_{number}" for number in range(1, 9)}


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


def _name(value: object) -> dict[str, str | None]:
    source = value if isinstance(value, dict) else {}
    return {
        "en": source.get("en") if isinstance(source.get("en"), str) else None,
        "es": source.get("es") if isinstance(source.get("es"), str) else None,
    }


def build_skins() -> dict:
    skins = _load(WEAPON_SKINS)
    weapons = _load(WEAPONS)
    weapon_rows = {item["id"]: item for item in weapons["items"] if isinstance(item, dict)}
    rows = []
    seen: set[str] = set()
    for item in skins["items"]:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str):
            raise ProjectionError("Skin de arma sin id")
        skin_id = item["id"]
        attributes = item.get("attributes")
        if not isinstance(attributes, dict):
            raise ProjectionError(f"{skin_id} no declara atributos")
        weapon_id = attributes.get("weapon_id")
        skin_index = attributes.get("skin_index")
        if not isinstance(weapon_id, str) or type(skin_index) is not int:
            raise ProjectionError(f"{skin_id} declara atributos inválidos")
        if skin_id in seen:
            raise ProjectionError(f"Skin duplicada: {skin_id}")
        weapon = weapon_rows.get(weapon_id)
        if weapon is None:
            raise ProjectionError(f"{skin_id} referencia un arma desconocida: {weapon_id}")
        seen.add(skin_id)
        rows.append(
            {
                "id": skin_id,
                "name": _name(item.get("name")),
                "weapon_id": weapon_id,
                "weapon_name": _name(weapon.get("name")),
                "skin_index": skin_index,
            }
        )
    rows.sort(key=lambda row: (row["weapon_id"], row["skin_index"]))
    distinct_weapons = len({row["weapon_id"] for row in rows})
    if len(rows) != EXPECTED_SKINS or distinct_weapons != EXPECTED_WEAPONS:
        raise ProjectionError(
            f"Recuento inesperado: {len(rows)} skins en {distinct_weapons} armas"
        )
    if skins.get("game_version") != GAME_VERSION:
        raise ProjectionError("La versión del catálogo de skins de arma cambió")
    return {
        "schema": SKINS_SCHEMA,
        "game_version": GAME_VERSION,
        "generated_by": "knowledge/tools/build_backend_customization.py",
        "source_refs": {
            "skins": "knowledge/catalogs/weapon_skins.json",
            "weapons": "knowledge/catalogs/weapons.json",
        },
        "evidence": "E1",
        "counts": {"skins": len(rows), "weapons": distinct_weapons},
        "weapon_skins": rows,
    }


def build_effects() -> dict:
    special = _load(SPECIAL_ITEMS)
    by_item = {
        item["id"]: item
        for item in special["items"]
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    rows = []
    for number in range(EXPECTED_EFFECTS):
        if number == 0:
            name = EFFECT_NAMES[0]
            item_id = None
            icon = None
            acquisition = "default"
        else:
            item_id = EFFECT_ITEM_IDS[number]
            item = by_item.get(item_id)
            if item is None:
                raise ProjectionError(f"Falta el objeto {item_id}")
            name = _name(item.get("name")) or EFFECT_NAMES.get(number)
            icon = f"Assets/RGTexture/kill_effect/effect_{number}/effect_{number}_icon.png"
            acquisition = None
        rows.append(
            {
                "id": number,
                "item_id": item_id,
                "name": name or {"en": None, "es": None},
                "icon": icon,
                "acquisition": acquisition,
                "evidence": "E1",
            }
        )
    if len(rows) != EXPECTED_EFFECTS:
        raise ProjectionError("Recuento de efectos de eliminación inesperado")
    return {
        "schema": EFFECTS_SCHEMA,
        "game_version": GAME_VERSION,
        "generated_by": "knowledge/tools/build_backend_customization.py",
        "source_refs": {
            "items": "knowledge/catalogs/special_items.json",
            "localization": "SKDFE I2language.csv 6.1.1",
            "assets": "APK 8.8.0 common.manifest",
        },
        "evidence": "E1",
        "counts": {"effects": len(rows)},
        "observed_unknown_ids": list(OBSERVED_UNKNOWN_EFFECTS),
        "effects": rows,
    }


def render(document: dict) -> str:
    return json.dumps(document, ensure_ascii=False, indent=2) + "\n"


def _write(output: Path, document: dict, check: bool) -> bool:
    expected = render(document)
    if check:
        try:
            current = output.read_text(encoding="utf-8")
        except OSError as error:
            print(f"Falta la proyección {output}: {error}", file=sys.stderr)
            return False
        if current != expected:
            print(f"La proyección {output.name} está desactualizada.", file=sys.stderr)
            return False
        print(f"Proyección {output.name} actualizada.")
        return True
    output.write_text(expected, encoding="utf-8")
    print(f"Escrito {output.relative_to(ROOT)}")
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    try:
        skins = build_skins()
        effects = build_effects()
    except ProjectionError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    ok = _write(SKINS_OUTPUT, skins, args.check)
    ok = _write(EFFECTS_OUTPUT, effects, args.check) and ok
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
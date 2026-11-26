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


def build() -> dict:
    document = _load(WEAPONS)
    if document.get("game_version") != "8.8.0":
        raise ProjectionError("El catálogo de armas no es de la versión 8.8.0")
    items = document["items"]
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
        rows.append(
            {
                "id": weapon_id,
                "name": _name(item),
                "subcategory": _text(item.get("subcategory")),
                "level": attributes.get("level")
                if type(attributes.get("level")) is int
                else None,
                "forgeable": attributes.get("forgeable") is True,
                "drop_level": attributes.get("drop_level")
                if type(attributes.get("drop_level")) is int
                else None,
                "in_weapon_catalog": attributes.get("in_weapon_catalog") is True,
                "tags": _tags(attributes),
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
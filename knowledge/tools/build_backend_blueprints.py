#!/usr/bin/env python3
"""Generate the backend projection of the 8.8.0 blueprint catalog.

The backend only needs stable identifiers, localized names when available and
the target/materials metadata used to label rows. This script is the sole
bridge between ``knowledge/catalogs/blueprints.json`` and the packaged
projection; ``--check`` detects drift in tests and CI.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BLUEPRINTS = ROOT / "knowledge" / "catalogs" / "blueprints.json"
OUTPUT = ROOT / "backend" / "app" / "catalogs" / "blueprints-880.json"

SCHEMA = "sk-under/backend-blueprints@1"
EXPECTED_BLUEPRINTS = 265
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


def _text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.replace("\x00", "")
    text = "".join(char for char in text if char.isprintable()).strip()
    if not text:
        return None
    return text if len(text) <= MAX_TEXT else text[:MAX_TEXT] + "…"


def _name(item: dict) -> dict[str, str | None]:
    name = item.get("name")
    if not isinstance(name, dict):
        name = {}
    return {key: _text(name.get(key)) for key in ("en", "es")}


def _materials(item: dict) -> list[dict[str, object]]:
    relations = item.get("relations")
    rows = relations.get("research_materials") if isinstance(relations, dict) else None
    if not isinstance(rows, list):
        return []
    result: list[dict[str, object]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        item_id = _text(row.get("item"))
        num = row.get("num")
        if item_id is None or type(num) is not int or num < 0:
            continue
        result.append({"item": item_id, "num": num})
    return result


def build() -> dict:
    document = _load(BLUEPRINTS)
    if document.get("game_version") != "8.8.0":
        raise ProjectionError("El catálogo de planos no es de la versión 8.8.0")
    items = document["items"]
    if len(items) != EXPECTED_BLUEPRINTS:
        raise ProjectionError("El recuento de planos no coincide con el esperado")
    rows = []
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            raise ProjectionError("Fila de plano inválida")
        blueprint_id = item.get("id")
        if not isinstance(blueprint_id, str) or not blueprint_id.startswith("blueprint_"):
            raise ProjectionError("Plano con identificador inválido")
        if blueprint_id in seen:
            raise ProjectionError(f"Plano repetido: {blueprint_id}")
        seen.add(blueprint_id)
        attributes = item.get("attributes")
        attributes = attributes if isinstance(attributes, dict) else {}
        relations = item.get("relations")
        relations = relations if isinstance(relations, dict) else {}
        blueprint_type = attributes.get("blueprint_type")
        rows.append(
            {
                "id": blueprint_id,
                "name": _name(item),
                "subcategory": _text(item.get("subcategory")),
                "blueprint_type": blueprint_type if type(blueprint_type) is int else None,
                "target": _text(relations.get("target")),
                "research_materials": _materials(item),
            }
        )
    if len(rows) != EXPECTED_BLUEPRINTS:
        raise ProjectionError("La proyección de planos quedó incompleta")
    return {
        "schema": SCHEMA,
        "game_version": "8.8.0",
        "generated_by": "knowledge/tools/build_backend_blueprints.py",
        "source_refs": {"blueprints": "knowledge/catalogs/blueprints.json"},
        "counts": {"blueprints": len(rows)},
        "blueprints": rows,
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
#!/usr/bin/env python3
"""Generate the backend projection of editable item ids from the knowledge catalogs.

The frontend and backend must not maintain their own copies of item names or ids.
This script is the only bridge between knowledge/catalogs/{materials,seeds}.json and
the packaged backend catalog. Run with --check in tests/CI to detect drift.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MATERIALS = ROOT / "knowledge" / "catalogs" / "materials.json"
SEEDS = ROOT / "knowledge" / "catalogs" / "seeds.json"
OUTPUT = ROOT / "backend" / "app" / "catalogs" / "items-880.json"

SCHEMA = "sk-under/backend-items@1"
MATERIAL_FISH_REASON = "Es el espejo de gameData.fishChip; se edita desde el control de fichas de pesca."


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


def _name(item: dict) -> dict[str, str | None]:
    name = item.get("name")
    if not isinstance(name, dict):
        name = {}
    return {
        "en": name.get("en") if isinstance(name.get("en"), str) else None,
        "es": name.get("es") if isinstance(name.get("es"), str) else None,
    }


def _subcategory(item: dict) -> str | None:
    value = item.get("subcategory")
    return value if isinstance(value, str) and value else None


def build() -> dict:
    materials = _load(MATERIALS)
    seeds = _load(SEEDS)
    material_rows = []
    for item in materials["items"]:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str):
            raise ProjectionError("Material sin id")
        item_id = item["id"]
        editable = item_id != "material_fish"
        row = {
            "id": item_id,
            "name": _name(item),
            "subcategory": _subcategory(item),
            "insertable": editable,
            "editable": editable,
        }
        if not editable:
            row["reason"] = MATERIAL_FISH_REASON
        material_rows.append(row)
    seed_rows = []
    for item in seeds["items"]:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str):
            raise ProjectionError("Semilla sin id")
        attributes = item.get("attributes")
        plant_id = attributes.get("plant_id") if isinstance(attributes, dict) else None
        seed_rows.append({
            "id": item["id"],
            "name": _name(item),
            "subcategory": _subcategory(item),
            "insertable": True,
            "editable": True,
            "plant_id": plant_id if isinstance(plant_id, str) else None,
        })
    document = {
        "schema": SCHEMA,
        "game_version": materials.get("game_version", seeds.get("game_version")),
        "generated_by": "knowledge/tools/build_backend_items.py",
        "source_refs": {
            "materials": "knowledge/catalogs/materials.json",
            "seeds": "knowledge/catalogs/seeds.json",
        },
        "counts": {"materials": len(material_rows), "seeds": len(seed_rows)},
        "materials": material_rows,
        "seeds": seed_rows,
    }
    if document["counts"] != {
        "materials": materials.get("count"),
        "seeds": seeds.get("count"),
    }:
        raise ProjectionError("El recuento del catálogo no coincide con su contenido")
    return document


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
            print(f"Falta la proyección {OUTPUT}: {error}", file=sys.stderr)
            return 1
        if current != expected:
            print("La proyección de materiales/semillas está desactualizada.", file=sys.stderr)
            return 1
        print("Proyección de materiales/semillas actualizada.")
        return 0
    OUTPUT.write_text(expected, encoding="utf-8")
    print(f"Escrito {OUTPUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

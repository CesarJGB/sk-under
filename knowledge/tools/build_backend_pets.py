#!/usr/bin/env python3
"""Generate the backend projection of pets and pet-skin variants.

The backend must not maintain its own copy of pet codes, numeric ids or names.
This script is the only bridge between ``knowledge/catalogs/{pets,pet_skins}.json``
and the packaged projection. Run with ``--check`` in tests/CI to detect drift.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PETS = ROOT / "knowledge" / "catalogs" / "pets.json"
PETS_SKINS = ROOT / "knowledge" / "catalogs" / "pet_skins.json"
OUTPUT = ROOT / "backend" / "app" / "catalogs" / "pets-880.json"

SCHEMA = "sk-under/backend-pets@1"
EXPECTED_PETS = 58
EXPECTED_SKINS = 12


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


def build() -> dict:
    pets = _load(PETS)
    skins = _load(PETS_SKINS)
    pet_rows = []
    for item in pets["items"]:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str):
            raise ProjectionError("Mascota sin id")
        attributes = item.get("attributes")
        numeric_id = attributes.get("numeric_id") if isinstance(attributes, dict) else None
        if type(numeric_id) is not int:
            raise ProjectionError(f"{item['id']} no declara numeric_id")
        refs = item.get("save_refs")
        pet_rows.append(
            {
                "id": item["id"],
                "numeric_id": numeric_id,
                "name": _name(item),
                "save_ref": refs[0] if isinstance(refs, list) and refs else None,
            }
        )
    skin_rows = []
    for item in skins["items"]:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str):
            raise ProjectionError("Skin de mascota sin id")
        attributes = item.get("attributes")
        if not isinstance(attributes, dict):
            raise ProjectionError(f"{item['id']} no declara atributos")
        pet_code = attributes.get("pet_code")
        base_pet = attributes.get("base_pet")
        skin_index = attributes.get("skin_index")
        if not isinstance(pet_code, str) or not isinstance(base_pet, str) or type(skin_index) is not int:
            raise ProjectionError(f"{item['id']} declara una variante incompleta")
        skin_rows.append(
            {
                "id": item["id"],
                "pet_code": pet_code,
                "base_pet": base_pet,
                "skin_index": skin_index,
                "name": _name(item),
                "save_ref": f"gameData.petUnlock.{pet_code}",
            }
        )
    document = {
        "schema": SCHEMA,
        "game_version": pets.get("game_version", skins.get("game_version")),
        "generated_by": "knowledge/tools/build_backend_pets.py",
        "source_refs": {
            "pets": "knowledge/catalogs/pets.json",
            "pet_skins": "knowledge/catalogs/pet_skins.json",
        },
        "counts": {"pets": len(pet_rows), "pet_skins": len(skin_rows)},
        "pets": pet_rows,
        "pet_skins": skin_rows,
    }
    if document["counts"] != {"pets": EXPECTED_PETS, "pet_skins": EXPECTED_SKINS}:
        raise ProjectionError("El recuento de mascotas o skins no coincide con el esperado")
    if document["counts"]["pets"] != pets.get("count") or document["counts"]["pet_skins"] != skins.get("count"):
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
            print("La proyección de mascotas está desactualizada.", file=sys.stderr)
            return 1
        print("Proyección de mascotas actualizada.")
        return 0
    OUTPUT.write_text(expected, encoding="utf-8")
    print(f"Escrito {OUTPUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
"""Verificación de los catálogos incluidos durante la construcción de la imagen."""

from __future__ import annotations

import sys

from . import CATALOG_PATH, CharacterCatalogError, load_character_catalog, validate_character_catalog
from .items import ITEMS_PATH, ItemCatalogError, load_item_catalog, validate_item_catalog


def main() -> int:
    try:
        catalog = load_character_catalog()
        validate_character_catalog(catalog)
        items = load_item_catalog()
        validate_item_catalog(items)
    except CharacterCatalogError as exc:
        print(f"ERROR [{exc.code}] {exc}", file=sys.stderr)
        return 1
    except ItemCatalogError as exc:
        print(f"ERROR [{exc.code}] {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"ERROR [catalog_unreadable] {exc}", file=sys.stderr)
        return 1
    print(
        "Catálogo de personajes válido: "
        f"{len(catalog['codes'])} personajes, "
        f"{len(catalog['skills'])} habilidades y "
        f"{sum(len(group) for group in catalog['skins'].values())} skins "
        f"({catalog['version']}, {CATALOG_PATH})."
    )
    print(
        "Catálogo de materiales y semillas válido: "
        f"{len(items['material_ids'])} materiales y "
        f"{len(items['seed_ids'])} semillas "
        f"({items['version']}, {ITEMS_PATH})."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
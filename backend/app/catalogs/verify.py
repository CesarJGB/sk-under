"""Verificación del catálogo de personajes durante la construcción de la imagen."""

from __future__ import annotations

import sys

from . import CATALOG_PATH, CharacterCatalogError, load_character_catalog, validate_character_catalog


def main() -> int:
    try:
        catalog = load_character_catalog()
        validate_character_catalog(catalog)
    except CharacterCatalogError as exc:
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
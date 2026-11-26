"""Verificación de los catálogos incluidos durante la construcción de la imagen."""

from __future__ import annotations

import sys

from . import CATALOG_PATH, CharacterCatalogError, load_character_catalog, validate_character_catalog
from .blueprints import (
    BLUEPRINTS_PATH,
    BlueprintCatalogError,
    load_blueprint_catalog,
    validate_blueprint_catalog,
)
from .items import ITEMS_PATH, ItemCatalogError, load_item_catalog, validate_item_catalog
from .kill_effects import (
    KILL_EFFECTS_PATH,
    KillEffectCatalogError,
    load_kill_effect_catalog,
    validate_kill_effect_catalog,
)
from .pets import PETS_PATH, PetCatalogError, load_pet_catalog, validate_pet_catalog
from .weapon_skins import (
    WEAPON_SKINS_PATH,
    WeaponSkinCatalogError,
    load_weapon_skin_catalog,
    validate_weapon_skin_catalog,
)


def main() -> int:
    try:
        catalog = load_character_catalog()
        validate_character_catalog(catalog)
        items = load_item_catalog()
        validate_item_catalog(items)
        pets = load_pet_catalog()
        validate_pet_catalog(pets)
        blueprints = load_blueprint_catalog()
        validate_blueprint_catalog(blueprints)
        weapon_skins = load_weapon_skin_catalog()
        validate_weapon_skin_catalog(weapon_skins)
        kill_effects = load_kill_effect_catalog()
        validate_kill_effect_catalog(kill_effects)
    except CharacterCatalogError as exc:
        print(f"ERROR [{exc.code}] {exc}", file=sys.stderr)
        return 1
    except ItemCatalogError as exc:
        print(f"ERROR [{exc.code}] {exc}", file=sys.stderr)
        return 1
    except PetCatalogError as exc:
        print(f"ERROR [{exc.code}] {exc}", file=sys.stderr)
        return 1
    except BlueprintCatalogError as exc:
        print(f"ERROR [{exc.code}] {exc}", file=sys.stderr)
        return 1
    except WeaponSkinCatalogError as exc:
        print(f"ERROR [{exc.code}] {exc}", file=sys.stderr)
        return 1
    except KillEffectCatalogError as exc:
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
    print(
        "Catálogo de mascotas válido: "
        f"{len(pets['pet_ids'])} mascotas y {len(pets['skin_ids'])} variantes "
        f"({pets['version']}, {PETS_PATH})."
    )
    print(
        "Catálogo de planos válido: "
        f"{len(blueprints['blueprint_ids'])} planos "
        f"({blueprints['version']}, {BLUEPRINTS_PATH})."
    )
    print(
        "Catálogo de skins de arma válido: "
        f"{weapon_skins['counts']['skins']} skins en "
        f"{weapon_skins['counts']['weapons']} armas "
        f"({weapon_skins['version']}, {WEAPON_SKINS_PATH})."
    )
    print(
        "Catálogo de efectos de eliminación válido: "
        f"{kill_effects['counts']['effects']} efectos "
        f"({kill_effects['version']}, {KILL_EFFECTS_PATH})."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
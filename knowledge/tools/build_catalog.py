#!/usr/bin/env python3
"""Genera los catálogos normalizados del Save Knowledge Engine.

La fuente principal es una copia local del repositorio SKDFE en el commit
8.8.0. El script no descarga nada, no se autentica y no escribe guardados:
solo transforma catálogos estáticos en artefactos normalizados con procedencia.

Uso:
    python3 knowledge/tools/build_catalog.py --skdfe /ruta/a/skdfe
    python3 knowledge/tools/build_catalog.py --skdfe /ruta/a/skdfe --check
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sk_knowledge import common  # noqa: E402
from sk_knowledge.common import (  # noqa: E402
    CATALOG_SCHEMA,
    CATALOGS_DIR,
    DIFF_SCHEMA,
    EVIDENCE_LEVELS,
    KNOWLEDGE_DIR,
    TRANSLATIONS_DIR,
    VERSION_DIFFS_DIR,
    catalog_document,
    ensure_unique_ids,
    normalize_id,
    read_json,
    sha256_bytes,
    source_ref,
    write_json,
)

DEFAULT_SKDFE = Path("/tmp/sk-under-6111-skdfe")
VERSION_COMMITS = {
    "8.6.0": "e088a67",
    "8.7.0": "8cfa5d5",
    "8.8.0": "57b9b86335c080caca55e178c8409cb67658ccf6",
}
LICENSE_NOTE = (
    "SKDFE no incluye archivo de licencia en el commit consultado. "
    "SK-Under conserva solo identificadores, nombres normalizados, recuentos y "
    "relaciones factuales con procedencia; no redistribuye CSV, texto de la wiki, "
    "sprites ni volcados completos."
)

I2_FIELDS = ("English", "Spanish", "Chinese (Simplified)")


def load_i2(path: Path) -> dict[str, dict[str, str | None]]:
    result: dict[str, dict[str, str | None]] = {}
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            key = (row.get("id") or "").strip()
            if not key:
                continue
            result[key] = {
                "en": common.stringify_name(row.get("English")),
                "es": common.stringify_name(row.get("Spanish")),
                "zh_cn": common.stringify_name(row.get("Chinese (Simplified)")),
            }
    return result


def load_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return [row for row in csv.DictReader(handle) if row.get("Key") != "string"]


def name_from_i2(
    i2: dict[str, dict[str, str | None]], *keys: str
) -> dict[str, str | None]:
    for key in keys:
        entry = i2.get(key)
        if entry and (entry.get("en") or entry.get("es") or entry.get("zh_cn")):
            return dict(entry)
    return {"en": None, "es": None, "zh_cn": None}


def name_from_needed(
    value: str | None,
    i2: dict[str, dict[str, str | None]],
    key: str,
) -> dict[str, str | None]:
    entry = name_from_i2(i2, key)
    if value and not entry["en"]:
        entry["en"] = value
    return entry


def parse_json(value: str, default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default


def item_source(commit: str, path: str) -> str:
    return f"SKDFE@{commit}:{path}"


def make_item(
    item_id: str,
    name: dict[str, str | None],
    category: str,
    *,
    subcategory: str | None = None,
    attributes: dict[str, Any] | None = None,
    relations: dict[str, Any] | None = None,
    save_refs: Iterable[str] = (),
    evidence: str = "E1",
    source: str,
    notes: Iterable[str] = (),
) -> dict[str, Any]:
    return {
        "id": item_id,
        "name": name,
        "category": category,
        "subcategory": subcategory,
        "attributes": attributes or {},
        "relations": relations or {},
        "save_refs": sorted(set(save_refs)),
        "notes": list(notes),
        "evidence": evidence,
        "source": source,
    }


def build_characters(
    codes: list[str],
    needed: dict[str, Any],
    i2: dict[str, dict[str, str | None]],
    highest: dict[str, int],
    commit: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    skills_by_char: dict[int, list[tuple[int, str]]] = defaultdict(list)
    for key in needed.get("character_skill", {}):
        match = re.fullmatch(r"Character(\d+)_skill_(\d+)_name", key)
        if match:
            skills_by_char[int(match.group(1))].append((int(match.group(2)), key))

    skins_by_char: dict[int, list[tuple[int, str]]] = defaultdict(list)
    for group, entries in needed.get("skin", {}).items():
        group_match = re.fullmatch(r"c(\d+)", group)
        if not group_match:
            continue
        character_index = int(group_match.group(1))
        for key in entries:
            skin_match = re.fullmatch(rf"c{character_index}_skin(\d+)", key)
            if skin_match:
                skins_by_char[character_index].append((int(skin_match.group(1)), key))

    characters: list[dict[str, Any]] = []
    skills: list[dict[str, Any]] = []
    skins: list[dict[str, Any]] = []
    for index, code in enumerate(codes):
        char_skills = sorted(skills_by_char.get(index, []))
        char_skins = sorted(skins_by_char.get(index, []))
        base_name = name_from_i2(i2, f"Character{index}_name_skin0")
        if not base_name["en"]:
            base_name["en"] = code
        character = make_item(
            code,
            base_name,
            "character",
            subcategory="playable",
            attributes={
                "index": index,
                "code": code,
                "max_skin_index": highest.get(f"c{index}"),
                "skill_count": len(char_skills),
                "skin_count": len(char_skins),
                "base_skin_key": f"c{index}_skin0" if char_skins else None,
            },
            relations={
                "character_skills": [key for _, key in char_skills],
                "character_skins": [key for _, key in char_skins],
            },
            save_refs=[
                f"gameData.heroUnlock.{code}",
                f"gameData.heroLevel.{code}",
                f"gameData.heroSkill.{code}",
                f"gameData.heroSkillUnlock.{code}",
                f"gameData.skinLock.{code}",
                f"gameData.currentSkinDatas.{code}",
            ],
            source=item_source(commit, "char_code_name.json"),
            notes=["El código interno y el nombre visible pueden diferir."],
        )
        characters.append(character)

        for slot, key in char_skills:
            skill_name = name_from_i2(i2, key)
            skills.append(
                make_item(
                    key,
                    skill_name,
                    "character_skill",
                    subcategory="active_or_passive_slot",
                    attributes={
                        "character": code,
                        "character_index": index,
                        "slot": slot,
                    },
                    relations={"character": code},
                    save_refs=[
                        f"gameData.heroSkill.{code}",
                        f"gameData.heroSkillUnlock.{code}[{slot}]",
                    ],
                    source=item_source(commit, "needed_data.json"),
                )
            )

        for skin_index, key in char_skins:
            skin_name = name_from_i2(
                i2, f"Character{index}_name_skin{skin_index}", key
            )
            skins.append(
                make_item(
                    key,
                    skin_name,
                    "character_skin",
                    subcategory="character",
                    attributes={
                        "character": code,
                        "character_index": index,
                        "skin_index": skin_index,
                    },
                    relations={"character": code},
                    save_refs=[f"gameData.skinLock.{code}[{skin_index}]"],
                    source=item_source(commit, "needed_data.json"),
                )
            )
    return characters, skills, skins


def build_pets(
    codes: list[str],
    needed: dict[str, Any],
    i2: dict[str, dict[str, str | None]],
    commit: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    pet_names: dict[str, str] = needed.get("pet", {})
    numeric_ids = sorted({int(key) for key in pet_names} | set(range(len(codes))) | {57})
    # El código 57 no está en pet_code_name.json, pero sí aparece como
    # ``FishChipKing`` en gameData.petUnlock de guardados y nube reales.
    code_overrides = {57: "FishChipKing"}
    pets: list[dict[str, Any]] = []
    for numeric_id in numeric_ids:
        code = code_overrides.get(numeric_id)
        if code is None and numeric_id < len(codes):
            code = codes[numeric_id]
        name = name_from_i2(i2, f"Pet_name_{numeric_id}")
        if not name["en"]:
            name["en"] = pet_names.get(str(numeric_id))
        pets.append(
            make_item(
                code or f"pet_id_{numeric_id}",
                name,
                "pet",
                subcategory="companion",
                attributes={
                    "numeric_id": numeric_id,
                    "code": code,
                    "has_config_name": pet_names.get(str(numeric_id)) is not None,
                    "has_code": code is not None,
                },
                relations={
                    "skills": [
                        re.sub(r"_name$", "", key)
                        for key in i2
                        if re.fullmatch(rf"pet_{numeric_id}_skill_\d+_name", key)
                    ]
                },
                save_refs=[f"gameData.petUnlock.{code}"] if code else [],
                source=item_source(
                    commit,
                    "needed_data.json" if numeric_id == 57 else "pet_code_name.json",
                ),
                notes=(
                    ["Identificador numérico sin nombre en needed_data.json."]
                    if not pet_names.get(str(numeric_id))
                    else []
                ),
            )
        )

    skills: list[dict[str, Any]] = []
    skill_names: dict[tuple[int, int], dict[str, str | None]] = {}
    for key in i2:
        match = re.fullmatch(r"pet_(\d+)_skill_(\d+)_name", key)
        if match:
            skill_names[(int(match.group(1)), int(match.group(2)))] = name_from_i2(i2, key)
    for (numeric_id, slot), name in sorted(skill_names.items()):
        description = name_from_i2(i2, f"pet_{numeric_id}_skill_{slot}_desc")
        code = "FishChipKing" if numeric_id == 57 else (
            codes[numeric_id] if numeric_id < len(codes) else None
        )
        skills.append(
            make_item(
                f"pet_{numeric_id}_skill_{slot}",
                name,
                "pet_skill",
                subcategory="pet_skill",
                attributes={
                    "pet_numeric_id": numeric_id,
                    "pet_code": code,
                    "slot": slot,
                    "description_en": description["en"],
                    "description_es": description["es"],
                },
                relations={"pet": code or f"pet_id_{numeric_id}"},
                source=item_source(commit, "I2language.csv"),
            )
        )
    return pets, skills


def build_pet_skins(
    pets: list[dict[str, Any]],
    i2: dict[str, dict[str, str | None]],
    commit: str,
) -> list[dict[str, Any]]:
    """Variantes de mascota observadas en el mismo mapa petUnlock.

    No se encontró un mapa de bloqueo específico de skins de mascota ni una
    clave de PlayerPrefs equivalente a ``skinLock``. Las variantes Cat1..Cat7,
    Dog1..Dog3, Pig1 y Rabbit1 se catalogan como candidatas E2: su desbloqueo
    se lee y escribe en ``gameData.petUnlock.<variante>``. El catálogo no
    afirma que sean la única representación posible de una skin.
    """
    skins: list[dict[str, Any]] = []
    for pet in pets:
        pet_id = pet.get("id")
        match = re.fullmatch(r"(Cat|Dog|Pig|Rabbit)(\d+)", pet_id or "")
        if not match:
            continue
        base = match.group(1)
        index = int(match.group(2))
        skins.append(
            make_item(
                pet_id,
                pet["name"],
                "pet_skin",
                subcategory="pet_variant",
                attributes={
                    "pet_code": pet_id,
                    "base_pet": base,
                    "skin_index": index,
                    "numeric_id": pet["attributes"].get("numeric_id"),
                },
                relations={"pet": base},
                save_refs=[f"gameData.petUnlock.{pet_id}"],
                evidence="E2",
                source=item_source(commit, "needed_data.json"),
                notes=[
                    "Variante de mascota agrupada por prefijo; no se halló un mapa de bloqueo de skins separado.",
                    "El desbloqueo se comparte con gameData.petUnlock.<variante>.",
                ],
            )
        )
    return skins


def build_weapons(
    weapon_full: list[dict[str, Any]],
    csv_rows: list[dict[str, str]],
    i2: dict[str, dict[str, str | None]],
    commit: str,
) -> list[dict[str, Any]]:
    csv_by_key = {row["Key"]: row for row in csv_rows}
    catalog_names = {entry["name"] for entry in weapon_full}
    items: list[dict[str, Any]] = []

    for entry in weapon_full:
        key = str(entry.get("name", "")).strip()
        if not key:
            continue
        csv_row = csv_by_key.get(key)
        name = name_from_i2(i2, f"weapon/{key}")
        zh = common.stringify_name(entry.get("title"))
        if not name["en"] and zh:
            name["zh_cn"] = zh
        materials = parse_json(csv_row.get("Materials", ""), []) if csv_row else []
        fusion = parse_json(csv_row.get("FusionList", ""), []) if csv_row else []
        talents = parse_json(csv_row.get("TalentList", ""), []) if csv_row else []
        fusion_sources: list[str] = []
        fusion_targets: list[str] = []
        for rule in fusion if isinstance(fusion, list) else []:
            if not isinstance(rule, dict):
                continue
            for source in rule.get("sourceWeapons", []) or []:
                if isinstance(source, dict) and source.get("weapon"):
                    fusion_sources.append(str(source["weapon"]))
            target = rule.get("targetWeapon")
            if isinstance(target, dict) and target.get("weapon"):
                fusion_targets.append(str(target["weapon"]))
        items.append(
            make_item(
                key,
                name,
                "weapon",
                subcategory=common.stringify_name(entry.get("type")),
                attributes={
                    "level": entry.get("level"),
                    "tags": entry.get("tags") or [],
                    "forgeable": entry.get("forgeable"),
                    "drop_level": entry.get("dropLevel"),
                    "is_melee": entry.get("isMelle"),
                    "cant_exchange_by_token": entry.get("cantExchangeByToken"),
                    "in_weapon_catalog": True,
                    "config_only": False,
                    "price": int(csv_row["Price"]) if csv_row and csv_row.get("Price", "").lstrip("-").isdigit() else None,
                    "original_weapon_raw": common.stringify_name(csv_row.get("OriginalWeapon") if csv_row else None),
                    "support_items": parse_json(csv_row.get("SupportItems", ""), []) if csv_row else [],
                    "decided_by_weapon_config": csv_row.get("DecidedByWeaponConfig") if csv_row else None,
                },
                relations={
                    "materials": [
                        {"item": item.get("item"), "num": item.get("num")}
                        for item in materials
                        if isinstance(item, dict)
                    ],
                    "fusion_sources": sorted(set(fusion_sources)),
                    "fusion_targets": sorted(set(fusion_targets)),
                    "talents": [
                        talent.get("talentName")
                        for talent in talents
                        if isinstance(talent, dict) and talent.get("talentName")
                    ],
                },
                save_refs=[
                    f"weaponEvolutionData.weapons.{key}",
                    f"itemData.forgeWeapons.{key}",
                ],
                source=item_source(commit, "weapon_full.json"),
                notes=(["Sin nombre inglés/español en I2language.csv; se conserva el título chino."] if not name["en"] else []),
            )
        )

    for row in csv_rows:
        key = row["Key"]
        if key in catalog_names:
            continue
        name = name_from_i2(i2, f"weapon/{key}")
        materials = parse_json(row.get("Materials", ""), [])
        fusion = parse_json(row.get("FusionList", ""), [])
        items.append(
            make_item(
                key,
                name,
                "weapon",
                subcategory="config_only",
                attributes={
                    "in_weapon_catalog": False,
                    "config_only": True,
                    "price": int(row["Price"]) if row.get("Price", "").lstrip("-").isdigit() else None,
                    "original_weapon_raw": common.stringify_name(row.get("OriginalWeapon")),
                    "decided_by_weapon_config": row.get("DecidedByWeaponConfig"),
                },
                relations={
                    "materials": [
                        {"item": item.get("item"), "num": item.get("num")}
                        for item in materials
                        if isinstance(item, dict)
                    ],
                    "fusion_targets": [
                        str((rule.get("targetWeapon") or {}).get("weapon"))
                        for rule in (fusion if isinstance(fusion, list) else [])
                        if isinstance(rule, dict) and isinstance(rule.get("targetWeapon"), dict)
                    ],
                },
                source=item_source(commit, "weapons.decrypted.csv"),
                notes=["Fila de weapons.decrypted.csv sin entrada en weapon_full.json (transformación, anillo o variante interna)."],
            )
        )
    return items


def build_weapon_skins(
    needed: dict[str, Any],
    i2: dict[str, dict[str, str | None]],
    commit: str,
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for key, fallback_name in needed.get("weapon_skin", {}).items():
        match = re.fullmatch(r"weapon_(.+)_s_(\d+)", key)
        weapon_id = f"weapon_{match.group(1)}" if match else None
        skin_index = int(match.group(2)) if match else None
        name = name_from_needed(fallback_name, i2, key)
        items.append(
            make_item(
                key,
                name,
                "weapon_skin",
                subcategory="weapon",
                attributes={"weapon_id": weapon_id, "skin_index": skin_index},
                relations={"weapon": weapon_id} if weapon_id else {},
                save_refs=(
                    [
                        f"weaponEvolutionData.weapons.{weapon_id}.UnlockedSkins[{skin_index}]",
                        f"weaponEvolutionData.weapons.{weapon_id}.CurrentSkinIndex",
                    ]
                    if weapon_id
                    else []
                ),
                source=item_source(commit, "needed_data.json"),
            )
        )
    return items


def build_materials(
    item_groups: dict[str, list[str]],
    needed: dict[str, Any],
    csv_by_key: dict[str, dict[str, str]],
    i2: dict[str, dict[str, str | None]],
    commit: str,
) -> list[dict[str, Any]]:
    needed_materials: dict[str, str] = needed.get("material", {})
    all_ids = sorted(set(needed_materials) | {key for ids in item_groups.values() for key in ids})
    group_by_id = {
        item_id: group for group, ids in item_groups.items() for item_id in ids
    }
    items: list[dict[str, Any]] = []
    for item_id in all_ids:
        row = csv_by_key.get(item_id)
        name = name_from_needed(needed_materials.get(item_id), i2, item_id)
        if not name["en"]:
            name = name_from_i2(i2, item_id, f"item/{item_id}")
        data = parse_json(row.get("DataStr", ""), {}) if row else {}
        items.append(
            make_item(
                item_id,
                name,
                "material",
                subcategory=group_by_id.get(item_id),
                attributes={
                    "item_group": group_by_id.get(item_id),
                    "in_needed_data": item_id in needed_materials,
                    "csv_type": row.get("Type") if row else None,
                    "csv_subtype": row.get("SubType") if row else None,
                    "item_value": data.get("ItemValue") if isinstance(data, dict) else None,
                    "item_level": data.get("ItemLevel") if isinstance(data, dict) else None,
                },
                save_refs=[
                    f"itemData.materials.{item_id}",
                    f"itemData.commodities.{item_id}",
                ],
                source=item_source(commit, "item.json"),
                notes=(["Sin nombre en needed_data.json ni I2language.csv."] if not name["en"] else []),
            )
        )
    return items


def build_seeds_and_plants(
    plant_keys: list[str],
    i2: dict[str, dict[str, str | None]],
    commit: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    seeds: list[dict[str, Any]] = []
    plants: list[dict[str, Any]] = []
    for seed_id in sorted(plant_keys):
        stem = seed_id.removeprefix("plant_").removesuffix("_seed")
        plant_id = f"plant_{stem}"
        plant_name = name_from_i2(i2, plant_id)
        seed_name = name_from_i2(i2, seed_id)
        display = seed_name if seed_name["en"] else dict(plant_name)
        seeds.append(
            make_item(
                seed_id,
                display,
                "seed",
                subcategory="garden_seed",
                attributes={
                    "plant_id": plant_id,
                    "seed_translation_available": bool(seed_name["en"]),
                },
                relations={"plant": plant_id},
                save_refs=[f"itemData.seeds.{seed_id}"],
                source=item_source(commit, "item.json"),
                notes=(["El nombre mostrado procede de la planta; no hay traducción propia para la semilla."] if not seed_name["en"] else []),
            )
        )
        plants.append(
            make_item(
                plant_id,
                plant_name,
                "plant",
                subcategory="garden",
                attributes={"seed_item": seed_id},
                relations={"seed": seed_id},
                save_refs=["itemData.plants", f"gameData.roomLevel.{plant_id}"],
                source=item_source(commit, "I2language.csv"),
            )
        )
    return seeds, plants


def build_blueprints(
    blueprint_groups: dict[str, list[str]],
    csv_by_key: dict[str, dict[str, str]],
    i2: dict[str, dict[str, str | None]],
    commit: str,
) -> list[dict[str, Any]]:
    group_by_id = {
        item_id: group for group, ids in blueprint_groups.items() for item_id in ids
    }
    items: list[dict[str, Any]] = []
    for item_id in sorted(csv_by_key):
        row = csv_by_key[item_id]
        if row.get("Type") != "BluePrint":
            continue
        data = parse_json(row.get("DataStr", ""), {})
        if not isinstance(data, dict):
            data = {}
        localization = common.stringify_name(data.get("Localization"))
        name = name_from_i2(
            i2,
            localization or "",
            item_id,
            f"item/{item_id}",
        )
        target = common.stringify_name(data.get("ItemName"))
        materials = data.get("ResearchMaterials") or []
        items.append(
            make_item(
                item_id,
                name,
                "blueprint",
                subcategory=group_by_id.get(item_id),
                attributes={
                    "blueprint_type": data.get("BlueprintType"),
                    "item_name": target,
                    "blueprint_level": data.get("BluePrintLevel"),
                    "weapon_drop_level": data.get("WeaponDropLevel"),
                    "hero": data.get("Hero"),
                    "skin_index": data.get("SkinIndex"),
                    "skill_index": data.get("SkillIndex"),
                    "not_required_in_research": data.get("NotRequiredInResearch"),
                    "need_record_consume": data.get("NeedRecordConsume"),
                },
                relations={
                    "target": target,
                    "research_materials": [
                        {"item": entry.get("item"), "num": entry.get("num")}
                        for entry in materials
                        if isinstance(entry, dict)
                    ],
                },
                save_refs=[f"itemData.blueprints.{item_id}"],
                source=item_source(commit, "items.decrypted.csv"),
                notes=(["Sin nombre en I2language.csv; se conserva la clave y su objetivo."] if not name["en"] else []),
            )
        )
    return items


def build_enemies(
    csv_rows: list[dict[str, str]],
    i2: dict[str, dict[str, str | None]],
    commit: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    enemies: list[dict[str, Any]] = []
    bosses: list[dict[str, Any]] = []
    for row in csv_rows:
        if not row.get("Key"):
            continue
        key = row["Key"]
        name = name_from_i2(i2, key, f"e_{key}")
        drops = parse_json(row.get("Drops", ""), [])
        drop_ids: list[dict[str, Any]] = []
        for drop in drops if isinstance(drops, list) else []:
            if not isinstance(drop, dict):
                continue
            item = drop.get("item")
            item_id = item.get("item") if isinstance(item, dict) else item
            if item_id:
                drop_ids.append({"item": item_id, "probability": drop.get("probability")})
        is_boss = str(row.get("IsBoss", "")).lower() == "true"
        enemy = make_item(
            key,
            name,
            "enemy",
            subcategory="boss" if is_boss else "enemy",
            attributes={
                "path": common.stringify_name(row.get("Path")),
                "asset_bundle": common.stringify_name(row.get("AssetBundle")),
                "level_key": common.stringify_name(row.get("LevelKey")),
                "enemy_id": common.stringify_name(row.get("EnemyId")),
                "is_boss": is_boss,
                "hp": row.get("Hp"),
                "speed": row.get("Speed"),
                "speed_rate": row.get("SpeedRate"),
                "critical": row.get("Critical"),
                "subspecies_boss": common.stringify_name(row.get("SubspeciesBoss")),
                "double_bosses": common.stringify_name(row.get("DoubleBosses")),
            },
            relations={"drops": drop_ids},
            source=item_source(commit, "enemies.decrypted.csv"),
        )
        enemies.append(enemy)
        if is_boss:
            bosses.append(
                make_item(
                    key,
                    dict(name),
                    "boss",
                    subcategory="enemy",
                    attributes={"enemy_id": key},
                    relations={"enemy": key},
                    source=item_source(commit, "enemies.decrypted.csv"),
                )
            )
    return enemies, bosses


def build_lobby(
    data: dict[str, Any],
    i2: dict[str, dict[str, str | None]],
    commit: str,
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for furniture_id in data.get("furniture", []):
        items.append(
            make_item(
                furniture_id,
                name_from_i2(i2, furniture_id, f"object/{furniture_id}"),
                "lobby",
                subcategory="room_unlock_flag",
                attributes={"kind": "room_unlock_flag", "expected_minimum": 1},
                save_refs=[f"statisticData.event2Count.{furniture_id}"],
                evidence="E2",
                source=item_source(commit, "data.json"),
                notes=[
                    "Identificador observado en una muestra externa con forma de guardado; la ruta de guardado se confirmó en las muestras A y C de la fase 9.2.",
                    "La presencia de la bandera correlaciona con la disponibilidad funcional del vestíbulo; la eficacia de escribirla no está validada en juego.",
                ],
            )
        )
    for unlock_id in data.get("itemUnlock", []):
        items.append(
            make_item(
                unlock_id,
                name_from_i2(i2, unlock_id, f"item/{unlock_id}"),
                "lobby",
                subcategory="item_unlock",
                attributes={"kind": "item_unlock", "observed_in_reference_sample": True},
                save_refs=["itemData.itemUnlock"],
                source=item_source(commit, "data.json"),
            )
        )
    for key in sorted(i2):
        if key.startswith("multi_room_skin_name_"):
            index = key.rsplit("_", 1)[-1]
            items.append(
                make_item(
                    f"room_skin_{index}",
                    name_from_i2(i2, key),
                    "lobby",
                    subcategory="room_skin",
                    attributes={"kind": "room_skin", "index": index},
                    save_refs=["gameData.currentRoomDecorate", "gameData.roomLevel"],
                    source=item_source(commit, "I2language.csv"),
                )
            )
        elif key.startswith("garden_skin_name_"):
            index = key.rsplit("_", 1)[-1]
            items.append(
                make_item(
                    f"garden_skin_{index}",
                    name_from_i2(i2, key),
                    "lobby",
                    subcategory="garden_skin",
                    attributes={"kind": "garden_skin", "index": index},
                    save_refs=["gameData.currentRoomDecorate", "gameData.roomLevel"],
                    source=item_source(commit, "I2language.csv"),
                )
            )
    return items


def build_simple_reference_items(
    values: Iterable[str | int],
    category: str,
    subcategory: str,
    i2: dict[str, dict[str, str | None]],
    commit: str,
    *,
    keys: tuple[str, ...] = (),
    save_refs: Iterable[str] = (),
    prefix: str = "",
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for value in values:
        raw = str(value)
        item_id = f"{prefix}{raw}"
        items.append(
            make_item(
                item_id,
                name_from_i2(i2, *[f"{key}{raw}" for key in keys]),
                category,
                subcategory=subcategory,
                attributes={"raw_id": raw},
                save_refs=save_refs,
                source=item_source(commit, "data.json"),
            )
        )
    return items


def build_reference_catalogs(
    data: dict[str, Any],
    item_json: dict[str, Any],
    csv_by_key: dict[str, dict[str, str]],
    i2: dict[str, dict[str, str | None]],
    commit: str,
) -> dict[str, list[dict[str, Any]]]:
    catalogs: dict[str, list[dict[str, Any]]] = {}

    tokens: list[dict[str, Any]] = []
    for token_id in item_json.get("token", []):
        row = csv_by_key.get(token_id)
        data_obj = parse_json(row.get("DataStr", ""), {}) if row else {}
        tokens.append(
            make_item(
                token_id,
                name_from_i2(i2, f"item/{token_id}", token_id),
                "token",
                subcategory="ticket_or_token",
                attributes={
                    "token_type": data_obj.get("TokenType") if isinstance(data_obj, dict) else None,
                    "item_value": data_obj.get("ItemValue") if isinstance(data_obj, dict) else None,
                },
                save_refs=["itemData.tokenTickets", "itemData.specialTickets"],
                source=item_source(commit, "item.json"),
            )
        )
    catalogs["tokens"] = tokens

    specials: list[dict[str, Any]] = []
    for item_id in item_json.get("active", []) + item_json.get("others", []):
        specials.append(
            make_item(
                item_id,
                name_from_i2(i2, f"item/{item_id}", item_id),
                "special_item",
                subcategory="active_or_other",
                save_refs=["itemData.commodities", "itemData.specialTickets"],
                source=item_source(commit, "item.json"),
            )
        )
    for item_id in item_json.get("customization", {}).get("kill_effect", []):
        specials.append(
            make_item(
                item_id,
                name_from_i2(i2, f"{item_id}_name", f"item/{item_id}", item_id),
                "special_item",
                subcategory="kill_effect",
                save_refs=["itemData.commodities"],
                source=item_source(commit, "item.json"),
            )
        )
    catalogs["special_items"] = specials

    vouchers: list[dict[str, Any]] = []
    for group, values in (data.get("token") or {}).items():
        if not isinstance(values, list):
            continue
        for value in values:
            raw = str(value)
            vouchers.append(
                make_item(
                    f"{group}:{raw}",
                    name_from_i2(i2, f"item/{raw}", raw),
                    "voucher",
                    subcategory=group,
                    attributes={"voucher_group": group, "raw_id": raw, "observed_in_reference_sample": True},
                    save_refs=["itemData.tokenTickets", "itemData.commodities"],
                    source=item_source(commit, "data.json"),
                    notes=["El valor aparece en una muestra externa con forma de guardado; el catálogo no prueba posesión."],
                )
            )
    catalogs["vouchers"] = vouchers

    jewelry = []
    for raw_id, payload in sorted((data.get("jewelryData") or {}).items()):
        jewelry.append(
            make_item(
                raw_id,
                name_from_i2(i2, f"jewelry/{raw_id}", f"item/{raw_id}", raw_id),
                "jewelry",
                subcategory="accessory",
                attributes={
                    "observed_in_reference_sample": True,
                    "sample_durability": payload.get("durability") if isinstance(payload, dict) else None,
                    "sample_rune1": payload.get("rune1") if isinstance(payload, dict) else None,
                    "sample_rune2": payload.get("rune2") if isinstance(payload, dict) else None,
                },
                save_refs=[f"itemData.jewelryData.{raw_id}"],
                source=item_source(commit, "data.json"),
            )
        )
    catalogs["jewelry"] = jewelry

    chips = []
    for payload in data.get("chips", []):
        if not isinstance(payload, dict) or not payload.get("chipName"):
            continue
        raw = str(payload["chipName"])
        chip_name = name_from_i2(i2, f"chip/{raw}", f"chip_{raw}", raw)
        if not chip_name["en"]:
            chip_name["en"] = raw
        chips.append(
            make_item(
                raw,
                chip_name,
                "chip",
                subcategory="monster_rise_chip",
                attributes={
                    "observed_in_reference_sample": True,
                    "sample_level": payload.get("level"),
                    "sample_refine_level": payload.get("refineLevel"),
                },
                save_refs=["monsterRiseData", "statisticData"],
                source=item_source(commit, "data.json"),
                notes=["No confundir con seasonData.chips, que representa fichas de temporada."],
            )
        )
    catalogs["chips"] = chips

    mounts = []
    for payload in (data.get("mountData") or {}).get("mountList", []):
        if not isinstance(payload, dict) or not payload.get("id"):
            continue
        raw = str(payload["id"])
        mounts.append(
            make_item(
                raw,
                name_from_i2(i2, f"mount/{raw}/name", f"mount/{raw}", raw),
                "mount",
                subcategory="mount",
                attributes={
                    "observed_in_reference_sample": True,
                    "sample_index": payload.get("index"),
                    "sample_level": payload.get("level"),
                    "sample_selected": raw == (data.get("mountData") or {}).get("curSelectMount"),
                },
                save_refs=["monsterRiseData", "statisticData"],
                source=item_source(commit, "data.json"),
            )
        )
    catalogs["mounts"] = mounts

    followers = []
    for payload in (data.get("slaveData") or {}).get("followerList", []):
        if not isinstance(payload, dict) or not payload.get("followerConfigId"):
            continue
        raw = str(payload["followerConfigId"])
        followers.append(
            make_item(
                raw,
                name_from_i2(i2, f"follower/{raw}", f"follower/{raw}/name", raw),
                "follower",
                subcategory="follower",
                attributes={
                    "observed_in_reference_sample": True,
                    "sample_level": payload.get("level"),
                },
                save_refs=["monsterRiseData", "statisticData"],
                source=item_source(commit, "data.json"),
            )
        )
    catalogs["followers"] = followers

    trophies = []
    for raw_id, value in sorted((data.get("visualtrophy") or {}).items()):
        trophies.append(
            make_item(
                f"visual:{raw_id}",
                name_from_i2(i2, raw_id),
                "trophy",
                subcategory="visual",
                attributes={"observed_in_reference_sample": True, "sample_value": value},
                save_refs=["statisticData"],
                source=item_source(commit, "data.json"),
            )
        )
    for group in ("aramtrophy", "irontrophy"):
        for raw_id in sorted((data.get(group) or {})):
            trophies.append(
                make_item(
                    f"{group}:{raw_id}",
                    name_from_i2(i2, raw_id),
                    "trophy",
                    subcategory=group,
                    attributes={"observed_in_reference_sample": True},
                    save_refs=["statisticData"],
                    source=item_source(commit, "data.json"),
                )
            )
    catalogs["trophies"] = trophies

    season_content = []
    for raw_id in data.get("catseason", []):
        season_content.append(
            make_item(
                str(raw_id),
                name_from_i2(i2, f"item/{raw_id}", str(raw_id)),
                "season_content",
                subcategory="cat_season",
                attributes={"observed_in_reference_sample": True},
                save_refs=["seasonData", "battlePassSaveData"],
                source=item_source(commit, "data.json"),
            )
        )
    catalogs["season_content"] = season_content

    collectibles = []
    monsrise = data.get("monsrise") or {}
    for raw in monsrise.get("unlockedContents", []):
        collectibles.append(
            make_item(
                f"monsrise_content_{raw}",
                {"en": None, "es": None, "zh_cn": None},
                "collectible",
                subcategory="monsrise_content",
                attributes={"raw_id": raw, "observed_in_reference_sample": True},
                save_refs=["monsterRiseData"],
                source=item_source(commit, "data.json"),
            )
        )
    for raw in sorted((monsrise.get("CollectedMonsters") or {})):
        collectibles.append(
            make_item(
                f"monsrise_monster:{raw}",
                name_from_i2(i2, raw),
                "collectible",
                subcategory="monsrise_monster",
                attributes={"raw_id": raw, "observed_in_reference_sample": True},
                save_refs=["monsterRiseData"],
                source=item_source(commit, "data.json"),
            )
        )
    for raw in sorted((monsrise.get("CollectedEmblems") or {})):
        collectibles.append(
            make_item(
                f"monsrise_emblem:{raw}",
                name_from_i2(i2, raw),
                "collectible",
                subcategory="monsrise_emblem",
                attributes={"raw_id": raw, "observed_in_reference_sample": True},
                save_refs=["monsterRiseData"],
                source=item_source(commit, "data.json"),
            )
        )
    catalogs["collectibles"] = collectibles
    return catalogs


def read_version_snapshot(skdfe: Path, commit: str) -> dict[str, Any]:
    def show(path: str) -> str:
        return subprocess.check_output(
            ["git", "-C", str(skdfe), "show", f"{commit}:{path}"],
            text=True,
        )

    needed = json.loads(show("needed_data.json"))
    item = json.loads(show("item.json"))
    weapon_full = json.loads(show("weapon_full.json"))["weapons"]
    enemies = json.loads(show("enemy.json"))
    codes = json.loads(show("char_code_name.json"))
    pets = json.loads(show("pet_code_name.json"))
    skills = sorted(needed.get("character_skill", {}))
    skins = sorted(
        key for entries in needed.get("skin", {}).values() for key in entries
    )
    weapon_skins = sorted(needed.get("weapon_skin", {}))
    materials = sorted(needed.get("material", {}))
    items = sorted(set(
        key
        for group in item.get("material", {}).values()
        for key in group
    ) | set(
        key
        for group in item.get("blueprint", {}).values()
        for key in group
    ))
    blueprints = sorted(
        key for group in item.get("blueprint", {}).values() for key in group
    )
    tokens = sorted(item.get("token", []))
    return {
        "commit": commit,
        "counts": {
            "characters": len(codes),
            "pets": len(pets),
            "character_skills": len(skills),
            "character_skins": len(skins),
            "weapons": len(weapon_full),
            "weapon_skins": len(weapon_skins),
            "materials": len(materials),
            "items": len(items),
            "blueprints": len(blueprints),
            "enemies": len(enemies),
            "tokens": len(tokens),
        },
        "ids": {
            "characters": sorted(codes),
            "pets": sorted(pets),
            "character_skills": skills,
            "character_skins": skins,
            "weapons": sorted(str(entry.get("name")) for entry in weapon_full),
            "weapon_skins": weapon_skins,
            "materials": materials,
            "items": items,
            "blueprints": blueprints,
            "enemies": sorted(enemies),
            "tokens": tokens,
        },
    }


def build_version_diffs(skdfe: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    snapshots = {
        version: read_version_snapshot(skdfe, commit)
        for version, commit in VERSION_COMMITS.items()
    }
    order = ["8.6.0", "8.7.0", "8.8.0"]
    diffs: list[dict[str, Any]] = []
    for previous, current in zip(order, order[1:]):
        old = snapshots[previous]
        new = snapshots[current]
        families: dict[str, Any] = {}
        for family in sorted(set(old["ids"]) | set(new["ids"])):
            before = set(old["ids"].get(family, []))
            after = set(new["ids"].get(family, []))
            families[family] = {
                "count_before": len(before),
                "count_after": len(after),
                "added": sorted(after - before),
                "removed": sorted(before - after),
            }
        diffs.append(
            {
                "schema": DIFF_SCHEMA,
                "from_version": previous,
                "to_version": current,
                "from_commit": VERSION_COMMITS[previous],
                "to_commit": VERSION_COMMITS[current],
                "families": families,
            }
        )
    return diffs, snapshots


def build_translations(catalogs: dict[str, dict[str, Any]]) -> dict[str, Any]:
    entries: list[dict[str, str]] = []
    for family, document in sorted(catalogs.items()):
        for item in document["items"]:
            for language in ("en", "es", "zh_cn"):
                text = (item.get("name") or {}).get(language)
                if text:
                    entries.append(
                        {
                            "text": text,
                            "language": language,
                            "catalog": family,
                            "item_id": item["id"],
                        }
                    )
    entries.sort(key=lambda row: (row["language"], row["text"].casefold(), row["catalog"], row["item_id"]))
    return {
        "schema": "sk-knowledge/name-index@1",
        "generated_by": "knowledge/tools/build_catalog.py",
        "count": len(entries),
        "entries": entries,
    }


def build_documents(
    skdfe: Path,
    *,
    include_version_diffs: bool = True,
    commit_override: str | None = None,
) -> dict[Path, Any]:
    """Construye todos los artefactos en memoria.

    ``commit_override`` permite usar una fixture sin repositorio git. Las
    diferencias entre versiones requieren el historial y se pueden desactivar.
    """
    if commit_override is not None:
        commit = commit_override
    else:
        try:
            commit = subprocess.check_output(
                ["git", "-C", str(skdfe), "rev-parse", "HEAD"], text=True
            ).strip()
        except (OSError, subprocess.CalledProcessError):
            commit = "working-tree"
    version = read_json(skdfe / "version.json").get("version", "8.8.0")
    i2 = load_i2(skdfe / "I2language.csv")
    needed = read_json(skdfe / "needed_data.json")
    item_json = read_json(skdfe / "item.json")
    data = read_json(skdfe / "data.json")
    codes = read_json(skdfe / "char_code_name.json")
    pet_codes = read_json(skdfe / "pet_code_name.json")
    highest = read_json(skdfe / "highest_skin_ids.json")
    weapon_full = read_json(skdfe / "weapon_full.json")["weapons"]
    weapon_csv = load_csv_rows(skdfe / "weapons.decrypted.csv")
    items_csv = load_csv_rows(skdfe / "items.decrypted.csv")
    enemies_csv = load_csv_rows(skdfe / "enemies.decrypted.csv")
    item_csv_by_key = {row["Key"]: row for row in items_csv}

    characters, character_skills, character_skins = build_characters(
        codes, needed, i2, highest, commit
    )
    pets, pet_skills = build_pets(pet_codes, needed, i2, commit)
    pet_skins = build_pet_skins(pets, i2, commit)
    weapons = build_weapons(weapon_full, weapon_csv, i2, commit)
    weapon_skins = build_weapon_skins(needed, i2, commit)
    materials = build_materials(
        item_json.get("material", {}), needed, item_csv_by_key, i2, commit
    )
    seeds, plants = build_seeds_and_plants(item_json.get("plant", []), i2, commit)
    blueprints = build_blueprints(item_json.get("blueprint", {}), item_csv_by_key, i2, commit)
    enemies, bosses = build_enemies(enemies_csv, i2, commit)
    lobby = build_lobby(data, i2, commit)

    reference = build_reference_catalogs(
        data, item_json, item_csv_by_key, i2, commit
    )

    definitions: dict[str, tuple[str, str, list[dict[str, Any]], list[Any], str]] = {
        "characters": ("Personajes jugables", "Códigos internos, nombres, habilidades y skins.", characters, ["char_code_name.json", "needed_data.json"], "characters"),
        "character_skills": ("Habilidades de personaje", "Habilidades por personaje e índice de slot.", character_skills, ["needed_data.json"], "character_skills"),
        "character_skins": ("Skins de personaje", "Skins indexadas por personaje.", character_skins, ["needed_data.json"], "character_skins"),
        "pets": ("Mascotas", "Códigos, identificadores numéricos y nombres disponibles.", pets, ["pet_code_name.json", "needed_data.json"], "pets"),
        "pet_skills": ("Habilidades de mascota", "Habilidades y descripciones localizadas.", pet_skills, ["I2language.csv"], "pet_skills"),
        "pet_skins": ("Skins de mascota", "Variantes de mascota agrupadas por mascota base; sin mapa de bloqueo separado confirmado.", pet_skins, ["needed_data.json"], "pet_skins"),
        "weapons": ("Armas y variantes de configuración", "Catálogo de armas, anillos, transformaciones y variantes internas.", weapons, ["weapon_full.json", "weapons.decrypted.csv"], "weapons"),
        "weapon_skins": ("Skins de arma", "Skins indexadas por arma.", weapon_skins, ["needed_data.json"], "weapon_skins"),
        "materials": ("Materiales", "Unión de materiales de item.json y needed_data.json.", materials, ["item.json", "needed_data.json"], "materials"),
        "seeds": ("Semillas", "Semillas de jardín observadas en el catálogo de objetos.", seeds, ["item.json"], "seeds"),
        "plants": ("Plantas", "Plantas de jardín y su semilla asociada.", plants, ["I2language.csv"], "plants"),
        "blueprints": ("Planos", "Planos, costes de investigación y objetivo asociado.", blueprints, ["items.decrypted.csv"], "blueprints"),
        "enemies": ("Enemigos", "Enemigos, jefes y drops declarados.", enemies, ["enemies.decrypted.csv"], "enemies"),
        "bosses": ("Jefes", "Subconjunto de enemigos con IsBoss=true.", bosses, ["enemies.decrypted.csv"], "bosses"),
        "lobby": ("Vestíbulo y decoraciones", "Muebles, desbloqueos, skins de sala y de jardín.", lobby, ["data.json", "I2language.csv"], "lobby"),
        "tokens": ("Tokens y tickets", "Tokens declarados en item.json.", reference.get("tokens", []), ["item.json"], "tokens"),
        "special_items": ("Objetos especiales", "Objetos activos, otros y efectos de eliminación.", reference.get("special_items", []), ["item.json"], "special_items"),
        "vouchers": ("Cupones y vales", "Vales agrupados observados en una muestra externa con forma de guardado.", reference.get("vouchers", []), ["data.json"], "vouchers"),
        "jewelry": ("Joyería", "Joyería observada en una muestra externa con forma de guardado.", reference.get("jewelry", []), ["data.json"], "jewelry"),
        "chips": ("Chips de Monster Rise", "Chips observados; no son las fichas de temporada.", reference.get("chips", []), ["data.json"], "chips"),
        "mounts": ("Monturas", "Monturas observadas en una muestra externa con forma de guardado.", reference.get("mounts", []), ["data.json"], "mounts"),
        "followers": ("Seguidores", "Seguidores observados en una muestra externa con forma de guardado.", reference.get("followers", []), ["data.json"], "followers"),
        "trophies": ("Trofeos y estadísticas de modo", "Claves de trofeos visuales, ARAM e Iron Tide.", reference.get("trophies", []), ["data.json"], "trophies"),
        "season_content": ("Contenido de temporada", "Claves de contenido de temporada observadas.", reference.get("season_content", []), ["data.json"], "season_content"),
        "collectibles": ("Coleccionables de Monster Rise", "Contenidos, monstruos y emblemas observados.", reference.get("collectibles", []), ["data.json"], "collectibles"),
    }

    documents: dict[Path, Any] = {}
    catalog_documents: dict[str, dict[str, Any]] = {}
    for family, (title, description, items, files, _) in definitions.items():
        ensure_unique_ids(items, family)
        refs = [source_ref(commit, filename) for filename in files]
        document = catalog_document(
            family,
            title,
            version,
            refs,
            items,
            description=description,
            license_note=LICENSE_NOTE,
        )
        catalog_documents[family] = document
        documents[CATALOGS_DIR / f"{family}.json"] = document

    translations = build_translations(catalog_documents)
    documents[TRANSLATIONS_DIR / "name-index.json"] = translations

    if include_version_diffs:
        diffs, snapshots = build_version_diffs(skdfe)
        for diff in diffs:
            documents[
                VERSION_DIFFS_DIR / f"{diff['from_version']}_to_{diff['to_version']}.json"
            ] = diff
        documents[VERSION_DIFFS_DIR / "snapshots.json"] = {
            "schema": "sk-knowledge/version-snapshots@1",
            "generated_by": "knowledge/tools/build_catalog.py",
            "versions": snapshots,
        }
    return documents


def write_or_check(documents: dict[Path, Any], check: bool) -> int:
    failures = 0
    for path, value in sorted(documents.items()):
        expected = common.canonical_json(value)
        if check:
            if not path.is_file():
                print(f"FALTA {path.relative_to(common.REPO_ROOT)}")
                failures += 1
                continue
            current = path.read_text(encoding="utf-8")
            if current != expected:
                print(f"DIFERENTE {path.relative_to(common.REPO_ROOT)}")
                failures += 1
            else:
                print(f"OK {path.relative_to(common.REPO_ROOT)}")
        else:
            write_json(path, value)
            print(f"ESCRITO {path.relative_to(common.REPO_ROOT)}")
    return 1 if failures else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skdfe", type=Path, default=DEFAULT_SKDFE)
    parser.add_argument("--check", action="store_true", help="No escribe; compara con los artefactos versionados.")
    parser.add_argument(
        "--no-version-diffs",
        action="store_true",
        help="Omite las diferencias históricas (útil con fixtures sin historial git).",
    )
    parser.add_argument("--commit", help="Commit de procedencia cuando la fuente no es un repositorio git.")
    args = parser.parse_args(argv)
    if not (args.skdfe / "weapon_full.json").is_file():
        print(f"ERROR: no se encontró una copia de SKDFE en {args.skdfe}", file=sys.stderr)
        return 2
    documents = build_documents(
        args.skdfe,
        include_version_diffs=not args.no_version_diffs,
        commit_override=args.commit,
    )
    return write_or_check(documents, args.check)


if __name__ == "__main__":
    raise SystemExit(main())
"""Informe saneado de solo lectura para fichas, personajes y recursos.

El módulo reutiliza los analizadores existentes y nunca devuelve el documento
completo. Solo expone los campos cuyo nombre y tipo se observaron en las
muestras, junto con su estado de evidencia. La escritura no forma parte de este
módulo: todos los grupos se publican como ``read_only``.
"""

from __future__ import annotations

from typing import Any, Mapping

from .catalogs import load_character_catalog
from .cloud_save import reconstruct_cloud_save
from .save_analysis import MISSING, character_report, fish_chip_report, kind_of

REPORT_VERSION = 1
MAX_ITEMS = 200
MAX_TEXT = 120

READ_ONLY = "read_only"
E2 = "E2: presencia y estructura observadas; comportamiento no validado."
E3 = "E3: comportamiento validado en una muestra experimental."
E4 = "E4: persistencia y consistencia confirmadas en un dispositivo físico."


def _mapping(value: object) -> Mapping[str, Any] | None:
    return value if isinstance(value, dict) else None


def _safe_text(value: object, limit: int = MAX_TEXT) -> str:
    text = "" if value is None else str(value)
    text = text.replace("\x00", "")
    text = "".join(char for char in text if char.isprintable())
    return text if len(text) <= limit else text[:limit] + "…"


def _nested(document: Mapping[str, Any], *path: str) -> object:
    value: object = document
    for part in path:
        if not isinstance(value, dict) or part not in value:
            return MISSING
        value = value[part]
    return value


def _state(value: object) -> str:
    if value is MISSING:
        return "missing"
    if value is None:
        return "null"
    return "present"


def _load_character_catalog() -> dict[str, object]:
    """Carga el catálogo empaquetado sin convertirlo en una dependencia obligatoria."""
    return load_character_catalog()


def _character_rows(game: Mapping[str, Any]) -> dict[str, object]:
    catalog = _load_character_catalog()
    codes = catalog["codes"] or None
    skins = catalog["skins"] or None
    skills = catalog["skills"] or None
    report = character_report(
        game,
        character_codes=codes,
        skin_catalog=skins,
        skill_catalog=skills,
    )
    rows: list[dict[str, object]] = []
    for row in report["characters"]:
        code = row["code"]
        entry = catalog["characters"].get(code) if isinstance(catalog["characters"], dict) else None
        name = entry.get("name") if isinstance(entry, dict) else None
        if not isinstance(name, str):
            name = code
        observed_skins = row.pop("skins", [])
        selected_skin = row.get("selected_skin")
        equipped = None
        if type(selected_skin) is int:
            equipped = next(
                (skin for skin in observed_skins if skin.get("key") == selected_skin),
                {"key": selected_skin, "state": None, "name": None},
            )
        options = []
        skin_options = []
        observed_by_index = {
            skin.get("key"): skin.get("state")
            for skin in observed_skins
            if isinstance(skin, dict)
        }
        if isinstance(entry, dict):
            for skill in entry.get("skills", []) if isinstance(entry.get("skills"), list) else []:
                if isinstance(skill, dict) and type(skill.get("index")) is int:
                    options.append({"index": skill["index"], "name": _safe_text(skill.get("name"))})
            for skin in entry.get("skins", []) if isinstance(entry.get("skins"), list) else []:
                if not isinstance(skin, dict) or type(skin.get("index")) is not int:
                    continue
                index = skin["index"]
                value = observed_by_index.get(index)
                compatible = type(value) is int
                if not compatible:
                    state = "unknown"
                elif value == 1:
                    state = "unlocked"
                else:
                    state = "locked"
                skin_options.append(
                    {
                        "index": index,
                        "key": _safe_text(skin.get("key")),
                        "name": _safe_text(skin.get("name")),
                        "state": state,
                        "value": value if type(value) is int else None,
                        "compatible": compatible,
                    }
                )
        row.update(
            {
                "name": _safe_text(name),
                "level_max": None,
                "level_status": "not_validated",
                "skill_options": options,
                "skin_options": skin_options,
                "equipped_skin": equipped,
                "skins_recorded": len(observed_skins),
                "skins_status": "confirmed_by_owner",
            }
        )
        rows.append(row)

    total_skills = sum(
        len(row["skill_options"]) for row in rows if isinstance(row.get("skill_options"), list)
    )
    unlocked_skills = 0
    selected_skills = 0
    characters_with_skills = 0
    for row in rows:
        options = row.get("skill_options")
        observed = row.get("skills")
        if not isinstance(options, list) or not isinstance(observed, list):
            continue
        if observed:
            characters_with_skills += 1
        observed_by_index = {
            entry.get("key"): entry.get("unlocked")
            for entry in observed
            if isinstance(entry, dict)
        }
        option_indices = {
            option.get("index") for option in options if isinstance(option, dict)
        }
        unlocked_skills += sum(
            1 for index in option_indices if observed_by_index.get(index) is True
        )
        selected = row.get("selected_skill")
        if type(selected) is int and selected in option_indices:
            selected_skills += 1

    total_skins = 0
    unlocked_skins = 0
    incompatible_skins = 0
    selected_skins = 0
    characters_with_skins = 0
    for row in rows:
        options = row.get("skin_options")
        if not isinstance(options, list):
            continue
        if row.get("skins_recorded"):
            characters_with_skins += 1
        total_skins += len(options)
        compatible_indices: set[int] = set()
        for option in options:
            if not isinstance(option, dict):
                continue
            if option.get("compatible") is True and type(option.get("index")) is int:
                compatible_indices.add(option["index"])
                if option.get("state") == "unlocked":
                    unlocked_skins += 1
            else:
                incompatible_skins += 1
        selected = row.get("selected_skin")
        if type(selected) is int and selected in compatible_indices:
            selected_skins += 1
    return {
        "items": rows,
        "counts": report["counts"],
        "skills": {
            "total": total_skills,
            "unlocked": unlocked_skills,
            "locked": total_skills - unlocked_skills,
            "selected": selected_skills,
            "characters_with_data": characters_with_skills,
            "status": READ_ONLY,
        },
        "skins": {
            "total": total_skins,
            "unlocked": unlocked_skins,
            "pending": total_skins - unlocked_skins - incompatible_skins,
            "selected": selected_skins,
            "incompatible": incompatible_skins,
            "characters_with_data": characters_with_skins,
            "status": "confirmed_by_owner",
        },
        "level_status": "not_validated",
        "skins_status": "confirmed_by_owner",
        "catalog": {
            "available": bool(catalog.get("available", bool(catalog.get("codes")))),
            "error": catalog.get("error"),
            "version": catalog.get("version"),
            "source": catalog.get("source"),
            "characters": len(catalog["codes"]),
        },
        "notes": [
            "El nivel se muestra tal como aparece en la partida; no hay máximo validado.",
            "Solo Knight tiene un cambio de nivel observado experimentalmente (E3).",
            "El desbloqueo de skins está confirmado por el propietario en Android físico (E3): interpreta Value=1 como desbloqueada, no crea posiciones y conserva currentSkinDatas. Los demás valores de skinLock no tienen semántica validada.",
            "Las habilidades se muestran con nombre de catálogo y el estado observado en heroSkillUnlock.",
            "El desbloqueo de personajes está confirmado por el propietario en Android físico; solo activa gameData.heroUnlock y conserva niveles, habilidades y skins.",
            "El desbloqueo de habilidades fue confirmado por el propietario en el cliente oficial y Android físico (E3); solo activa posiciones existentes de gameData.heroSkillUnlock y conserva gameData.heroSkill.",
        ],
        "status": READ_ONLY,
    }


def _map_items(value: Mapping[str, Any], *, include_count: bool = True) -> list[dict[str, object]]:
    rows = []
    for key in sorted(value):
        item = value[key]
        row: dict[str, object] = {"id": _safe_text(key)}
        if include_count and type(item) is int:
            row["count"] = item
        elif type(item) is str:
            row["type"] = "str"
            row["text_length"] = len(item)
        else:
            row["type"] = kind_of(item)
        rows.append(row)
        if len(rows) >= MAX_ITEMS:
            break
    return rows


def _plant_items(value: list[Any]) -> list[dict[str, object]]:
    rows = []
    for item in value:
        if not isinstance(item, dict):
            rows.append({"state": "unknown"})
        else:
            rows.append(
                {
                    "plant": _safe_text(item.get("plantName")) if item.get("plantName") is not None else None,
                    "state": item.get("state") if type(item.get("state")) is int else None,
                    "fertilized": item.get("fertilized") if type(item.get("fertilized")) is bool else None,
                    "watered": item.get("watered") if type(item.get("watered")) is bool else None,
                }
            )
        if len(rows) >= MAX_ITEMS:
            break
    return rows


def _commodity_items(value: list[Any]) -> list[dict[str, object]]:
    rows = []
    for item in value:
        if not isinstance(item, dict):
            rows.append({"state": "unknown"})
        else:
            rows.append(
                {
                    "name": _safe_text(item.get("name")) if item.get("name") is not None else None,
                    "count": item.get("count") if type(item.get("count")) is int else None,
                }
            )
        if len(rows) >= MAX_ITEMS:
            break
    return rows


def _identifier_items(value: list[Any]) -> list[dict[str, object]]:
    rows = []
    for item in value:
        if isinstance(item, str):
            rows.append({"id": _safe_text(item)})
        elif isinstance(item, dict):
            identifier = item.get("name", item.get("id"))
            rows.append(
                {
                    "id": _safe_text(identifier) if identifier is not None else None,
                    "type": "object",
                }
            )
        else:
            rows.append({"state": kind_of(item)})
        if len(rows) >= MAX_ITEMS:
            break
    return rows


def _list_shape(value: list[Any]) -> dict[str, object]:
    types: dict[str, int] = {}
    for item in value:
        name = kind_of(item)
        types[name] = types.get(name, 0) + 1
    return {"item_types": dict(sorted(types.items())), "list_length": len(value)}


def _resource_group(
    document: Mapping[str, Any],
    *,
    identifier: str,
    label: str,
    section: str,
    field: str,
    note: str,
    items: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    value = _nested(document, section, field)
    present = value is not MISSING
    entries = len(value) if isinstance(value, (dict, list)) else (1 if present and value is not None else 0)
    group: dict[str, object] = {
        "id": identifier,
        "label": label,
        "path": f"{section}.{field}",
        "state": _state(value),
        "type": kind_of(value),
        "entries": entries,
        "status": READ_ONLY,
        "evidence": E2,
        "note": note,
    }
    if items is not None and present and value is not None:
        group["items"] = items
        group["truncated"] = entries > len(items)
    elif isinstance(value, dict):
        group["items"] = _map_items(value)
        group["truncated"] = entries > len(group["items"])
    elif isinstance(value, list):
        if identifier == "plants":
            group["items"] = _plant_items(value)
        elif identifier == "commodities":
            group["items"] = _commodity_items(value)
        elif identifier == "unlocked_items":
            group["items"] = _identifier_items(value)
        else:
            group["items"] = []
        group["truncated"] = entries > len(group["items"])
        group.update(_list_shape(value))
    elif present and value is not None:
        group["value"] = value if type(value) is int else kind_of(value)
    return group


def _resources(document: Mapping[str, Any]) -> dict[str, object]:
    groups = [
        _resource_group(
            document,
            identifier="materials",
            label="Materiales",
            section="itemData",
            field="materials",
            note="Identificadores observados; no hay catálogo de objetos 8.8.0 para traducir todos los nombres.",
        ),
        _resource_group(
            document,
            identifier="seeds",
            label="Semillas",
            section="itemData",
            field="seeds",
            note="Cantidad por identificador de semilla observada en itemData.seeds.",
        ),
        _resource_group(
            document,
            identifier="token_tickets",
            label="Tickets ordinarios",
            section="itemData",
            field="tokenTickets",
            note="Tickets comunes; no se confunden con tickets especiales ni con fichas de pesca.",
        ),
        _resource_group(
            document,
            identifier="special_tickets",
            label="Tickets especiales",
            section="itemData",
            field="specialTickets",
            note="Estructura observada; no se deduce su uso ni se edita.",
        ),
        _resource_group(
            document,
            identifier="blueprints",
            label="Planos",
            section="itemData",
            field="blueprints",
            note="Se muestran los identificadores; el contenido textual del valor se omite.",
        ),
        _resource_group(
            document,
            identifier="unlocked_items",
            label="Objetos desbloqueados",
            section="itemData",
            field="itemUnlock",
            note="Lista de identificadores desbloqueados observada; no se modifica.",
        ),
        _resource_group(
            document,
            identifier="plants",
            label="Plantas",
            section="itemData",
            field="plants",
            note="Estado observado por planta; no se interpreta como cosecha disponible.",
        ),
        _resource_group(
            document,
            identifier="commodities",
            label="Mercancía",
            section="itemData",
            field="commodities",
            note="Entradas observadas en el inventario de mercancía.",
        ),
        _resource_group(
            document,
            identifier="forge_weapons",
            label="Armas de forja",
            section="itemData",
            field="forgeWeapons",
            note="Solo se resume la forma de la lista; no se deduce ni se edita el equipo.",
        ),
        _resource_group(
            document,
            identifier="cumulative_fish_count",
            label="Peces acumulados",
            section="itemData",
            field="cumulativeFishCount",
            note="Contador acumulativo; no es el saldo de fichas de pesca.",
        ),
    ]
    counts = {group["id"]: group["entries"] for group in groups}
    return {
        "groups": groups,
        "counts": counts,
        "status": READ_ONLY,
        "notes": [
            "Esta sección es informativa: no se ha validado una escritura segura para recursos.",
            "Los nombres de objetos no identificados se muestran como aparecen en la partida.",
            "Fertilizantes y fragmentos son claves dentro de materiales; no se inventa su semántica.",
        ],
    }


def build_save_report(document: Mapping[str, Any]) -> dict[str, object]:
    """Construye el informe saneado a partir del agregado ya decodificado."""
    game = _mapping(document.get("gameData")) or {}
    fish = fish_chip_report(document)
    fish.update(
        {
            "status": READ_ONLY,
            "evidence": E4,
            "validation_level": "E4",
            "write_policy": "confirmed_by_owner",
            "transaction_validated": True,
            "missing_proof": (
                "El propietario confirmó en Android la subida y recuperación desde la nube, "
                "la visualización del saldo, la compra de paquetes con descuento correcto y "
                "el guardado posterior desde el cliente oficial al modificar conjuntamente "
                "gameData.fishChip e itemData.materials.material_fish."
            ),
        }
    )
    game_version = game.get("gameVersion")
    return {
        "version": REPORT_VERSION,
        "game_version": game_version if type(game_version) is int else None,
        "fish_chips": fish,
        "characters": _character_rows(game),
        "resources": _resources(document),
        "limitations": [
            "El propietario confirmó el saldo de fichas de pesca y la escritura conjunta de gameData.fishChip e itemData.materials.material_fish en un dispositivo Android físico.",
            "El desbloqueo de personajes confirmado por el propietario solo modifica gameData.heroUnlock; no edita niveles, habilidades, skins ni recursos.",
            "No se habilita la escritura de niveles, recursos ni otras categorías. El desbloqueo de personajes, habilidades y skins está confirmado por el propietario; no se declara persistencia posterior.",
            "Solo se interpreta skinLock Value=1 como skin desbloqueada; el propietario confirmó el resultado en Android físico (E3). Los demás valores se conservan sin semántica validada.",
            "Los niveles máximos de personaje no están validados; no se muestran como si lo estuvieran.",
        ],
    }


def read_save_report(source: bytes) -> dict[str, object]:
    """Decodifica una copia de nube y devuelve únicamente el informe saneado."""
    reconstructed = reconstruct_cloud_save(source)
    data = reconstructed.data
    document: dict[str, object] = dict(data.optional_sections)
    document["gameData"] = data.game_data
    report = build_save_report(document)
    report["serialzed_version"] = data.serialzed_version
    report["encoding"] = reconstructed.encoding
    return report
"""Inventario y comparación de solo lectura para guardados de Soul Knight.

El módulo no conoce credenciales, no abre conexiones y no escribe archivos.
Trabaja sobre el agregado de nube ya decodificado o sobre las secciones locales
que el llamador haya abierto con :mod:`app.local_save`. Su objetivo es describir
la forma observada, no atribuir una función a un nombre de campo.

Los informes omiten valores por defecto. Un valor solo se devuelve cuando el
llamador lo pide de forma explícita para una ruta concreta.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

MISSING = "<missing>"


def kind_of(value: object) -> str:
    """Devuelve el tipo JSON observado sin confundir ``bool`` con ``int``."""
    if value is None:
        return "null"
    if type(value) is bool:
        return "bool"
    if type(value) is int:
        return "int"
    if type(value) is float:
        return "float"
    if type(value) is str:
        return "str"
    if type(value) is list:
        return "list"
    if type(value) is dict:
        return "object"
    return type(value).__name__


def _join(prefix: tuple[str, ...], name: str) -> str:
    return ".".join((*prefix, name))


def _mapping(value: object) -> Mapping[str, Any] | None:
    return value if isinstance(value, dict) else None


def section_summary(document: Mapping[str, Any]) -> list[dict[str, object]]:
    """Resume las claves superiores de un agregado o de una sección local."""
    rows: list[dict[str, object]] = []
    for name in sorted(document):
        value = document[name]
        row: dict[str, object] = {"section": name, "type": kind_of(value)}
        if isinstance(value, dict):
            row["entries"] = len(value)
            row["keys"] = sorted(value)[:24]
        elif isinstance(value, list):
            row["entries"] = len(value)
            item_types = sorted({kind_of(item) for item in value})
            row["item_types"] = item_types
        rows.append(row)
    return rows


@dataclass(frozen=True)
class FieldShape:
    """Forma agregada de una ruta; las listas usan ``[]`` como marcador."""

    path: str
    kind: str
    occurrences: int
    distinct_values: int | None = None
    sample: object | None = None
    include_sample: bool = False

    def as_dict(self) -> dict[str, object]:
        row: dict[str, object] = {
            "path": self.path,
            "type": self.kind,
            "occurrences": self.occurrences,
        }
        if self.distinct_values is not None:
            row["distinct_values"] = self.distinct_values
        if self.include_sample:
            row["sample"] = self.sample
        return row


@dataclass
class _ShapeAccumulator:
    kinds: set[str] = field(default_factory=set)
    occurrences: int = 0
    values: set[str] = field(default_factory=set)
    sample: object | None = None


def _collect(
    value: object,
    path: tuple[str, ...],
    accumulators: dict[tuple[str, ...], _ShapeAccumulator],
    *,
    depth: int,
    max_depth: int,
) -> None:
    accumulator = accumulators.setdefault(path, _ShapeAccumulator())
    accumulator.kinds.add(kind_of(value))
    accumulator.occurrences += 1
    accumulator.sample = value
    if type(value) is dict:
        if depth >= max_depth:
            return
        for name in sorted(value):
            _collect(value[name], (*path, name), accumulators, depth=depth + 1, max_depth=max_depth)
    elif type(value) is list:
        if depth >= max_depth:
            return
        for item in value:
            _collect(item, (*path, "[]"), accumulators, depth=depth + 1, max_depth=max_depth)
    else:
        accumulator.values.add(repr(value))


def field_shapes(
    document: Mapping[str, Any],
    *,
    max_depth: int = 6,
    include_samples: bool = False,
    prefix: tuple[str, ...] = (),
) -> list[FieldShape]:
    """Devuelve las rutas observadas con tipo, repeticiones y valores distintos.

    Los índices de listas se agrupan bajo ``[]`` para no convertir un mapa de
    1.500 armas en 1.500 rutas distintas. El llamador puede inspeccionar un
    índice concreto con :func:`value_at`.
    """
    accumulators: dict[tuple[str, ...], _ShapeAccumulator] = {}
    _collect(document, prefix, accumulators, depth=0, max_depth=max_depth)
    rows = []
    for path, accumulator in accumulators.items():
        # Un mismo marcador puede recibir tipos distintos; se conservan todos
        # para que un cambio de tipo no pase desapercibido.
        kind = "|".join(sorted(accumulator.kinds))
        rows.append(
            FieldShape(
                path=".".join(path),
                kind=kind,
                occurrences=accumulator.occurrences,
                distinct_values=len(accumulator.values) if accumulator.values else None,
                sample=accumulator.sample if include_samples else None,
                include_sample=include_samples,
            )
        )
    return sorted(rows, key=lambda row: row.path)


def value_at(document: Mapping[str, Any], path: str) -> object:
    """Lee una ruta con puntos; ``[]`` no se expande."""
    value: object = document
    for part in path.split(".") if path else []:
        if isinstance(value, dict) and part in value:
            value = value[part]
        elif isinstance(value, list) and part.isdecimal() and int(part) < len(value):
            value = value[int(part)]
        else:
            return MISSING
    return value


@dataclass(frozen=True)
class Change:
    path: str
    kind: str
    before: object = MISSING
    after: object = MISSING

    def as_dict(self, *, include_values: bool = True) -> dict[str, object]:
        row: dict[str, object] = {"path": self.path, "kind": self.kind}
        if include_values and self.kind in ("changed", "type", "removed"):
            row["before"] = self.before
        if include_values and self.kind in ("changed", "type", "added"):
            row["after"] = self.after
        return row


def structural_diff(before: object, after: object, path: tuple[str, ...] = ()) -> list[Change]:
    """Compara dos árboles JSON y conserva la diferencia ausente/vacío/cero."""
    if type(before) is not type(after):
        return [Change(".".join(path), "type", before, after)]
    if isinstance(before, dict):
        changes: list[Change] = []
        for name in sorted(before.keys() | after.keys()):
            child = (*path, name)
            if name not in before:
                changes.append(Change(".".join(child), "added", after=after[name]))
            elif name not in after:
                changes.append(Change(".".join(child), "removed", before=before[name]))
            else:
                changes.extend(structural_diff(before[name], after[name], child))
        return changes
    if isinstance(before, list):
        changes = []
        for index in range(max(len(before), len(after))):
            child = (*path, f"[{index}]")
            if index >= len(before):
                changes.append(Change(".".join(child), "added", after=after[index]))
            elif index >= len(after):
                changes.append(Change(".".join(child), "removed", before=before[index]))
            else:
                changes.extend(structural_diff(before[index], after[index], child))
        return changes
    return [] if before == after else [Change(".".join(path), "changed", before, after)]


def compare_documents(
    before: Mapping[str, Any],
    after: Mapping[str, Any],
    *,
    include_values: bool = False,
    ignore: Iterable[str] = (),
) -> dict[str, object]:
    """Compara secciones completas y resume los cambios por sección.

    ``ignore`` acepta prefijos de ruta. El resultado no incluye valores salvo
    que ``include_values`` sea verdadero.
    """
    changes = structural_diff(before, after)
    prefixes = tuple(ignore)
    filtered = [change for change in changes if not prefixes or not change.path.startswith(prefixes)]
    sections: dict[str, int] = {}
    for change in filtered:
        section = change.path.split(".", 1)[0] or "<root>"
        sections[section] = sections.get(section, 0) + 1
    return {
        "changed_sections": dict(sorted(sections.items())),
        "change_count": len(filtered),
        "changes": [change.as_dict(include_values=include_values) for change in filtered],
    }


def _nested(document: Mapping[str, Any], *path: str) -> object:
    value: object = document
    for part in path:
        if not isinstance(value, dict) or part not in value:
            return MISSING
        value = value[part]
    return value


def fish_chip_report(document: Mapping[str, Any]) -> dict[str, object]:
    """Describe la representación observada de las fichas de pesca.

    Clasifica cada ruta por archivo y función estructural. No equipara
    ``cumulativeFishCount``, ``material_fish`` ni ``seasonData.chips`` con el
    saldo de fichas. El saldo solo se propone cuando ``gameData.fishChip`` está
    presente y es entero; aun así, la autoridad del servidor queda pendiente.
    """
    game = _mapping(document.get("gameData"))
    item = _mapping(document.get("itemData"))
    mall = _mapping(document.get("mallReloadData"))
    season = _mapping(document.get("seasonData"))
    statistic = _mapping(document.get("statisticData"))

    balance = game.get("fishChip", MISSING) if game is not None else MISSING
    fields: list[dict[str, object]] = []
    if balance is not MISSING:
        fields.append(
            {
                "path": "gameData.fishChip",
                "type": kind_of(balance),
                "value": balance,
                "role": "saldo candidato",
                "evidence": "E4: saldo y gasto confirmados por el propietario en Android 8.8.0.",
            }
        )
    materials = item.get("materials") if item is not None else None
    if isinstance(materials, dict) and "material_fish" in materials:
        material = materials["material_fish"]
        fields.append(
            {
                "path": "itemData.materials.material_fish",
                "type": kind_of(material),
                "value": material,
                "role": "material de pesca (no es el saldo de fichas)",
                "evidence": (
                    "E4: confirmado por el propietario en Android; debe editarse junto con gameData.fishChip "
                    "para que el saldo y el gasto coincidan."
                ),
            }
        )
    if item is not None:
        for name in sorted(item):
            if "fishchip" not in name.lower():
                continue
            value = item[name]
            fields.append(
                {
                    "path": f"itemData.{name}",
                    "type": kind_of(value),
                    "entries": len(value) if isinstance(value, (dict, list)) else None,
                    "role": "configuración o historial de tienda",
                    "evidence": "E2: estructura observada; no es un saldo.",
                }
            )
    if mall is not None:
        for name in sorted(mall):
            if name.startswith("buyFishCount"):
                value = mall[name]
                fields.append(
                    {
                        "path": f"mallReloadData.{name}",
                        "type": kind_of(value),
                        "value": value,
                        "role": "contador de compras de peces",
                        "evidence": "E2: contador de tienda; no se vincula al saldo de fichas.",
                    }
                )
    if season is not None:
        for name in (
            "extraRewardChipTimesToday",
            "extraRewardChestNoChipTimes",
            "extraRewardChestTimes",
        ):
            if name in season:
                value = season[name]
                fields.append(
                    {
                        "path": f"seasonData.{name}",
                        "type": kind_of(value),
                        "value": value,
                        "role": "contador de recompensas de temporada",
                        "evidence": "E2: contador; no es el saldo de fichas.",
                    }
                )
    statistic_path = "StatisticsData.HallGameStatisticData._buyItemUseFishChipTimes"
    statistic_value = _nested(statistic, "StatisticsData", "HallGameStatisticData", "_buyItemUseFishChipTimes") if statistic is not None else MISSING
    if statistic_value is not MISSING:
        fields.append(
            {
                "path": f"statisticData.{statistic_path}",
                "type": kind_of(statistic_value),
                "entries": len(statistic_value) if isinstance(statistic_value, dict) else None,
                "role": "estadística de compras con fichas",
                "evidence": "E2: contador histórico observado en la muestra 8.6.0; no es el saldo.",
            }
        )

    distinct = {
        "season_chips": _nested(season, "chips") if season is not None else MISSING,
        "cumulative_fish_count": item.get("cumulativeFishCount", MISSING) if item is not None else MISSING,
    }
    return {
        "balance_path": "gameData.fishChip" if balance is not MISSING else None,
        "balance": balance if balance is not MISSING else None,
        "balance_is_integer": type(balance) is int,
        "fields": fields,
        "distinct_collections": {
            name: {"type": kind_of(value), "entries": len(value) if isinstance(value, (dict, list)) else None}
            for name, value in distinct.items()
            if value is not MISSING
        },
        "server_authority": "unknown",
    }


def character_report(
    game: Mapping[str, Any],
    *,
    character_codes: list[str] | None = None,
    skin_catalog: Mapping[str, Mapping[str, str]] | None = None,
    skill_catalog: Mapping[str, str] | None = None,
) -> dict[str, object]:
    """Cruza los mapas de héroes con catálogos opcionales.

    ``skin_catalog`` usa la forma ``{"c0": {"c0_skin0": "Knight"}}`` y
    ``skill_catalog`` la forma ``{"Character0_skill_0_name": "Dual Wield"}``.
    El catálogo solo aporta nombres; no se deduce posesión a partir de él.
    """
    unlocks = game.get("heroUnlock") if isinstance(game.get("heroUnlock"), dict) else {}
    levels = game.get("heroLevel") if isinstance(game.get("heroLevel"), dict) else {}
    skills = game.get("heroSkill") if isinstance(game.get("heroSkill"), dict) else {}
    skill_unlocks = game.get("heroSkillUnlock") if isinstance(game.get("heroSkillUnlock"), dict) else {}
    skins = game.get("skinLock") if isinstance(game.get("skinLock"), dict) else {}
    selected_skins = game.get("currentSkinDatas") if isinstance(game.get("currentSkinDatas"), dict) else {}

    codes = list(character_codes) if character_codes is not None else sorted(
        set(unlocks) | set(levels) | set(skills) | set(skill_unlocks) | set(skins)
    )
    catalog_index = {code: index for index, code in enumerate(character_codes or [])}
    rows = []
    for code in codes:
        index = catalog_index.get(code)
        group = f"c{index}" if index is not None else None
        skin_names = skin_catalog.get(group, {}) if group and skin_catalog else {}
        skill_rows = []
        for entry in skill_unlocks.get(code, []) if isinstance(skill_unlocks.get(code), list) else []:
            if isinstance(entry, dict) and type(entry.get("Key")) is int:
                key = entry["Key"]
                name = skill_catalog.get(f"Character{index}_skill_{key}_name") if index is not None and skill_catalog else None
                skill_rows.append({"key": key, "unlocked": entry.get("Value"), "name": name})
        skin_values = []
        for entry in skins.get(code, []) if isinstance(skins.get(code), list) else []:
            if isinstance(entry, dict) and type(entry.get("Key")) is int:
                key = entry["Key"]
                value = entry.get("Value")
                skin_values.append(
                    {
                        "key": key,
                        "state": value,
                        "name": skin_names.get(f"{group}_skin{key}") if group else None,
                    }
                )
        rows.append(
            {
                "code": code,
                "catalog_index": index,
                "unlocked": unlocks.get(code, MISSING),
                "level": levels.get(code, MISSING),
                "selected_skill": skills.get(code, MISSING),
                "skills": skill_rows,
                "selected_skin": selected_skins.get(code, MISSING),
                "skins": skin_values,
            }
        )
    return {
        "characters": rows,
        "counts": {
            "characters": len(rows),
            "unlocked": sum(row["unlocked"] is True for row in rows),
            "selected_skins": sum(row["selected_skin"] is not MISSING for row in rows),
        },
    }
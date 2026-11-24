"""Conocimiento y diagnóstico conservador de recursos del agregado.

Ninguna relación transaccional se considera demostrada por coincidencia de valores.
El planificador estricto no autoriza escrituras hasta contar con esa evidencia.
"""
from dataclasses import dataclass
from typing import Any

from ..cloud_save import reconstruct_cloud_save, unpack_cloud_save
from ..parsers.json_document import parse_json


@dataclass(frozen=True)
class Resource:
    id: str
    name: str
    observed_paths: tuple[tuple[str, ...], ...]
    evidence: str
    transactional_relations_confirmed: bool = False


RESOURCES = {
    "gems": Resource("gems", "Gemas", (("gameData", "gems"),
        ("gameData", "lastGems"), ("gameData", "varGems"),
        ("gameData", "cumulativeGems"), ("gameData", "cumulativeConsumeGems")),
        "docs/research/phase5-5/save-schema-880.md; docs/research/phase5-8/cloud-roundtrip.md"),
    "fish": Resource("fish", "Pescados", (("itemData", "cumulativeFishCount"),),
        "docs/research/phase5-5/schema-diff-860-880.md"),
    "season_coin": Resource("season_coin", "Monedas de temporada", (("seasonData", "coin"),
        ("seasonData", "gainedCoinToday"), ("seasonData", "cumulativeCoinCount")),
        "docs/phase3/SUPPORTED_FIELDS.md"),
}


class ConsistencyUnknown(ValueError):
    """No hay evidencia suficiente para garantizar una operación."""


def inspect_resource(document: dict, resource_id: str) -> dict[str, str]:
    """Informa presencia y tipo; no presupone que campos similares sean equivalentes."""
    resource = RESOURCES[resource_id]
    result = {}
    for path in resource.observed_paths:
        value: Any = document
        for part in path:
            if not isinstance(value, dict) or part not in value:
                value = _MISSING
                break
            value = value[part]
        result[".".join(path)] = "missing" if value is _MISSING else type(value).__name__
    return result


_MISSING = object()


def plan_consistent_edit(document: dict, resource_id: str, value: object) -> None:
    """Rechaza de forma explícita mientras se desconozcan las dependencias."""
    resource = RESOURCES[resource_id]
    if not resource.transactional_relations_confirmed:
        raise ConsistencyUnknown(f"Dependencias transaccionales desconocidas: {resource_id}")
    raise ConsistencyUnknown("No existe un planificador validado para este recurso")


def aggregate_tree(source: bytes) -> dict:
    reconstruct_cloud_save(source)
    _, document = unpack_cloud_save(source)
    return parse_json(document)


def structural_diff(before: Any, after: Any, path: tuple = ()) -> list[dict]:
    """Cambios por ruta; valores se devuelven solo al llamador local, no se registran."""
    if type(before) is not type(after):
        return [{"path": path, "kind": "type", "before": before, "after": after}]
    if isinstance(before, dict):
        changes = []
        for key in sorted(before.keys() | after.keys()):
            if key not in before:
                changes.append({"path": path + (key,), "kind": "added", "after": after[key]})
            elif key not in after:
                changes.append({"path": path + (key,), "kind": "removed", "before": before[key]})
            else:
                changes.extend(structural_diff(before[key], after[key], path + (key,)))
        return changes
    if isinstance(before, list):
        changes = []
        for i in range(max(len(before), len(after))):
            if i >= len(before):
                changes.append({"path": path + (i,), "kind": "added", "after": after[i]})
            elif i >= len(after):
                changes.append({"path": path + (i,), "kind": "removed", "before": before[i]})
            else:
                changes.extend(structural_diff(before[i], after[i], path + (i,)))
        return changes
    return [] if before == after else [{"path": path, "kind": "changed", "before": before, "after": after}]

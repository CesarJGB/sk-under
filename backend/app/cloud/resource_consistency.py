"""Estructuras observadas y comprobaciones de consistencia del agregado."""
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
    aggregate_versions: frozenset[int] = frozenset()
    integer_range: tuple[int, int] | None = None


RESOURCES = {
    "gems": Resource("gems", "Gemas", (("gameData", "gems"),
        ("gameData", "lastGems"), ("gameData", "varGems"),
        ("gameData", "cumulativeGems"), ("gameData", "cumulativeConsumeGems")),
        "docs/research/phase6-11/README.md",
        aggregate_versions=frozenset({1}), integer_range=(0, 2_147_483_647)),
    "fish": Resource("fish", "Pescados", (("itemData", "cumulativeFishCount"),),
        "docs/research/phase5-5/schema-diff-860-880.md"),
    "season_coin": Resource("season_coin", "Monedas de temporada", (("seasonData", "coin"),
        ("seasonData", "gainedCoinToday"), ("seasonData", "cumulativeCoinCount")),
        "docs/phase3/SUPPORTED_FIELDS.md"),
}


class ConsistencyUnknown(ValueError):
    """No hay evidencia suficiente para garantizar una operación."""


class IncompatibleResource(ValueError):
    """El recurso no encaja en la estructura respaldada por las muestras."""


class ResourceDiscrepancy(ValueError):
    """La edición no preservaría una relación observada en el cliente."""


GEMS_PREFERENCES = {
    "gems": "gems",
    "last_gems": "lastGems",
    "var_gems": "varGems",
    "cumulative_gems": "cumulativeGems",
    "cumulative_consume_gems": "cumulativeConsumeGems",
}


def validate_resource_shape(document: dict, resource_id: str) -> None:
    """Valida el perfil del agregado sin exigir campos auxiliares para leerlo."""
    resource = RESOURCES[resource_id]
    version = document.get("serialzedVersion")
    if type(version) is not int or version not in resource.aggregate_versions:
        raise IncompatibleResource("La versión del agregado no está verificada para editar este recurso.")
    if resource_id == "gems":
        data = document.get("gameData")
        if not isinstance(data, dict):
            raise IncompatibleResource("Se requiere gameData como objeto JSON.")
        # Los cinco miembros observados son Int32 en el modelo 8.8.0. Los
        # auxiliares ausentes no se inventan. No se imponen signos ni igualdades.
        for _, key in resource.observed_paths:
            if key in data and (type(data[key]) is not int or not -(2**31) <= data[key] < 2**31):
                raise IncompatibleResource(f"gameData.{key} debe ser un entero de 32 bits.")


def plan_gems_transition(document: dict, target: int) -> dict[str, int]:
    """Planifica las rutas que mantienen la relación observada en ConsumeGem."""
    validate_resource_shape(document, "gems")
    data = document["gameData"]
    if data.get("gems") == target:
        return {}  # La confirmación impide subir operaciones sin cambios.
    if "lastGems" not in data or "varGems" not in data:
        raise ConsistencyUnknown("Faltan lastGems o varGems para comprobar la consistencia de las gemas.")
    effective = data["lastGems"] + data["varGems"]
    minimum, maximum = RESOURCES["gems"].integer_range
    if not minimum <= effective <= maximum:
        raise ConsistencyUnknown("El saldo calculado queda fuera del intervalo verificado.")
    if target == effective:
        return {"gems": target}
    if data.get("gems") != effective:
        raise ResourceDiscrepancy(
            f"El saldo descargado difiere del saldo conciliado ({effective}). "
            "Primero prepara una edición con el saldo conciliado."
        )
    # Mantener la base previa y los contadores de transacciones reales. La
    # diferencia es la única variación que satisface la suma con esa base.
    variation = target - data["lastGems"]
    if not -(2**31) <= variation < 2**31:
        raise ConsistencyUnknown("La variación de gemas quedaría fuera del intervalo de 32 bits.")
    return {"gems": target, "varGems": variation}


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

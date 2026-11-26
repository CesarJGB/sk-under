"""Editor experimental de decoraciones del vestíbulo y del jardín.

La evidencia real separa tres mecanismos distintos:

* ``itemData.roomDecorateDic``: la presencia de una clave de objeto indica que el
  objeto está desbloqueado. La cuenta avanzada tiene los diez objetos observados
  y la nueva solo ``ItemEggMachine``; por eso crear la clave con ``[0]`` es la
  transición compatible documentada. ``[0]`` no se interpreta como nivel máximo.
* ``gameData.roomObjectLevel``: niveles de mejora por objeto. La cuenta avanzada
  confirma nivel 5 en ``Book``, ``CatFood``, ``Planet`` y ``Safe`` y nivel 1 en
  ``Chest``; solo se permite subir hasta el máximo observado de cada clave.
* ``itemData.blueprints``: las apariencias temáticas (vestíbulo, jardín, hall,
  área mágica y taller) se poseen como planos. Este módulo las expone en modo de
  lectura; su obtención e investigación se realizan con el escritor de planos.

No se edita ``gameData.currentRoomDecorate`` ni ``unlockRoomDecorate`` porque su
significado y el mapa de selección todavía no están determinados.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from hashlib import sha256
from typing import Any, Mapping

from ..cloud_save import (
    MAX_INPUT_BYTES,
    AggregateFormatError,
    CloudSaveError,
    JsonObject,
    reconstruct_cloud_save,
    unpack_cloud_save,
)
from ..parsers.json_document import parse_json
from .blueprint_editor import blueprints_snapshot, is_decorative_blueprint
from .gems_editor import serialize_aggregate
from .lab import BinaryDiff, binary_diff

DECORATE_PATH = "itemData.roomDecorateDic"
ROOM_LEVEL_PATH = "gameData.roomObjectLevel"
ROOM_DECORATE_PATH = "gameData.currentRoomDecorate"
UNLOCK_LIST_PATH = "gameData.unlockRoomDecorate"
ROOM_LEVEL_VALUE = "gameData.roomLevel"
MAX_LEVEL = 5
MAX_OBJECTS = 10
APPEARANCE_SUBCATEGORIES = frozenset(
    {"room_skin", "garden_skin", "hall_skin", "magic_area_skin", "work_shop_skin"}
)

# Objetos observados en las dos cuentas reales. La etiqueta es solo de interfaz.
DECORATION_OBJECTS: dict[str, str] = {
    "ItemEggMachine": "Máquina de huevos",
    "ItemTrashCan": "Papelera",
    "ObjectBooks": "Estantería de libros",
    "ObjectDrinkSeller": "Máquina expendedora",
    "ObjectFishBowl": "Pecera",
    "ObjectMagicWell": "Pozo mágico",
    "ObjectMysteriouStatue": "Estatua misteriosa",
    "ObjectPlant": "Planta del vestíbulo",
    "ObjectSafe": "Caja fuerte",
    "PetFood": "Zona de alimentación de mascotas",
}

# Nivel máximo realmente observado por clave; no se extrapola a claves nuevas.
ROOM_LEVEL_MAX_OBSERVED: dict[str, int] = {
    "Book": 5,
    "CatFood": 5,
    "Chest": 1,
    "Planet": 5,
    "Safe": 5,
}

DECORATION_LIMITATION = (
    "La presencia en roomDecorateDic se interpreta como objeto desbloqueado porque "
    "la cuenta avanzada contiene los diez objetos y la nueva solo la máquina de "
    "huevos. El valor [0] se conserva tal cual y no se trata como nivel. Los niveles "
    "solo suben hasta el máximo observado por clave (5 en Book/CatFood/Planet/Safe, "
    "1 en Chest). La selección de apariencia activa depende de currentRoomDecorate, "
    "cuyo mapa de valores aún no está determinado: no se edita. La eficacia de las "
    "transiciones debe validarse en Android físico."
)


class DecorationEditError(CloudSaveError):
    code = "decoration_edit"


class InvalidDecorationPlan(DecorationEditError):
    code = "decoration_plan_invalid"


class UnsupportedDecorationSerialization(DecorationEditError):
    code = "decoration_unsupported_serialization"


class DecorationFieldMissing(DecorationEditError):
    code = "decoration_field_missing"


class DecorationFieldIncompatible(DecorationEditError):
    code = "decoration_field_incompatible"


class DecorationVerificationError(DecorationEditError):
    code = "decoration_verification"


class OutdatedDecorationDraft(DecorationEditError):
    code = "decoration_outdated"


def _validated_document(source: bytes) -> tuple[JsonObject, int, bytes]:
    try:
        raw = source.encode("utf-8") if isinstance(source, str) else bytes(source)
    except (UnicodeEncodeError, TypeError):
        raise UnsupportedDecorationSerialization("El guardado no es UTF-8 válido.") from None
    if not raw or len(raw) > MAX_INPUT_BYTES:
        raise UnsupportedDecorationSerialization("El tamaño del guardado no es válido.")
    try:
        reconstruct_cloud_save(raw)
        encoding, document = unpack_cloud_save(raw)
    except AggregateFormatError as exc:
        raise UnsupportedDecorationSerialization(str(exc)) from exc
    if encoding != "json":
        raise UnsupportedDecorationSerialization("El guardado no usa el formato JSON esperado.")
    try:
        root = parse_json(document)
    except (ValueError, RecursionError) as exc:
        raise UnsupportedDecorationSerialization("El guardado no contiene JSON válido.") from exc
    if not isinstance(root, dict):
        raise UnsupportedDecorationSerialization("El guardado no contiene un objeto raíz.")
    if not isinstance(root.get("serialzedVersion"), int):
        raise UnsupportedDecorationSerialization("El guardado no declara serialzedVersion.")
    try:
        serialized = serialize_aggregate(root)
    except (TypeError, ValueError) as exc:
        raise UnsupportedDecorationSerialization(f"No se pudo serializar el guardado: {exc}") from exc
    if serialized != raw:
        raise UnsupportedDecorationSerialization(
            "La serialización canónica no coincide con el guardado descargado."
        )
    return root, root["serialzedVersion"], raw


def _objects(root: Mapping[str, Any]) -> dict[str, Any]:
    item_data = root.get("itemData")
    if not isinstance(item_data, dict) or not isinstance(item_data.get("roomDecorateDic"), dict):
        raise DecorationFieldMissing("No existe itemData.roomDecorateDic como mapa de objetos.")
    return item_data["roomDecorateDic"]


def _levels(root: Mapping[str, Any]) -> dict[str, Any]:
    game_data = root.get("gameData")
    if not isinstance(game_data, dict) or not isinstance(game_data.get("roomObjectLevel"), dict):
        raise DecorationFieldMissing("No existe gameData.roomObjectLevel como mapa de niveles.")
    return game_data["roomObjectLevel"]


def normalize_decoration_plan(raw: object) -> dict[str, object]:
    if not isinstance(raw, Mapping):
        raise InvalidDecorationPlan("decorations debe ser un objeto JSON.")
    unknown = set(raw) - {"objects", "levels"}
    if unknown:
        raise InvalidDecorationPlan(f"decorations contiene claves no autorizadas: {sorted(unknown)}.")
    raw_objects = raw.get("objects") or []
    raw_levels = raw.get("levels") or {}
    if isinstance(raw_objects, Mapping):
        objects = [key for key, value in raw_objects.items() if value is True]
        invalid = [key for key, value in raw_objects.items() if value is not True]
        if invalid:
            raise InvalidDecorationPlan("objects solo admite el valor true para desbloquear.")
    elif isinstance(raw_objects, list):
        objects = list(raw_objects)
    else:
        raise InvalidDecorationPlan("decorations.objects debe ser una lista o un mapa.")
    if len(objects) > MAX_OBJECTS:
        raise InvalidDecorationPlan(f"decorations.objects supera el máximo de {MAX_OBJECTS}.")
    normalized_objects: list[str] = []
    for object_id in objects:
        if not isinstance(object_id, str) or object_id not in DECORATION_OBJECTS:
            raise InvalidDecorationPlan(f"{object_id!r} no es un objeto de vestíbulo observado.")
        if object_id in normalized_objects:
            raise InvalidDecorationPlan(f"decorations.objects repite {object_id}.")
        normalized_objects.append(object_id)
    if isinstance(raw_levels, list):
        level_entries: dict[str, object] = {}
        for item in raw_levels:
            if not isinstance(item, Mapping) or not isinstance(item.get("id"), str):
                raise InvalidDecorationPlan("decorations.levels contiene una entrada inválida.")
            if item["id"] in level_entries:
                raise InvalidDecorationPlan(f"decorations.levels repite {item['id']}.")
            level_entries[item["id"]] = item.get("level")
    elif isinstance(raw_levels, Mapping):
        level_entries = dict(raw_levels)
    else:
        raise InvalidDecorationPlan("decorations.levels debe ser un objeto o una lista.")
    normalized_levels: dict[str, int] = {}
    for key, value in level_entries.items():
        if not isinstance(key, str) or key not in ROOM_LEVEL_MAX_OBSERVED:
            raise InvalidDecorationPlan(f"{key!r} no tiene un máximo observado para mejorarse.")
        if type(value) is not int or value < 1 or value > ROOM_LEVEL_MAX_OBSERVED[key]:
            raise InvalidDecorationPlan(
                f"{key} solo admite un nivel entre 1 y {ROOM_LEVEL_MAX_OBSERVED[key]}."
            )
        normalized_levels[key] = value
    if not normalized_objects and not normalized_levels:
        raise InvalidDecorationPlan("decorations no contiene ningún cambio.")
    return {
        "objects": sorted(normalized_objects),
        "levels": dict(sorted(normalized_levels.items())),
    }


def decorations_snapshot(payload: Mapping[str, Any]) -> dict[str, object]:
    item_data = payload.get("itemData")
    game_data = payload.get("gameData")
    objects = item_data.get("roomDecorateDic") if isinstance(item_data, dict) else None
    levels = game_data.get("roomObjectLevel") if isinstance(game_data, dict) else None
    available = isinstance(objects, dict) and isinstance(levels, dict)
    object_map = objects if isinstance(objects, dict) else {}
    level_map = levels if isinstance(levels, dict) else {}

    object_rows: list[dict[str, object]] = []
    for object_id, label in DECORATION_OBJECTS.items():
        value = object_map.get(object_id)
        unlocked = object_id in object_map
        object_rows.append(
            {
                "id": object_id,
                "label": label,
                "unlocked": unlocked,
                "value": value,
                "editable": available and not unlocked,
                "reason": (
                    "Ya desbloqueado; no se elimina."
                    if unlocked
                    else "No desbloqueado; se puede crear la clave con [0]."
                ),
                "path": f"{DECORATE_PATH}.{object_id}" if unlocked else None,
            }
        )
    unknown_objects = sorted(key for key in object_map if key not in DECORATION_OBJECTS)

    level_rows: list[dict[str, object]] = []
    for key, max_observed in ROOM_LEVEL_MAX_OBSERVED.items():
        value = level_map.get(key)
        valid = type(value) is int and value >= 0
        if not valid:
            reason = "No existe un nivel entero compatible; no se crea."
        elif value > max_observed:
            reason = f"Nivel {value} por encima del máximo observado {max_observed}."
        elif value == max_observed:
            reason = f"Ya está en el máximo observado ({max_observed})."
        else:
            reason = f"Se puede subir hasta el máximo observado ({max_observed})."
        level_rows.append(
            {
                "id": key,
                "level": value if valid else None,
                "max_observed": max_observed,
                "editable": available and valid and value < max_observed,
                "reason": reason,
                "path": f"{ROOM_LEVEL_PATH}.{key}" if valid else None,
            }
        )
    unknown_levels = sorted(key for key in level_map if key not in ROOM_LEVEL_MAX_OBSERVED)

    blueprints = blueprints_snapshot(payload)
    appearances = [
        {
            "id": entry["id"],
            "key": entry["key"],
            "name": entry["name"],
            "subcategory": entry["subcategory"],
            "status": entry["status"],
            "obtained": entry["status"] is not None,
            "researched": entry["status"] == "Researched",
            "path": entry["path"],
        }
        for entry in blueprints["entries"]
        if is_decorative_blueprint(entry, entry["id"])
        and str(entry.get("target", "")).startswith(
            ("multi_room_skin_", "garden_skin_", "hall_skin_", "magic_area_skin_", "work_shop_skin_")
        )
    ]

    room_decoration = game_data.get("currentRoomDecorate") if isinstance(game_data, dict) else None
    unlock_list = game_data.get("unlockRoomDecorate") if isinstance(game_data, dict) else None
    room_level = game_data.get("roomLevel") if isinstance(game_data, dict) else None
    return {
        "available": available,
        "objects": object_rows,
        "levels": level_rows,
        "appearances": appearances,
        "unknown_objects": unknown_objects,
        "unknown_levels": unknown_levels,
        "room": {
            "current": room_decoration,
            "current_type": type(room_decoration).__name__ if room_decoration is not None else None,
            "room_level": room_level,
            "unlock_list": unlock_list if isinstance(unlock_list, list) else None,
            "selection_editable": False,
            "selection_reason": (
                "El mapa entre currentRoomDecorate y las apariencias no está determinado; "
                "no se inventa un valor de selección."
            ),
        },
        "experimental": True,
        "evidence_level": "E2",
        "note": (
            "Los objetos se desbloquean por presencia en roomDecorateDic. Las "
            "apariencias se poseen como planos y se consultan aquí; su obtención e "
            "investigación se realizan en la categoría Planos."
        ),
        "limitation": DECORATION_LIMITATION,
    }


def read_decorations(source: bytes) -> dict[str, object]:
    root, _, _ = _validated_document(source)
    return decorations_snapshot(root)


@dataclass
class DecorationChange:
    path: str
    before: object
    after: object
    created: bool = False

    def summary(self) -> dict[str, object]:
        return {
            "path": self.path,
            "before": self.before,
            "after": self.after,
            "created": self.created,
        }


@dataclass
class DecorationEdit:
    plan: dict[str, object]
    changes: list[DecorationChange]
    changed: bool
    original: bytes
    candidate: bytes
    original_sha256: str
    candidate_sha256: str
    binary: BinaryDiff
    serialzed_version: int
    changed_fields: tuple[str, ...] = field(default_factory=tuple)

    def summary(self) -> dict[str, object]:
        return {
            "field": "decorations",
            "plan": self.plan,
            "changes": [change.summary() for change in self.changes],
            "changed": self.changed,
            "original_size": len(self.original),
            "candidate_size": len(self.candidate),
            "original_sha256": self.original_sha256,
            "candidate_sha256": self.candidate_sha256,
            "byte_diff": self.binary.as_dict(),
            "changed_fields": list(self.changed_fields),
            "serialzed_version": self.serialzed_version,
        }


_MISSING = object()


def prepare_decoration_edit(source: bytes, plan: object) -> DecorationEdit:
    root, version, source = _validated_document(source)
    normalized = normalize_decoration_plan(plan)
    candidate = deepcopy(root)
    object_map = _objects(candidate)
    level_map = _levels(candidate)
    changes: list[DecorationChange] = []
    originals: list[tuple[str, object]] = []

    for object_id in normalized["objects"]:  # type: ignore[union-attr]
        before = object_map.get(object_id, _MISSING)
        if before is not _MISSING:
            continue
        object_map[object_id] = [0]
        originals.append((object_id, _MISSING))
        changes.append(DecorationChange(f"{DECORATE_PATH}.{object_id}", None, [0], created=True))

    for key, requested in normalized["levels"].items():  # type: ignore[union-attr]
        before = level_map.get(key, _MISSING)
        if before is _MISSING:
            raise DecorationFieldIncompatible(
                f"{ROOM_LEVEL_PATH}.{key} no existe; no se crean niveles sin evidencia."
            )
        if type(before) is not int:
            raise DecorationFieldIncompatible(f"{ROOM_LEVEL_PATH}.{key} no contiene un entero.")
        maximum = ROOM_LEVEL_MAX_OBSERVED[key]
        if requested < before:
            raise DecorationFieldIncompatible(f"{ROOM_LEVEL_PATH}.{key} no puede bajar de nivel.")
        if requested > maximum:
            raise DecorationFieldIncompatible(f"{ROOM_LEVEL_PATH}.{key} supera el máximo observado.")
        if requested == before:
            continue
        originals.append((key, before))
        level_map[key] = requested
        changes.append(DecorationChange(f"{ROOM_LEVEL_PATH}.{key}", before, requested))

    changed_fields = tuple(change.path for change in changes)
    if not changes:
        digest = sha256(source).hexdigest()
        return DecorationEdit(
            plan=normalized,
            changes=[],
            changed=False,
            original=source,
            candidate=source,
            original_sha256=digest,
            candidate_sha256=digest,
            binary=binary_diff(source, source),
            serialzed_version=version,
        )

    try:
        candidate_source = serialize_aggregate(candidate)
    except (TypeError, ValueError) as exc:
        raise DecorationVerificationError(f"No se pudo serializar el candidato: {exc}") from exc
    if len(candidate_source) > MAX_INPUT_BYTES:
        raise DecorationVerificationError("El guardado candidato supera el tamaño permitido.")
    try:
        reconstruct_cloud_save(candidate_source)
        encoding_name, document = unpack_cloud_save(candidate_source)
        if encoding_name != "json":
            raise DecorationVerificationError("El candidato no conserva el formato JSON.")
        reopened = parse_json(document)
    except (AggregateFormatError, ValueError) as exc:
        raise DecorationVerificationError(f"El candidato no se puede volver a abrir: {exc}") from exc
    if not isinstance(reopened, dict):
        raise DecorationVerificationError("El candidato no conserva el objeto raíz.")
    if serialize_aggregate(deepcopy(reopened)) != candidate_source:
        raise DecorationVerificationError("El candidato no es estable al reserializarlo.")

    reopened_objects = _objects(reopened)
    reopened_levels = _levels(reopened)
    for object_id in normalized["objects"]:  # type: ignore[union-attr]
        if reopened_objects.get(object_id) != [0]:
            raise DecorationVerificationError(f"No se conservó {DECORATE_PATH}.{object_id}.")
    for key, requested in normalized["levels"].items():  # type: ignore[union-attr]
        if reopened_levels.get(key) != requested:
            raise DecorationVerificationError(f"No se conservó {ROOM_LEVEL_PATH}.{key}.")

    for key, before in originals:
        if isinstance(key, str) and key in DECORATION_OBJECTS and before is _MISSING:
            reopened_objects.pop(key, None)
        elif before is not _MISSING:
            reopened_levels[key] = before
    if serialize_aggregate(reopened) != source:
        raise DecorationVerificationError(
            "La reversión del plan no reproduce el guardado original; hay cambios colaterales."
        )

    binary = binary_diff(source, candidate_source)
    if binary.first_difference is None:
        raise DecorationVerificationError("El plan no produjo una diferencia binaria verificable.")
    return DecorationEdit(
        plan=normalized,
        changes=changes,
        changed=True,
        original=source,
        candidate=candidate_source,
        original_sha256=sha256(source).hexdigest(),
        candidate_sha256=sha256(candidate_source).hexdigest(),
        binary=binary,
        serialzed_version=version,
        changed_fields=changed_fields,
    )


def require_decoration_write_compatibility(source: bytes, plan: object, candidate: bytes) -> None:
    try:
        expected = prepare_decoration_edit(source, plan).candidate
    except DecorationEditError as exc:
        if exc.code == DecorationVerificationError.code:
            raise
        raise DecorationEditError(f"El borrador de decoraciones ya no es compatible: {exc}") from exc
    if expected != candidate:
        raise OutdatedDecorationDraft("El borrador de decoraciones no coincide con el guardado actual.")

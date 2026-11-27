"""Editor experimental de decoraciones del vestíbulo y del jardín.

La evidencia real separa cuatro mecanismos distintos:

* ``itemData.roomDecorateDic``: la presencia de una clave de objeto indica que el
  objeto está poseído. La cuenta avanzada tiene los diez objetos observados y la
  nueva solo ``ItemEggMachine``. Crear la clave con ``[0]`` es necesario, pero
  **no suficiente** para que el objeto esté disponible dentro del juego.
* ``statisticData.event2Count``: contiene las banderas ``room_unlock_*`` que el
  juego consulta para habilitar instalaciones del vestíbulo. La cuenta avanzada
  tiene ``room_unlock_book``, ``room_unlock_safe``, ``room_unlock_pet_food``,
  ``room_unlock_trash_can``, ``room_unlock_plant``, ``room_unlock_cellar`` y
  ``room_unlock_magic_area``; la cuenta nueva no tiene ninguna. Este es el
  indicador funcional que faltaba en la fase 9.1.
* ``itemData.blueprints``: cuatro objetos decorativos (máquina expendedora,
  pecera, pozo mágico y estatua) requieren que su plano esté investigado. Las
  apariencias temáticas también se poseen como planos y se exponen en lectura.
* ``gameData.roomObjectLevel``: niveles de mejora por objeto. Las muestras
  avanzadas confirman nivel 5 en ``Book``, ``CatFood``, ``Chest``, ``Planet`` y
  ``Safe``; solo se permite subir hasta el máximo observado de cada clave.

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
from .blueprint_editor import (
    blueprint_encoding,
    blueprints_snapshot,
    decode_blueprint_status,
    encode_blueprint_status,
    is_decorative_blueprint,
    preferred_blueprint_key,
    resolve_blueprint_key,
)
from .gems_editor import serialize_aggregate
from .aggregate_cache import validated_document
from .lab import BinaryDiff, binary_diff

DECORATE_PATH = "itemData.roomDecorateDic"
ROOM_LEVEL_PATH = "gameData.roomObjectLevel"
ROOM_DECORATE_PATH = "gameData.currentRoomDecorate"
UNLOCK_LIST_PATH = "gameData.unlockRoomDecorate"
ROOM_LEVEL_VALUE = "gameData.roomLevel"
EVENT_COUNT_PATH = "statisticData.event2Count"
BLUEPRINTS_PATH = "itemData.blueprints"
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

# Requisitos funcionales observados en las muestras avanzadas. La presencia en
# roomDecorateDic es posesión; estas banderas y planos son los que habilitan el
# uso dentro del juego. No se añaden objetos sin evidencia.
OBJECT_UNLOCK_FLAGS: dict[str, tuple[str, ...]] = {
    "ItemEggMachine": (),
    "ItemTrashCan": ("room_unlock_trash_can",),
    "ObjectBooks": ("room_unlock_book",),
    "ObjectDrinkSeller": (),
    "ObjectFishBowl": (),
    "ObjectMagicWell": ("room_unlock_magic_area",),
    "ObjectMysteriouStatue": (),
    "ObjectPlant": ("room_unlock_plant",),
    "ObjectSafe": ("room_unlock_safe",),
    "PetFood": ("room_unlock_pet_food",),
}
OBJECT_UNLOCK_BLUEPRINTS: dict[str, tuple[str, ...]] = {
    "ItemEggMachine": (),
    "ItemTrashCan": (),
    "ObjectBooks": (),
    "ObjectDrinkSeller": ("blueprint_room_decorate_drink_seller",),
    "ObjectFishBowl": ("blueprint_room_decorate_fishbowl",),
    "ObjectMagicWell": ("blueprint_room_decorate_magic_well",),
    "ObjectMysteriouStatue": ("blueprint_room_decorate_mysteriou_statue",),
    "ObjectPlant": (),
    "ObjectSafe": (),
    "PetFood": (),
}
# Al mejorar estos objetos se garantiza la bandera que habilita la instalación.
# Planet no tiene bandera identificada y no se inventa.
ROOM_LEVEL_GATES: dict[str, str] = {
    "Book": "room_unlock_book",
    "CatFood": "room_unlock_pet_food",
    "Chest": "room_unlock_cellar",
    "Safe": "room_unlock_safe",
}

# Nivel máximo realmente observado por clave; no se extrapola a claves nuevas.
ROOM_LEVEL_MAX_OBSERVED: dict[str, int] = {
    "Book": 5,
    "CatFood": 5,
    "Chest": 5,
    "Planet": 5,
    "Safe": 5,
}

DECORATION_LIMITATION = (
    "roomDecorateDic indica posesión, no disponibilidad funcional. El juego "
    "consulta las banderas room_unlock_* de statisticData.event2Count; los cuatro "
    "objetos decorativos (máquina expendedora, pecera, pozo mágico y estatua) "
    "además requieren su plano investigado. El editor crea la clave del objeto y "
    "sus requisitos conocidos, pero la eficacia debe validarse en el juego. [0] no "
    "se interpreta como nivel. Los niveles solo suben hasta el máximo observado por "
    "clave (5). La selección de apariencia activa depende de currentRoomDecorate, "
    "cuyo mapa de valores aún no está determinado: no se edita. La máquina de "
    "huevos se posee sin requisitos conocidos. No se identificaron banderas para la "
    "estatua ni para la máquina expendedora, ni el significado de "
    "room_decorate_fishbowl_level."
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
    root, version = validated_document(
        source,
        unsupported_error=UnsupportedDecorationSerialization,
        unsupported_message=(
            "La copia no usa la serialización canónica observada; no se puede garantizar "
            "que el cambio sea granular."
        ),
    )
    return root, version, bytes(source)
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


def _event_counters(root: Mapping[str, Any]) -> dict[str, Any]:
    statistic_data = root.get("statisticData")
    if not isinstance(statistic_data, dict) or not isinstance(
        statistic_data.get("event2Count"), dict
    ):
        raise DecorationFieldMissing(
            "No existe statisticData.event2Count; no se crean banderas de desbloqueo."
        )
    return statistic_data["event2Count"]


def _blueprints(root: Mapping[str, Any]) -> dict[str, Any]:
    item_data = root.get("itemData")
    if not isinstance(item_data, dict) or not isinstance(item_data.get("blueprints"), dict):
        raise DecorationFieldMissing(
            "No existe itemData.blueprints; no se crean planos de decoración."
        )
    return item_data["blueprints"]


def _requirement_rows(
    object_id: str, counters: Mapping[str, Any], blueprints: Mapping[str, Any]
) -> list[dict[str, object]]:
    requirements: list[dict[str, object]] = []
    for flag in OBJECT_UNLOCK_FLAGS.get(object_id, ()):
        value = counters.get(flag)
        met = type(value) is int and value >= 1
        requirements.append(
            {
                "kind": "flag",
                "key": flag,
                "value": value,
                "met": met,
                "path": f"{EVENT_COUNT_PATH}.{flag}",
            }
        )
    for blueprint_id in OBJECT_UNLOCK_BLUEPRINTS.get(object_id, ()):
        key = resolve_blueprint_key(blueprint_id, blueprints)
        value = blueprints.get(key) if key is not None else None
        status = decode_blueprint_status(value)
        requirements.append(
            {
                "kind": "blueprint",
                "key": key or blueprint_id,
                "value": value,
                "status": status,
                "met": status == "Researched",
                "path": f"{BLUEPRINTS_PATH}.{key}" if key is not None else None,
            }
        )
    return requirements


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
    statistic_data = payload.get("statisticData")
    objects = item_data.get("roomDecorateDic") if isinstance(item_data, dict) else None
    levels = game_data.get("roomObjectLevel") if isinstance(game_data, dict) else None
    available = isinstance(objects, dict) and isinstance(levels, dict)
    object_map = objects if isinstance(objects, dict) else {}
    level_map = levels if isinstance(levels, dict) else {}
    counter_map = (
        statistic_data.get("event2Count")
        if isinstance(statistic_data, dict) and isinstance(statistic_data.get("event2Count"), dict)
        else {}
    )
    blueprint_map = (
        item_data.get("blueprints")
        if isinstance(item_data, dict) and isinstance(item_data.get("blueprints"), dict)
        else {}
    )

    object_rows: list[dict[str, object]] = []
    for object_id, label in DECORATION_OBJECTS.items():
        value = object_map.get(object_id)
        unlocked = object_id in object_map
        requirements = _requirement_rows(object_id, counter_map, blueprint_map)
        functional = unlocked and all(row["met"] is True for row in requirements)
        if not available:
            reason = "No hay mapas de objetos y niveles compatibles."
        elif functional:
            reason = "Disponible: objeto y requisitos presentes; no se elimina."
        elif unlocked:
            reason = "Presente, pero faltan requisitos para que esté disponible."
        elif requirements:
            reason = "No poseído; se crea la clave y se completan sus requisitos."
        else:
            reason = "No poseído; se puede crear la clave con [0]."
        object_rows.append(
            {
                "id": object_id,
                "label": label,
                "unlocked": unlocked,
                "functional": functional,
                "value": value,
                "requirements": requirements,
                "editable": available and not functional,
                "reason": reason,
                "path": f"{DECORATE_PATH}.{object_id}" if unlocked else None,
            }
        )
    unknown_objects = sorted(key for key in object_map if key not in DECORATION_OBJECTS)

    level_rows: list[dict[str, object]] = []
    for key, max_observed in ROOM_LEVEL_MAX_OBSERVED.items():
        value = level_map.get(key)
        valid = type(value) is int and value >= 0
        gate = ROOM_LEVEL_GATES.get(key)
        gate_value = counter_map.get(gate) if gate else None
        gate_met = None if gate is None else type(gate_value) is int and gate_value >= 1
        gate_compatible = gate is None or gate_value is None or (
            type(gate_value) is int and gate_value >= 0
        )
        if not valid:
            reason = "No existe un nivel entero compatible; no se crea."
        elif value > max_observed:
            reason = f"Nivel {value} por encima del máximo observado {max_observed}."
        elif value == max_observed:
            reason = f"Ya está en el máximo observado ({max_observed})."
        else:
            reason = f"Se puede subir hasta el máximo observado ({max_observed})."
            if gate and not gate_met:
                reason += (
                    f" Se activará {gate}." if gate_compatible else f" {gate} no es entero."
                )
        level_rows.append(
            {
                "id": key,
                "level": value if valid else None,
                "max_observed": max_observed,
                "gate": gate,
                "gate_value": gate_value,
                "gate_met": gate_met,
                "editable": available and valid and value < max_observed and gate_compatible,
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
            "roomDecorateDic indica posesión. La disponibilidad funcional exige las "
            "banderas room_unlock_* de statisticData.event2Count y, en cuatro objetos, "
            "el plano investigado. Las apariencias se consultan aquí; su obtención e "
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
    requested_objects: dict[str, object] = {}
    created_objects: dict[str, object] = {}
    changed_levels: dict[str, int] = {}
    changed_flags: dict[str, object] = {}
    changed_blueprints: dict[str, tuple[object, object]] = {}
    flags_seen: set[str] = set()
    blueprints_seen: set[str] = set()
    counter_map: dict[str, Any] | None = None
    blueprint_map: dict[str, Any] | None = None

    def ensure_flag(flag: str) -> None:
        nonlocal counter_map
        if flag in flags_seen:
            return
        flags_seen.add(flag)
        if counter_map is None:
            counter_map = _event_counters(candidate)
        before = counter_map.get(flag, _MISSING)
        if before is _MISSING:
            counter_map[flag] = 1
            changed_flags[flag] = _MISSING
            changes.append(
                DecorationChange(f"{EVENT_COUNT_PATH}.{flag}", None, 1, created=True)
            )
            return
        if type(before) is not int or before < 0:
            raise DecorationFieldIncompatible(
                f"{EVENT_COUNT_PATH}.{flag} no contiene un entero no negativo compatible."
            )
        if before >= 1:
            return
        counter_map[flag] = 1
        changed_flags[flag] = before
        changes.append(DecorationChange(f"{EVENT_COUNT_PATH}.{flag}", before, 1))

    def ensure_blueprint(blueprint_id: str) -> None:
        nonlocal blueprint_map
        if blueprint_id in blueprints_seen:
            return
        blueprints_seen.add(blueprint_id)
        if blueprint_map is None:
            blueprint_map = _blueprints(candidate)
        key = preferred_blueprint_key(blueprint_id, blueprint_map)
        before = blueprint_map.get(key, _MISSING)
        if before is not _MISSING:
            status = decode_blueprint_status(before)
            if status is None:
                raise DecorationFieldIncompatible(
                    f"{BLUEPRINTS_PATH}.{key} declara un estado desconocido y no se sobrescribe."
                )
            if status == "Researched":
                return
            encoding = "integer" if type(before) is int else "text"
        else:
            encoding = blueprint_encoding(blueprint_map)
        after = encode_blueprint_status("Researched", encoding)
        blueprint_map[key] = after
        changed_blueprints[key] = (before, after)
        changes.append(
            DecorationChange(
                f"{BLUEPRINTS_PATH}.{key}",
                None if before is _MISSING else before,
                after,
                created=before is _MISSING,
            )
        )

    for object_id in normalized["objects"]:  # type: ignore[union-attr]
        before = object_map.get(object_id, _MISSING)
        requested_objects[object_id] = before
        if before is _MISSING:
            object_map[object_id] = [0]
            created_objects[object_id] = _MISSING
            changes.append(DecorationChange(f"{DECORATE_PATH}.{object_id}", None, [0], created=True))
        for flag in OBJECT_UNLOCK_FLAGS.get(object_id, ()):
            ensure_flag(flag)
        for blueprint_id in OBJECT_UNLOCK_BLUEPRINTS.get(object_id, ()):
            ensure_blueprint(blueprint_id)

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
        level_map[key] = requested
        changed_levels[key] = before
        changes.append(DecorationChange(f"{ROOM_LEVEL_PATH}.{key}", before, requested))
        gate = ROOM_LEVEL_GATES.get(key)
        if gate is not None:
            ensure_flag(gate)

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
    for object_id, before in requested_objects.items():
        expected = [0] if before is _MISSING else before
        if reopened_objects.get(object_id) != expected:
            raise DecorationVerificationError(f"No se conservó {DECORATE_PATH}.{object_id}.")
    for key, requested in normalized["levels"].items():  # type: ignore[union-attr]
        if reopened_levels.get(key) != requested:
            raise DecorationVerificationError(f"No se conservó {ROOM_LEVEL_PATH}.{key}.")
    if changed_flags:
        reopened_counters = _event_counters(reopened)
        for flag in changed_flags:
            if reopened_counters.get(flag) != 1:
                raise DecorationVerificationError(f"No se conservó {EVENT_COUNT_PATH}.{flag}.")
    if changed_blueprints:
        reopened_blueprints = _blueprints(reopened)
        for key, (_, after) in changed_blueprints.items():
            if reopened_blueprints.get(key) != after:
                raise DecorationVerificationError(f"No se conservó {BLUEPRINTS_PATH}.{key}.")

    for object_id in created_objects:
        reopened_objects.pop(object_id, None)
    for key, before in changed_levels.items():
        reopened_levels[key] = before
    if changed_flags:
        for flag, before in changed_flags.items():
            if before is _MISSING:
                reopened_counters.pop(flag, None)
            else:
                reopened_counters[flag] = before
    if changed_blueprints:
        for key, (before, _) in changed_blueprints.items():
            if before is _MISSING:
                reopened_blueprints.pop(key, None)
            else:
                reopened_blueprints[key] = before
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

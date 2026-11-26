"""Editor experimental de planos de fabricación.

``itemData.blueprints`` es un mapa ``clave -> "Got" | "Researched"``. La
muestra real usa tanto el identificador actual ``blueprint_*`` como alias
heredados sin el prefijo (por ejemplo ``multi_room_skin_20``). El escritor
permite crear registros ausentes que pertenecen al catálogo (o a los
identificadores decorativos observados) con las transiciones No obtenido ->
Got, No obtenido -> Researched y Got -> Researched. Nunca rebaja Researched a
Got, no inventa identificadores y conserva las claves desconocidas.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from hashlib import sha256
from typing import Any, Mapping

from ..catalogs.blueprints import load_blueprint_catalog
from ..cloud_save import (
    MAX_INPUT_BYTES,
    AggregateFormatError,
    CloudSaveError,
    JsonObject,
    reconstruct_cloud_save,
    unpack_cloud_save,
)
from ..parsers.json_document import parse_json
from .gems_editor import serialize_aggregate
from .lab import BinaryDiff, binary_diff

BLUEPRINTS_PATH = "itemData.blueprints"
BLUEPRINT_STATUSES = frozenset({"Got", "Researched"})
MAX_BLUEPRINTS = 296
BLUEPRINT_PREFIX = "blueprint_"
# La cuenta de 8.8.0 serializa el estado como entero: 1 = Got y 2 = Researched.
# El valor 2 no aparece en las muestras observadas, pero es la progresión natural
# del mismo enum y solo se acepta para subir desde Got. Nunca se escribe 0.
INTEGER_STATUSES = {1: "Got", 2: "Researched"}
INTEGER_VALUES = {"Got": 1, "Researched": 2}
DECORATIVE_SUBCATEGORIES = frozenset(
    {"room_skin", "garden_skin", "hall_skin", "magic_area_skin", "work_shop_skin", "observed"}
)
DECORATIVE_TARGET_PREFIXES = (
    "multi_room_skin_",
    "garden_skin_",
    "hall_skin_",
    "magic_area_skin_",
    "work_shop_skin_",
    "room_decorate_",
)


def is_decorative_blueprint(row: Mapping[str, Any] | None, blueprint_id: str = "") -> bool:
    if row is None:
        return False
    target = row.get("target")
    return (
        row.get("subcategory") in DECORATIVE_SUBCATEGORIES
        or isinstance(target, str)
        and target.startswith(DECORATIVE_TARGET_PREFIXES)
        or blueprint_id in _observed_extra_ids()
    )

BLUEPRINT_LIMITATION = (
    "La cuenta antigua guarda los estados como texto (Got/Researched) y la nueva "
    "como enteros (1 observado = Got; 2 = Researched se deduce del mismo enum y "
    "queda sin confirmar). El escritor crea registros ausentes solo para "
    "identificadores del catálogo o decorativos observados, respeta la codificación "
    "de cada cuenta, no rebaja Researched a Got y conserva las claves desconocidas. "
    "La eficacia todavía debe validarse en Android físico."
)


class BlueprintEditError(CloudSaveError):
    code = "blueprint_edit"


class InvalidBlueprintPlan(BlueprintEditError):
    code = "blueprint_plan_invalid"


class UnsupportedBlueprintSerialization(BlueprintEditError):
    code = "blueprint_unsupported_serialization"


class BlueprintFieldMissing(BlueprintEditError):
    code = "blueprint_field_missing"


class BlueprintFieldIncompatible(BlueprintEditError):
    code = "blueprint_field_incompatible"


class BlueprintCatalogMissing(BlueprintEditError):
    code = "blueprint_catalog_missing"


class BlueprintVerificationError(BlueprintEditError):
    code = "blueprint_verification"


class OutdatedBlueprintDraft(BlueprintEditError):
    code = "blueprint_outdated"


def _validated_document(source: bytes) -> tuple[JsonObject, int, bytes]:
    try:
        raw = source.encode("utf-8") if isinstance(source, str) else bytes(source)
    except (UnicodeEncodeError, TypeError):
        raise UnsupportedBlueprintSerialization("El guardado no es UTF-8 válido.") from None
    if not raw or len(raw) > MAX_INPUT_BYTES:
        raise UnsupportedBlueprintSerialization("El tamaño del guardado no es válido.")
    try:
        reconstruct_cloud_save(raw)
        encoding, document = unpack_cloud_save(raw)
    except AggregateFormatError as exc:
        raise UnsupportedBlueprintSerialization(str(exc)) from exc
    if encoding != "json":
        raise UnsupportedBlueprintSerialization("El guardado no usa el formato JSON esperado.")
    try:
        root = parse_json(document)
    except (ValueError, RecursionError) as exc:
        raise UnsupportedBlueprintSerialization("El guardado no contiene JSON válido.") from exc
    if not isinstance(root, dict):
        raise UnsupportedBlueprintSerialization("El guardado no contiene un objeto raíz.")
    if not isinstance(root.get("serialzedVersion"), int):
        raise UnsupportedBlueprintSerialization("El guardado no declara serialzedVersion.")
    try:
        serialized = serialize_aggregate(root)
    except (TypeError, ValueError) as exc:
        raise UnsupportedBlueprintSerialization(f"No se pudo serializar el guardado: {exc}") from exc
    if serialized != raw:
        raise UnsupportedBlueprintSerialization(
            "La serialización canónica no coincide con el guardado descargado."
        )
    return root, root["serialzedVersion"], raw


def _catalog() -> dict[str, object]:
    catalog = load_blueprint_catalog()
    if not catalog.get("available"):
        raise BlueprintCatalogMissing("El catálogo de planos no está disponible.")
    return catalog


def _alias(blueprint_id: str) -> str:
    return blueprint_id[len(BLUEPRINT_PREFIX):] if blueprint_id.startswith(BLUEPRINT_PREFIX) else blueprint_id


def resolve_blueprint_key(blueprint_id: str, target: Mapping[str, Any]) -> str | None:
    """Resuelve el identificador actual y el alias heredado sin inventar claves."""
    if blueprint_id in target:
        return blueprint_id
    alias = _alias(blueprint_id)
    if alias and alias in target:
        return alias
    return None


def _catalog_row(blueprint_id: str) -> Mapping[str, Any] | None:
    rows = _catalog().get("blueprints")
    if not isinstance(rows, dict):
        return None
    row = rows.get(blueprint_id)
    return row if isinstance(row, dict) else None


def preferred_blueprint_key(blueprint_id: str, target: Mapping[str, Any]) -> str:
    """Elige la forma de clave coherente con el guardado, sin duplicar alias.

    Los decorados se guardan históricamente sin ``blueprint_``; las armas,
    habilidades y skins conservan el prefijo. Si ya existe cualquiera de las dos
    formas se reutiliza esa clave.
    """
    existing = resolve_blueprint_key(blueprint_id, target)
    if existing is not None:
        return existing
    row = _catalog_row(blueprint_id)
    if blueprint_id.startswith(BLUEPRINT_PREFIX) and is_decorative_blueprint(row, blueprint_id):
        return _alias(blueprint_id)
    return blueprint_id


def _observed_extra_ids() -> frozenset[str]:
    from ..catalogs.blueprints import OBSERVED_EXTRA_IDS

    return frozenset(OBSERVED_EXTRA_IDS)


def decode_blueprint_status(value: object) -> str | None:
    if isinstance(value, str) and value in BLUEPRINT_STATUSES:
        return value
    if type(value) is int:
        return INTEGER_STATUSES.get(value)
    return None


def blueprint_encoding(target: Mapping[str, Any]) -> str:
    """Detecta la codificación dominante de la cuenta (texto o entero)."""
    text = integer = 0
    for value in target.values():
        if isinstance(value, str) and value in BLUEPRINT_STATUSES:
            text += 1
        elif type(value) is int and value in INTEGER_STATUSES:
            integer += 1
    return "integer" if integer > text else "text"


def encode_blueprint_status(status: str, encoding: str) -> object:
    if status not in BLUEPRINT_STATUSES:
        raise InvalidBlueprintPlan(f"Estado de plano desconocido: {status!r}.")
    if encoding == "integer":
        return INTEGER_VALUES[status]
    return status


def normalize_blueprint_plan(raw: object) -> dict[str, str]:
    if isinstance(raw, Mapping):
        entries = [{"id": item_id, "status": status} for item_id, status in raw.items()]
    elif isinstance(raw, list):
        entries = list(raw)
    else:
        raise InvalidBlueprintPlan("blueprints debe ser una lista o un mapa de cambios.")
    if len(entries) > MAX_BLUEPRINTS:
        raise InvalidBlueprintPlan(f"blueprints supera el máximo de {MAX_BLUEPRINTS} elementos.")
    catalog = _catalog()
    ids = catalog["blueprint_ids"]
    assert isinstance(ids, frozenset)
    result: dict[str, str] = {}
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {"id", "status"}:
            raise InvalidBlueprintPlan("blueprints contiene un cambio con forma inválida.")
        blueprint_id = entry["id"]
        status = entry["status"]
        if not isinstance(blueprint_id, str) or blueprint_id not in ids:
            raise InvalidBlueprintPlan(
                f"{blueprint_id!r} no pertenece al catálogo de planos ni a los decorados observados."
            )
        if status not in BLUEPRINT_STATUSES:
            raise InvalidBlueprintPlan(f"{blueprint_id} declara un estado desconocido: {status!r}.")
        if blueprint_id in result:
            raise InvalidBlueprintPlan(f"blueprints repite el identificador {blueprint_id}.")
        result[blueprint_id] = status
    if not result:
        raise InvalidBlueprintPlan("blueprints no contiene ningún cambio.")
    return dict(sorted(result.items()))


@dataclass
class BlueprintChange:
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
class BlueprintEdit:
    plan: dict[str, str]
    changes: list[BlueprintChange]
    changed: bool
    original: bytes
    candidate: bytes
    original_sha256: str
    candidate_sha256: str
    binary: BinaryDiff
    serialzed_version: int
    changed_fields: tuple[str, ...] = field(default_factory=tuple)

    @property
    def original_size(self) -> int:
        return len(self.original)

    @property
    def candidate_size(self) -> int:
        return len(self.candidate)

    def summary(self) -> dict[str, object]:
        return {
            "field": "blueprints",
            "plan": self.plan,
            "changes": [change.summary() for change in self.changes],
            "changed": self.changed,
            "original_size": self.original_size,
            "candidate_size": self.candidate_size,
            "original_sha256": self.original_sha256,
            "candidate_sha256": self.candidate_sha256,
            "byte_diff": self.binary.as_dict(),
            "changed_fields": list(self.changed_fields),
            "serialzed_version": self.serialzed_version,
        }


def _blueprint_map(root: Mapping[str, Any]) -> dict[str, Any]:
    item_data = root.get("itemData")
    if not isinstance(item_data, dict) or not isinstance(item_data.get("blueprints"), dict):
        raise BlueprintFieldMissing("No existe itemData.blueprints como mapa de estados.")
    return item_data["blueprints"]


def blueprints_snapshot(payload: Mapping[str, Any]) -> dict[str, object]:
    catalog = _catalog()
    item_data = payload.get("itemData")
    target = item_data.get("blueprints") if isinstance(item_data, dict) else None
    available = isinstance(target, dict)
    target = target if isinstance(target, dict) else {}
    rows_by_id = catalog["blueprints"]
    assert isinstance(rows_by_id, dict)
    encoding = blueprint_encoding(target)
    resolved_keys: set[str] = set()
    entries: list[dict[str, object]] = []
    for blueprint_id in catalog["ordered_blueprints"]:  # type: ignore[union-attr]
        row = rows_by_id[blueprint_id]
        key = resolve_blueprint_key(blueprint_id, target)
        alias = _alias(blueprint_id)
        alias_key = alias if alias != blueprint_id and alias in target and alias != key else None
        value = target.get(key) if key is not None else None
        status = decode_blueprint_status(value)
        present = key is not None
        if key is not None:
            resolved_keys.add(key)
        if alias_key is not None:
            resolved_keys.add(alias_key)
        name = row.get("name") if isinstance(row.get("name"), dict) else {}
        if not available:
            reason = "itemData.blueprints no está disponible como mapa."
        elif present and status is None:
            reason = f"El valor {value!r} no es un estado conocido; no se sobrescribe."
        elif status == "Researched":
            reason = "Ya está investigado; no se permite retroceder a Got."
        elif status == "Got":
            reason = "Obtenido sin investigar; se puede investigar."
        elif alias_key is not None:
            reason = f"Existe el alias heredado {alias_key}; se reutiliza esa clave."
        else:
            reason = "No obtenido; se puede crear el registro compatible."
        entries.append(
            {
                "id": blueprint_id,
                "key": key,
                "alias_key": alias_key,
                "name": name,
                "subcategory": row.get("subcategory"),
                "blueprint_type": row.get("blueprint_type"),
                "target": row.get("target"),
                "research_materials": row.get("research_materials"),
                "observed_extra": bool(row.get("observed_extra")),
                "status": status,
                "raw_value": value if present else None,
                "value_type": type(value).__name__ if present else None,
                "present": present,
                "creatable": available and status is None and key is None,
                "editable": available and status is not None,
                "bulk_eligible": available and (status == "Got" or (status is None and key is None)),
                "reason": reason,
                "path": f"{BLUEPRINTS_PATH}.{key}" if key is not None else None,
            }
        )
    unmatched = sorted(key for key in target if key not in resolved_keys)
    return {
        "available": available,
        "path": BLUEPRINTS_PATH,
        "statuses": sorted(BLUEPRINT_STATUSES),
        "encoding": encoding,
        "entries": entries,
        "unmatched": unmatched,
        "experimental": True,
        "evidence_level": "E2",
        "note": (
            "Los planos ausentes del catálogo se pueden crear como Got o Researched. "
            "Researched representa la investigación completada y Got el plano obtenido "
            "sin investigar; nunca se rebaja un plano investigado."
        ),
        "limitation": BLUEPRINT_LIMITATION,
    }


def read_blueprints(source: bytes) -> dict[str, object]:
    root, _, _ = _validated_document(source)
    return blueprints_snapshot(root)


_MISSING = object()


def prepare_blueprint_edit(source: bytes, plan: object) -> BlueprintEdit:
    root, version, source = _validated_document(source)
    normalized = normalize_blueprint_plan(plan)
    candidate = deepcopy(root)
    target = _blueprint_map(candidate)
    encoding = blueprint_encoding(target)
    changes: list[BlueprintChange] = []
    originals: list[tuple[str, object]] = []
    resolved: dict[str, str] = {}
    used_keys: set[str] = set()

    for blueprint_id, requested in normalized.items():
        key = preferred_blueprint_key(blueprint_id, target)
        if key in used_keys:
            raise BlueprintFieldIncompatible(
                f"Dos identificadores del catálogo resuelven a la misma clave {key}."
            )
        used_keys.add(key)
        resolved[blueprint_id] = key
        before = target.get(key, _MISSING)
        if before is not _MISSING:
            before_status = decode_blueprint_status(before)
            if before_status is None:
                raise BlueprintFieldIncompatible(
                    f"{BLUEPRINTS_PATH}.{key} declara un estado desconocido y no se sobrescribe."
                )
            if before_status == "Researched" and requested == "Got":
                raise BlueprintFieldIncompatible(
                    f"{BLUEPRINTS_PATH}.{key} ya está investigado; no se permite retroceder a Got."
                )
            if before_status == requested:
                continue
        originals.append((key, before))
        target[key] = encode_blueprint_status(requested, encoding)
        changes.append(
            BlueprintChange(
                f"{BLUEPRINTS_PATH}.{key}",
                None if before is _MISSING else before,
                target[key],
                created=before is _MISSING,
            )
        )

    changed_fields = tuple(change.path for change in changes)
    if not changes:
        digest = sha256(source).hexdigest()
        return BlueprintEdit(
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
        raise BlueprintVerificationError(f"No se pudo serializar el candidato: {exc}") from exc
    if len(candidate_source) > MAX_INPUT_BYTES:
        raise BlueprintVerificationError("El guardado candidato supera el tamaño permitido.")

    try:
        reconstruct_cloud_save(candidate_source)
        encoding_name, document = unpack_cloud_save(candidate_source)
        if encoding_name != "json":
            raise BlueprintVerificationError("El candidato no conserva el formato JSON.")
        reopened = parse_json(document)
    except (AggregateFormatError, ValueError) as exc:
        raise BlueprintVerificationError(f"El candidato no se puede volver a abrir: {exc}") from exc
    if not isinstance(reopened, dict):
        raise BlueprintVerificationError("El candidato no conserva el objeto raíz.")
    if serialize_aggregate(deepcopy(reopened)) != candidate_source:
        raise BlueprintVerificationError("El candidato no es estable al reserializarlo.")

    reopened_map = _blueprint_map(reopened)
    for blueprint_id, requested in normalized.items():
        key = resolved[blueprint_id]
        expected = encode_blueprint_status(requested, encoding)
        if reopened_map.get(key) != expected:
            raise BlueprintVerificationError(f"No se conservó {BLUEPRINTS_PATH}.{key}.")

    for key, before in originals:
        if before is _MISSING:
            reopened_map.pop(key, None)
        else:
            reopened_map[key] = before
    if serialize_aggregate(reopened) != source:
        raise BlueprintVerificationError(
            "La reversión del plan no reproduce el guardado original; hay cambios colaterales."
        )

    binary = binary_diff(source, candidate_source)
    if binary.first_difference is None:
        raise BlueprintVerificationError("El plan no produjo una diferencia binaria verificable.")
    return BlueprintEdit(
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


def require_blueprint_write_compatibility(
    source: bytes, plan: object, candidate: bytes
) -> None:
    try:
        expected = prepare_blueprint_edit(source, plan).candidate
    except BlueprintEditError as exc:
        if exc.code == BlueprintVerificationError.code:
            raise
        raise BlueprintEditError(f"El borrador de planos ya no es compatible: {exc}") from exc
    if expected != candidate:
        raise OutdatedBlueprintDraft("El borrador de planos no coincide con el guardado actual.")
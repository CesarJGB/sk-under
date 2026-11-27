"""Edición determinista del saldo de gemas en un agregado de nube.

El agregado real de 8.8.0 se serializa con claves ordenadas, separadores
``", "``/``": "``, sin indentación y sin escapes ASCII. Este módulo exige esa
misma forma canónica antes de editar: si la serialización canónica del original
no reproduce sus bytes, se rechaza la operación.

Después de aplicar el plan se reconstruye el agregado completo. Restaurar las
rutas del plan debe reproducir exactamente los bytes de entrada.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from hashlib import sha256

from ..cloud_save import (
    MAX_INPUT_BYTES,
    AggregateFormatError,
    CloudSaveError,
    CopyLimitError,
    JsonObject,
    reconstruct_cloud_save,
    unpack_cloud_save,
)
from ..parsers.json_document import parse_json
from .aggregate_cache import serialize_canonical, validated_document
from .lab import BinaryDiff, binary_diff, clone_json
from .resource_consistency import (
    RESOURCES,
    ConsistencyUnknown,
    IncompatibleResource,
    ResourceDiscrepancy,
    plan_gems_transition,
)

_GEMS = RESOURCES["gems"]
GEMS_FIELD_ID = _GEMS.id
GEMS_CATEGORY = _GEMS.name
MIN_GEMS, MAX_GEMS = _GEMS.integer_range


class GemsEditError(CloudSaveError):
    code = "gems_edit"


class InvalidGemsValue(GemsEditError):
    code = "invalid_gems_value"


class GemsFieldMissing(GemsEditError):
    code = "gems_field_missing"


class UnsupportedAggregateSerialization(GemsEditError):
    code = "unsupported_serialization"


class GemsVerificationError(GemsEditError):
    code = "gems_verification_failed"


class UnsupportedGemsStructure(GemsEditError):
    code = "unsupported_gems_structure"


class UnknownGemsDependencies(GemsEditError):
    code = "unknown_gems_dependencies"


class InconsistentGemsBalance(GemsEditError):
    code = "inconsistent_gems_balance"


class OutdatedGemsDraft(GemsEditError):
    code = "outdated_gems_draft"


@dataclass(frozen=True)
class GemsSnapshot:
    """Valor actual y huella del agregado, sin conservar su contenido."""

    gems: int
    size: int
    sha256: str = field(repr=False)
    serialzed_version: int

    def summary(self) -> dict[str, object]:
        return {
            "gems": self.gems,
            "size": self.size,
            "sha256": self.sha256,
            "serialzed_version": self.serialzed_version,
        }


@dataclass(frozen=True)
class GemsEdit:
    """Resultado determinista de preparar un cambio de gemas."""

    original_gems: int
    new_gems: int
    changed: bool
    original: bytes = field(repr=False)
    candidate: bytes = field(repr=False)
    original_sha256: str = field(repr=False)
    candidate_sha256: str = field(repr=False)
    binary: BinaryDiff = field(repr=False)
    serialzed_version: int
    changed_fields: tuple[str, ...] = ()

    @property
    def original_size(self) -> int:
        return len(self.original)

    @property
    def candidate_size(self) -> int:
        return len(self.candidate)

    def summary(self) -> dict[str, object]:
        return {
            "original_gems": self.original_gems,
            "new_gems": self.new_gems,
            "changed": self.changed,
            "original_size": len(self.original),
            "candidate_size": len(self.candidate),
            "original_sha256": self.original_sha256,
            "candidate_sha256": self.candidate_sha256,
            "serialzed_version": self.serialzed_version,
            "binary": self.binary.as_dict(),
            "changed_fields": list(self.changed_fields),
        }


def validate_gems_value(value: object) -> int:
    """Acepta solo un entero JSON, nunca booleanos, texto o flotantes."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise InvalidGemsValue("Las gemas deben ser un número entero.")
    if not MIN_GEMS <= value <= MAX_GEMS:
        raise InvalidGemsValue(f"Las gemas deben estar entre {MIN_GEMS} y {MAX_GEMS}.")
    return value


def serialize_aggregate(document: JsonObject) -> bytes:
    """Serializa con la forma canónica observada en la copia real de 8.8.0."""
    try:
        return serialize_canonical(document)
    except AggregateFormatError:
        raise GemsEditError("El agregado no se puede serializar como JSON.") from None


def _validated_document(source: bytes) -> tuple[JsonObject, int]:
    return validated_document(
        source,
        unsupported_error=UnsupportedAggregateSerialization,
        unsupported_message=(
            "La copia no usa la serialización canónica observada; no se puede garantizar "
            "que el cambio sea granular."
        ),
    )


def _game_data(root: JsonObject) -> JsonObject:
    game_data = root.get("gameData")
    if not isinstance(game_data, dict):
        raise AggregateFormatError("Se requiere gameData como objeto JSON.")
    return game_data


def _gems_plan(root: JsonObject, target: int) -> dict[str, int]:
    try:
        return plan_gems_transition(root, target)
    except IncompatibleResource as exc:
        raise UnsupportedGemsStructure(str(exc)) from None
    except ConsistencyUnknown as exc:
        raise UnknownGemsDependencies(str(exc)) from None
    except ResourceDiscrepancy as exc:
        raise InconsistentGemsBalance(str(exc)) from None


def require_gems_write_compatibility(source: bytes, target: int, candidate: bytes) -> None:
    if prepare_gems_edit(source, target).candidate != candidate:
        raise OutdatedGemsDraft("El respaldo usa un borrador antiguo. Prepara de nuevo la edición antes de subirla.")


def read_gems(source: bytes) -> GemsSnapshot:
    """Lee ``gameData.gems`` y valida la estructura sin modificarla."""
    root, version = _validated_document(source)
    game_data = _game_data(root)
    if GEMS_FIELD_ID not in game_data:
        raise GemsFieldMissing("La copia no contiene gameData.gems.")
    gems = validate_gems_value(game_data[GEMS_FIELD_ID])
    return GemsSnapshot(
        gems=gems,
        size=len(source),
        sha256=sha256(source).hexdigest(),
        serialzed_version=version,
    )


def prepare_gems_edit(source: bytes, new_gems: object) -> GemsEdit:
    """Prepara el candidato con la política actual de escritura."""
    return _prepare(source, new_gems, legacy=False)


def replay_legacy_gems_edit(source: bytes, new_gems: object) -> GemsEdit:
    """Reproduce el candidato histórico para verificar y recuperar respaldos."""
    return _prepare(source, new_gems, legacy=True)


def _prepare(source: bytes, new_gems: object, *, legacy: bool) -> GemsEdit:
    value = validate_gems_value(new_gems)
    root, version = _validated_document(source)
    game_data = _game_data(root)
    if GEMS_FIELD_ID not in game_data:
        raise GemsFieldMissing("La copia no contiene gameData.gems.")
    original_gems = validate_gems_value(game_data[GEMS_FIELD_ID])
    fields = {GEMS_FIELD_ID: value} if legacy and value != original_gems else {}
    if not legacy:
        fields = _gems_plan(root, value)
    original_sha = sha256(source).hexdigest()

    if not fields:
        return GemsEdit(
            original_gems=original_gems,
            new_gems=value,
            changed=False,
            original=source,
            candidate=source,
            original_sha256=original_sha,
            candidate_sha256=original_sha,
            binary=binary_diff(source, source),
            serialzed_version=version,
        )

    modified = clone_json(root)
    _game_data(modified).update(fields)

    candidate = serialize_aggregate(modified)
    if len(candidate) > MAX_INPUT_BYTES:
        raise CopyLimitError("La copia editada supera el límite permitido.")
    reconstruct_cloud_save(candidate)
    try:
        reopened = parse_json(unpack_cloud_save(candidate)[1])
    except (ValueError, RecursionError):
        raise GemsVerificationError("La copia editada no se puede volver a abrir.") from None
    if reopened != modified:
        raise GemsVerificationError("La copia reabierta no coincide con la copia editada.")
    if serialize_aggregate(reopened) != candidate:
        raise GemsVerificationError("La copia editada no es estable al serializarla de nuevo.")
    if read_gems(candidate).gems != value:
        raise GemsVerificationError("La copia editada no contiene el valor solicitado.")
    _game_data(reopened).update({key: game_data[key] for key in fields})
    if serialize_aggregate(reopened) != source:
        raise GemsVerificationError("La edición afectó a datos fuera del plan de gemas.")
    binary = binary_diff(source, candidate)
    if binary.first_difference is None:
        raise GemsVerificationError("La copia editada es idéntica al original.")

    return GemsEdit(
        original_gems=original_gems,
        new_gems=value,
        changed=True,
        original=source,
        candidate=candidate,
        original_sha256=original_sha,
        candidate_sha256=sha256(candidate).hexdigest(),
        binary=binary,
        serialzed_version=version,
        changed_fields=tuple(f"gameData.{key}" for key in fields),
    )

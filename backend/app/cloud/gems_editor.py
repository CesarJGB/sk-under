"""Edición determinista de ``gameData.gems`` en un agregado de nube.

El agregado real de 8.8.0 se serializa con claves ordenadas, separadores
``", "``/``": "``, sin indentación y sin escapes ASCII. Este módulo exige esa
misma forma canónica antes de editar: si la serialización canónica del original
no reproduce sus bytes, no se puede garantizar que el cambio afecte solo a
``gems`` y la operación se rechaza.

La edición no toca ninguna otra ruta. Después de serializar se vuelve a
reconstruir el agregado completo, se compara el árbol y se comprueba que al
restaurar el valor original se recuperan exactamente los bytes de entrada.
"""

from __future__ import annotations

import json
from copy import deepcopy
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
from .lab import BinaryDiff, binary_diff

GEMS_FIELD_ID = "gems"
GEMS_CATEGORY = "Gemas"
MIN_GEMS = 0
# Cota conservadora de entero con signo de 32 bits. No se verificó que el
# servicio acepte valores fuera de este rango; el editor no los propone.
MAX_GEMS = 2_147_483_647


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
        return json.dumps(
            document,
            ensure_ascii=False,
            sort_keys=True,
            allow_nan=False,
            separators=(", ", ": "),
        ).encode("utf-8")
    except (TypeError, ValueError):
        raise GemsEditError("El agregado no se puede serializar como JSON.") from None


def _validated_document(source: bytes) -> tuple[JsonObject, int]:
    if not source:
        raise CopyLimitError("La copia está vacía.")
    if len(source) > MAX_INPUT_BYTES:
        raise CopyLimitError("La copia supera el límite permitido.")
    reconstruct_cloud_save(source)
    encoding, document = unpack_cloud_save(source)
    if encoding != "json":
        raise UnsupportedAggregateSerialization(
            "El editor de gemas solo admite el agregado JSON que usa el sobre de nube."
        )
    try:
        root = parse_json(document)
    except (ValueError, RecursionError):
        raise AggregateFormatError("El documento no contiene JSON UTF-8 válido.") from None
    if not isinstance(root, dict):
        raise AggregateFormatError("Se esperaba un objeto JSON en la raíz.")
    if serialize_aggregate(root) != source:
        raise UnsupportedAggregateSerialization(
            "La copia no usa la serialización canónica observada; no se puede garantizar "
            "que solo cambie gameData.gems."
        )
    version = root.get("serialzedVersion")
    if isinstance(version, bool) or not isinstance(version, int):
        raise AggregateFormatError("Se requiere serialzedVersion como entero.")
    return root, version


def _game_data(root: JsonObject) -> JsonObject:
    game_data = root.get("gameData")
    if not isinstance(game_data, dict):
        raise AggregateFormatError("Se requiere gameData como objeto JSON.")
    return game_data


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


def _assert_only_gems_changed(original: JsonObject, modified: JsonObject, original_gems: int) -> None:
    """Demuestra que el único valor distinto es ``gameData.gems``."""
    if original == modified:
        raise GemsVerificationError("La copia editada no contiene ningún cambio.")
    restored = deepcopy(modified)
    _game_data(restored)[GEMS_FIELD_ID] = original_gems
    if restored != original:
        raise GemsVerificationError("La edición afectó a datos distintos de gameData.gems.")
    if serialize_aggregate(restored) != serialize_aggregate(original):
        raise GemsVerificationError("La serialización no es determinista para el original.")


def prepare_gems_edit(source: bytes, new_gems: object) -> GemsEdit:
    """Prepara una copia con solo ``gameData.gems`` modificado.

    Un valor igual al actual produce una operación sin cambios y conserva los
    bytes originales exactos.
    """
    value = validate_gems_value(new_gems)
    root, version = _validated_document(source)
    game_data = _game_data(root)
    if GEMS_FIELD_ID not in game_data:
        raise GemsFieldMissing("La copia no contiene gameData.gems.")
    original_gems = validate_gems_value(game_data[GEMS_FIELD_ID])
    original_sha = sha256(source).hexdigest()

    if value == original_gems:
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

    modified = deepcopy(root)
    _game_data(modified)[GEMS_FIELD_ID] = value
    _assert_only_gems_changed(root, modified, original_gems)

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
    if binary_diff(source, candidate).first_difference is None:
        raise GemsVerificationError("La copia editada es idéntica al original.")

    return GemsEdit(
        original_gems=original_gems,
        new_gems=value,
        changed=True,
        original=source,
        candidate=candidate,
        original_sha256=original_sha,
        candidate_sha256=sha256(candidate).hexdigest(),
        binary=binary_diff(source, candidate),
        serialzed_version=version,
    )

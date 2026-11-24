"""Edición experimental y determinista de ``gameData.fishChip``.

La Fase 6.14 habilita una prueba manual autorizada sobre el saldo candidato de
fichas de pesca. El campo sigue siendo E2: no se ha observado una transacción
legítima con saldo positivo, ni la autoridad del servidor, ni una recuperación
tras reiniciar. Este módulo solo modifica esa ruta y conserva intactos los
demás campos del agregado.

Se reutilizan las garantías del editor de gemas: serialización canónica,
reconstrucción del sobre de nube y comparación inversa del documento. No se
tocan ``material_fish``, los historiales ``fishChipStore*`` ni
``cumulativeFishCount``.
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
from .gems_editor import serialize_aggregate
from .lab import BinaryDiff, binary_diff

FISH_CHIP_FIELD_ID = "fishChip"
FISH_CHIP_PATH = "gameData.fishChip"
FISH_CHIP_RECORD_FIELD = "fish_chip"
MIN_FISH_CHIP = 0
MAX_FISH_CHIP = 2_147_483_647


class FishChipEditError(CloudSaveError):
    code = "fish_chip_edit"


class InvalidFishChipValue(FishChipEditError):
    code = "invalid_fish_chip_value"


class FishChipFieldMissing(FishChipEditError):
    code = "fish_chip_field_missing"


class UnsupportedFishChipSerialization(FishChipEditError):
    code = "unsupported_serialization"


class FishChipVerificationError(FishChipEditError):
    code = "fish_chip_verification_failed"


class OutdatedFishChipDraft(FishChipEditError):
    code = "outdated_fish_chip_draft"


@dataclass(frozen=True)
class FishChipSnapshot:
    """Saldo actual de fichas y huella del agregado, sin conservar su contenido."""

    fish_chip: int
    size: int
    sha256: str = field(repr=False)
    serialzed_version: int

    def summary(self) -> dict[str, object]:
        return {
            "fish_chip": self.fish_chip,
            "size": self.size,
            "sha256": self.sha256,
            "serialzed_version": self.serialzed_version,
        }


@dataclass(frozen=True)
class FishChipEdit:
    """Resultado determinista de preparar un cambio de fichas de pesca."""

    original_fish_chip: int
    new_fish_chip: int
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
            "field": FISH_CHIP_PATH,
            "original_fish_chip": self.original_fish_chip,
            "new_fish_chip": self.new_fish_chip,
            "changed": self.changed,
            "original_size": len(self.original),
            "candidate_size": len(self.candidate),
            "original_sha256": self.original_sha256,
            "candidate_sha256": self.candidate_sha256,
            "serialzed_version": self.serialzed_version,
            "binary": self.binary.as_dict(),
            "changed_fields": list(self.changed_fields),
        }


def validate_fish_chip_value(value: object) -> int:
    """Acepta solo un entero JSON no negativo, nunca booleanos, texto o flotantes."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise InvalidFishChipValue("Las fichas de pesca deben ser un número entero.")
    if not MIN_FISH_CHIP <= value <= MAX_FISH_CHIP:
        raise InvalidFishChipValue(
            f"Las fichas de pesca deben estar entre {MIN_FISH_CHIP} y {MAX_FISH_CHIP}."
        )
    return value


def _validated_document(source: bytes) -> tuple[JsonObject, int]:
    if not source:
        raise CopyLimitError("La copia está vacía.")
    if len(source) > MAX_INPUT_BYTES:
        raise CopyLimitError("La copia supera el límite permitido.")
    reconstruct_cloud_save(source)
    encoding, document = unpack_cloud_save(source)
    if encoding != "json":
        raise UnsupportedFishChipSerialization(
            "El editor de fichas de pesca solo admite el agregado JSON que usa el sobre de nube."
        )
    try:
        root = parse_json(document)
    except (ValueError, RecursionError):
        raise AggregateFormatError("El documento no contiene JSON UTF-8 válido.") from None
    if not isinstance(root, dict):
        raise AggregateFormatError("Se esperaba un objeto JSON en la raíz.")
    if serialize_aggregate(root) != source:
        raise UnsupportedFishChipSerialization(
            "La copia no usa la serialización canónica observada; no se puede garantizar "
            "que el cambio sea granular."
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


def read_fish_chip(source: bytes) -> FishChipSnapshot:
    """Lee ``gameData.fishChip`` y valida la estructura sin modificarla."""
    root, version = _validated_document(source)
    game_data = _game_data(root)
    if FISH_CHIP_FIELD_ID not in game_data:
        raise FishChipFieldMissing("La copia no contiene gameData.fishChip.")
    value = validate_fish_chip_value(game_data[FISH_CHIP_FIELD_ID])
    return FishChipSnapshot(
        fish_chip=value,
        size=len(source),
        sha256=sha256(source).hexdigest(),
        serialzed_version=version,
    )


def prepare_fish_chip_edit(source: bytes, new_fish_chip: object) -> FishChipEdit:
    """Prepara el candidato cambiando únicamente ``gameData.fishChip``."""
    value = validate_fish_chip_value(new_fish_chip)
    root, version = _validated_document(source)
    game_data = _game_data(root)
    if FISH_CHIP_FIELD_ID not in game_data:
        raise FishChipFieldMissing("La copia no contiene gameData.fishChip.")
    original_value = validate_fish_chip_value(game_data[FISH_CHIP_FIELD_ID])
    original_sha = sha256(source).hexdigest()

    if value == original_value:
        return FishChipEdit(
            original_fish_chip=original_value,
            new_fish_chip=value,
            changed=False,
            original=source,
            candidate=source,
            original_sha256=original_sha,
            candidate_sha256=original_sha,
            binary=binary_diff(source, source),
            serialzed_version=version,
        )

    modified = deepcopy(root)
    _game_data(modified)[FISH_CHIP_FIELD_ID] = value

    candidate = serialize_aggregate(modified)
    if len(candidate) > MAX_INPUT_BYTES:
        raise CopyLimitError("La copia editada supera el límite permitido.")
    reconstruct_cloud_save(candidate)
    try:
        reopened = parse_json(unpack_cloud_save(candidate)[1])
    except (ValueError, RecursionError):
        raise FishChipVerificationError("La copia editada no se puede volver a abrir.") from None
    if reopened != modified:
        raise FishChipVerificationError("La copia reabierta no coincide con la copia editada.")
    if serialize_aggregate(reopened) != candidate:
        raise FishChipVerificationError("La copia editada no es estable al serializarla de nuevo.")
    if read_fish_chip(candidate).fish_chip != value:
        raise FishChipVerificationError("La copia editada no contiene el valor solicitado.")
    # Restaurar el único valor del plan debe reproducir el original byte a byte.
    _game_data(reopened)[FISH_CHIP_FIELD_ID] = original_value
    if serialize_aggregate(reopened) != source:
        raise FishChipVerificationError(
            "La edición afectó a datos fuera del saldo de fichas de pesca."
        )
    binary = binary_diff(source, candidate)
    if binary.first_difference is None:
        raise FishChipVerificationError("La copia editada es idéntica al original.")

    return FishChipEdit(
        original_fish_chip=original_value,
        new_fish_chip=value,
        changed=True,
        original=source,
        candidate=candidate,
        original_sha256=original_sha,
        candidate_sha256=sha256(candidate).hexdigest(),
        binary=binary,
        serialzed_version=version,
        changed_fields=(FISH_CHIP_PATH,),
    )


def require_fish_chip_write_compatibility(source: bytes, target: int, candidate: bytes) -> None:
    if prepare_fish_chip_edit(source, target).candidate != candidate:
        raise OutdatedFishChipDraft(
            "El respaldo usa un borrador antiguo. Prepara de nuevo la edición antes de subirla."
        )
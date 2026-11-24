"""Edición experimental del progreso acumulado de la tienda de fichas de pesca.

La Fase 6.20 identificó, en el cliente 8.8.0, que la barra de recompensas de la
tienda lee ``ItemData.cumulativeFishCount`` a través de
``FishChipPurchaseController``. Es un contador histórico independiente del
saldo actual (``gameData.fishChip``) y del material espejo
(``itemData.materials.material_fish``).

La evidencia es E2: estructura y uso en código observados, sin una prueba
manual en Android que confirme que la recompensa se refresca al restaurar la
nube. Este módulo solo cambia ``itemData.cumulativeFishCount`` y conserva el
resto del agregado, incluidos el saldo, el material y los historiales.
"""

from __future__ import annotations

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

PROGRESS_FIELD_ID = "cumulativeFishCount"
PROGRESS_PATH = "itemData.cumulativeFishCount"
PROGRESS_RECORD_FIELD = "fish_progress"
MIN_FISH_PROGRESS = 0
MAX_FISH_PROGRESS = 2_147_483_647


class FishProgressEditError(CloudSaveError):
    code = "fish_progress_edit"


class InvalidFishProgressValue(FishProgressEditError):
    code = "invalid_fish_progress_value"


class FishProgressFieldMissing(FishProgressEditError):
    code = "fish_progress_field_missing"


class UnsupportedFishProgressSerialization(FishProgressEditError):
    code = "unsupported_fish_progress_serialization"


class FishProgressVerificationError(FishProgressEditError):
    code = "fish_progress_verification_failed"


class OutdatedFishProgressDraft(FishProgressEditError):
    code = "outdated_fish_progress_draft"


@dataclass(frozen=True)
class FishProgressSnapshot:
    """Progreso acumulado actual y huella del agregado."""

    cumulative_fish_count: int
    size: int
    sha256: str = field(repr=False)
    serialzed_version: int

    def summary(self) -> dict[str, object]:
        return {
            "cumulative_fish_count": self.cumulative_fish_count,
            "cumulative_fish_count_path": PROGRESS_PATH,
            "size": self.size,
            "sha256": self.sha256,
            "serialzed_version": self.serialzed_version,
        }


@dataclass(frozen=True)
class FishProgressEdit:
    """Resultado determinista de preparar un cambio del progreso acumulado."""

    original_cumulative_fish_count: int
    new_cumulative_fish_count: int
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
            "field": PROGRESS_PATH,
            "original_cumulative_fish_count": self.original_cumulative_fish_count,
            "new_cumulative_fish_count": self.new_cumulative_fish_count,
            "changed": self.changed,
            "original_size": len(self.original),
            "candidate_size": len(self.candidate),
            "original_sha256": self.original_sha256,
            "candidate_sha256": self.candidate_sha256,
            "serialzed_version": self.serialzed_version,
            "binary": self.binary.as_dict(),
            "changed_fields": list(self.changed_fields),
        }


def validate_fish_progress_value(value: object) -> int:
    """Acepta solo un entero JSON no negativo, nunca booleanos, texto o flotantes."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise InvalidFishProgressValue(
            "El progreso acumulado de fichas debe ser un número entero."
        )
    if not MIN_FISH_PROGRESS <= value <= MAX_FISH_PROGRESS:
        raise InvalidFishProgressValue(
            "El progreso acumulado de fichas debe estar entre "
            f"{MIN_FISH_PROGRESS} y {MAX_FISH_PROGRESS}."
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
        raise UnsupportedFishProgressSerialization(
            "El editor de progreso de fichas solo admite el agregado JSON que usa el sobre de nube."
        )
    try:
        root = parse_json(document)
    except (ValueError, RecursionError):
        raise AggregateFormatError("El documento no contiene JSON UTF-8 válido.") from None
    if not isinstance(root, dict):
        raise AggregateFormatError("Se esperaba un objeto JSON en la raíz.")
    if serialize_aggregate(root) != source:
        raise UnsupportedFishProgressSerialization(
            "La copia no usa la serialización canónica observada; no se puede garantizar "
            "que el cambio sea granular."
        )
    version = root.get("serialzedVersion")
    if isinstance(version, bool) or not isinstance(version, int):
        raise AggregateFormatError("Se requiere serialzedVersion como entero.")
    return root, version


def _item_data(root: JsonObject) -> JsonObject:
    item_data = root.get("itemData")
    if not isinstance(item_data, dict):
        raise FishProgressFieldMissing(
            "La copia no contiene itemData; no se puede editar el progreso acumulado."
        )
    return item_data


def _read_value(item_data: JsonObject) -> int:
    if PROGRESS_FIELD_ID not in item_data:
        raise FishProgressFieldMissing(
            "La copia no contiene itemData.cumulativeFishCount."
        )
    return validate_fish_progress_value(item_data[PROGRESS_FIELD_ID])


def read_fish_progress(source: bytes) -> FishProgressSnapshot:
    """Lee el contador acumulado sin modificar la copia."""
    root, version = _validated_document(source)
    item_data = _item_data(root)
    value = _read_value(item_data)
    return FishProgressSnapshot(
        cumulative_fish_count=value,
        size=len(source),
        sha256=sha256(source).hexdigest(),
        serialzed_version=version,
    )


def prepare_fish_progress_edit(source: bytes, new_value: object) -> FishProgressEdit:
    """Prepara el candidato cambiando únicamente ``itemData.cumulativeFishCount``."""
    value = validate_fish_progress_value(new_value)
    root, version = _validated_document(source)
    item_data = _item_data(root)
    original_value = _read_value(item_data)
    original_sha = sha256(source).hexdigest()

    if value == original_value:
        return FishProgressEdit(
            original_cumulative_fish_count=original_value,
            new_cumulative_fish_count=value,
            changed=False,
            original=source,
            candidate=source,
            original_sha256=original_sha,
            candidate_sha256=original_sha,
            binary=binary_diff(source, source),
            serialzed_version=version,
        )

    modified = deepcopy(root)
    _item_data(modified)[PROGRESS_FIELD_ID] = value

    candidate = serialize_aggregate(modified)
    if len(candidate) > MAX_INPUT_BYTES:
        raise CopyLimitError("La copia editada supera el límite permitido.")
    reconstruct_cloud_save(candidate)
    try:
        reopened = parse_json(unpack_cloud_save(candidate)[1])
    except (ValueError, RecursionError):
        raise FishProgressVerificationError("La copia editada no se puede volver a abrir.") from None
    if reopened != modified:
        raise FishProgressVerificationError("La copia reabierta no coincide con la copia editada.")
    if serialize_aggregate(reopened) != candidate:
        raise FishProgressVerificationError("La copia editada no es estable al serializarla de nuevo.")
    if read_fish_progress(candidate).cumulative_fish_count != value:
        raise FishProgressVerificationError(
            "La copia editada no contiene el progreso acumulado solicitado."
        )
    # Restaurar el único valor del plan debe reproducir el original.
    _item_data(reopened)[PROGRESS_FIELD_ID] = original_value
    if serialize_aggregate(reopened) != source:
        raise FishProgressVerificationError(
            "La edición afectó a datos fuera de itemData.cumulativeFishCount."
        )
    binary = binary_diff(source, candidate)
    if binary.first_difference is None:
        raise FishProgressVerificationError("La copia editada es idéntica al original.")

    return FishProgressEdit(
        original_cumulative_fish_count=original_value,
        new_cumulative_fish_count=value,
        changed=True,
        original=source,
        candidate=candidate,
        original_sha256=original_sha,
        candidate_sha256=sha256(candidate).hexdigest(),
        binary=binary,
        serialzed_version=version,
        changed_fields=(PROGRESS_PATH,),
    )


def require_fish_progress_write_compatibility(
    source: bytes, target: int, candidate: bytes
) -> None:
    if prepare_fish_progress_edit(source, target).candidate != candidate:
        raise OutdatedFishProgressDraft(
            "El respaldo usa un borrador antiguo. Prepara de nuevo la edición antes de subirla."
        )
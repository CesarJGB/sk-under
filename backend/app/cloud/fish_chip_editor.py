"""Edición experimental y determinista de las fichas de pesca.

La Fase 6.15 amplía la prueba manual autorizada de la Fase 6.14 para cambiar, en
la misma operación, ``gameData.fishChip`` y
``itemData.materials.material_fish``. El propietario indicó que un editor
anterior requería ambos valores; el segundo se trata como hipótesis respaldada
por esa observación, no como una validación dentro del cliente.

El campo sigue siendo E2: no se ha observado una transacción legítima con saldo
positivo, ni la autoridad del servidor, ni una recuperación tras reiniciar.
Este módulo solo modifica esas dos rutas y conserva intactos los demás campos,
incluidas las demás entradas del mapa ``materials``.

Se reutilizan las garantías del editor de gemas: serialización canónica,
reconstrucción del sobre de nube y comparación inversa del documento. No se
tocan los historiales ``fishChipStore*`` ni ``cumulativeFishCount``.
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
from .aggregate_cache import validated_document
from .lab import BinaryDiff, binary_diff

FISH_CHIP_FIELD_ID = "fishChip"
FISH_CHIP_PATH = "gameData.fishChip"
MATERIAL_FISH_FIELD_ID = "material_fish"
MATERIAL_FISH_PATH = "itemData.materials.material_fish"
FISH_EDIT_PATHS = (FISH_CHIP_PATH, MATERIAL_FISH_PATH)
FISH_CHIP_RECORD_FIELD = "fish_chip"
MIN_FISH_CHIP = 0
MAX_FISH_CHIP = 2_147_483_647


class FishChipEditError(CloudSaveError):
    code = "fish_chip_edit"


class InvalidFishChipValue(FishChipEditError):
    code = "invalid_fish_chip_value"


class InvalidFishMaterialValue(FishChipEditError):
    code = "invalid_fish_material_value"


class FishChipFieldMissing(FishChipEditError):
    code = "fish_chip_field_missing"


class FishMaterialFieldMissing(FishChipEditError):
    code = "fish_material_field_missing"


class UnsupportedFishChipSerialization(FishChipEditError):
    code = "unsupported_serialization"


class FishChipVerificationError(FishChipEditError):
    code = "fish_chip_verification_failed"


class OutdatedFishChipDraft(FishChipEditError):
    code = "outdated_fish_chip_draft"


@dataclass(frozen=True)
class FishChipSnapshot:
    """Saldos actuales y huella del agregado, sin conservar su contenido."""

    fish_chip: int
    material_fish: int | None
    size: int
    sha256: str = field(repr=False)
    serialzed_version: int

    def summary(self) -> dict[str, object]:
        return {
            "fish_chip": self.fish_chip,
            "fish_chip_path": FISH_CHIP_PATH,
            "material_fish": self.material_fish,
            "material_fish_path": MATERIAL_FISH_PATH,
            "size": self.size,
            "sha256": self.sha256,
            "serialzed_version": self.serialzed_version,
        }


@dataclass(frozen=True)
class FishChipEdit:
    """Resultado determinista de preparar un cambio conjunto de pesca."""

    original_fish_chip: int
    new_fish_chip: int
    original_material_fish: int | None
    new_material_fish: int
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
            "material_fish_path": MATERIAL_FISH_PATH,
            "original_fish_chip": self.original_fish_chip,
            "new_fish_chip": self.new_fish_chip,
            "original_material_fish": self.original_material_fish,
            "new_material_fish": self.new_material_fish,
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


def validate_material_fish_value(value: object) -> int:
    """El material de pesca existente debe ser un entero no negativo."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise InvalidFishMaterialValue(
            "itemData.materials.material_fish debe ser un número entero; no se sobrescribe "
            "una estructura de otro tipo."
        )
    if not MIN_FISH_CHIP <= value <= MAX_FISH_CHIP:
        raise InvalidFishMaterialValue(
            f"material_fish debe estar entre {MIN_FISH_CHIP} y {MAX_FISH_CHIP}."
        )
    return value


def _validated_document(source: bytes) -> tuple[JsonObject, int]:
    root, version = validated_document(
        source,
        unsupported_error=UnsupportedFishChipSerialization,
        unsupported_message=(
            "La copia no usa la serialización canónica observada; no se puede garantizar "
            "que el cambio sea granular."
        ),
    )
    return root, version
def _game_data(root: JsonObject) -> JsonObject:
    game_data = root.get("gameData")
    if not isinstance(game_data, dict):
        raise AggregateFormatError("Se requiere gameData como objeto JSON.")
    return game_data


def _optional_materials(root: JsonObject) -> JsonObject | None:
    item_data = root.get("itemData")
    if not isinstance(item_data, dict):
        return None
    materials = item_data.get("materials")
    return materials if isinstance(materials, dict) else None


def _materials_for_edit(root: JsonObject) -> JsonObject:
    item_data = root.get("itemData")
    if not isinstance(item_data, dict):
        raise FishMaterialFieldMissing(
            "La copia no contiene itemData; no se puede editar material_fish."
        )
    materials = item_data.get("materials")
    if not isinstance(materials, dict):
        raise FishMaterialFieldMissing(
            "La copia no contiene itemData.materials como objeto; no se puede editar material_fish."
        )
    return materials


def _read_material_fish(materials: JsonObject | None) -> int | None:
    if materials is None or MATERIAL_FISH_FIELD_ID not in materials:
        return None
    return validate_material_fish_value(materials[MATERIAL_FISH_FIELD_ID])


def read_fish_chip(source: bytes) -> FishChipSnapshot:
    """Lee ``gameData.fishChip`` y el material de pesca sin modificar la copia."""
    root, version = _validated_document(source)
    game_data = _game_data(root)
    if FISH_CHIP_FIELD_ID not in game_data:
        raise FishChipFieldMissing("La copia no contiene gameData.fishChip.")
    value = validate_fish_chip_value(game_data[FISH_CHIP_FIELD_ID])
    material_fish = _read_material_fish(_optional_materials(root))
    return FishChipSnapshot(
        fish_chip=value,
        material_fish=material_fish,
        size=len(source),
        sha256=sha256(source).hexdigest(),
        serialzed_version=version,
    )


def prepare_fish_chip_edit(source: bytes, new_fish_chip: object) -> FishChipEdit:
    """Prepara el candidato cambiando solo las dos rutas de pesca indicadas."""
    value = validate_fish_chip_value(new_fish_chip)
    root, version = _validated_document(source)
    game_data = _game_data(root)
    if FISH_CHIP_FIELD_ID not in game_data:
        raise FishChipFieldMissing("La copia no contiene gameData.fishChip.")
    materials = _materials_for_edit(root)
    original_value = validate_fish_chip_value(game_data[FISH_CHIP_FIELD_ID])
    original_material = _read_material_fish(materials)
    original_sha = sha256(source).hexdigest()

    if value == original_value and value == original_material:
        return FishChipEdit(
            original_fish_chip=original_value,
            new_fish_chip=value,
            original_material_fish=original_material,
            new_material_fish=value,
            changed=False,
            original=source,
            candidate=source,
            original_sha256=original_sha,
            candidate_sha256=original_sha,
            binary=binary_diff(source, source),
            serialzed_version=version,
        )

    changed_fields: list[str] = []
    if value != original_value:
        changed_fields.append(FISH_CHIP_PATH)
    if value != original_material:
        changed_fields.append(MATERIAL_FISH_PATH)

    modified = deepcopy(root)
    _game_data(modified)[FISH_CHIP_FIELD_ID] = value
    _materials_for_edit(modified)[MATERIAL_FISH_FIELD_ID] = value

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
    reopened_snapshot = read_fish_chip(candidate)
    if reopened_snapshot.fish_chip != value or reopened_snapshot.material_fish != value:
        raise FishChipVerificationError("La copia editada no contiene los dos valores solicitados.")
    # Restaurar exactamente los dos valores del plan debe reproducir el original.
    _game_data(reopened)[FISH_CHIP_FIELD_ID] = original_value
    reopened_materials = _materials_for_edit(reopened)
    if original_material is None:
        reopened_materials.pop(MATERIAL_FISH_FIELD_ID, None)
    else:
        reopened_materials[MATERIAL_FISH_FIELD_ID] = original_material
    if serialize_aggregate(reopened) != source:
        raise FishChipVerificationError(
            "La edición afectó a datos fuera de gameData.fishChip y "
            "itemData.materials.material_fish."
        )
    binary = binary_diff(source, candidate)
    if binary.first_difference is None:
        raise FishChipVerificationError("La copia editada es idéntica al original.")

    return FishChipEdit(
        original_fish_chip=original_value,
        new_fish_chip=value,
        original_material_fish=original_material,
        new_material_fish=value,
        changed=True,
        original=source,
        candidate=candidate,
        original_sha256=original_sha,
        candidate_sha256=sha256(candidate).hexdigest(),
        binary=binary,
        serialzed_version=version,
        changed_fields=tuple(changed_fields),
    )


def legacy_fish_chip_candidate_matches(source: bytes, target: int, candidate: bytes) -> bool:
    """Acepta un respaldo de la Fase 6.14 que solo cambiaba ``fishChip``.

    Sirve para listar, verificar y restaurar respaldos creados antes de que el
    editor incluyera ``material_fish``. El candidato debe cambiar únicamente
    ``gameData.fishChip`` y conservar el resto del agregado byte a byte.
    """
    value = validate_fish_chip_value(target)
    original_root, _ = _validated_document(source)
    candidate_root, _ = _validated_document(candidate)
    original_game = _game_data(original_root)
    candidate_game = _game_data(candidate_root)
    if FISH_CHIP_FIELD_ID not in original_game or FISH_CHIP_FIELD_ID not in candidate_game:
        return False
    if validate_fish_chip_value(candidate_game[FISH_CHIP_FIELD_ID]) != value:
        return False
    candidate_game[FISH_CHIP_FIELD_ID] = original_game[FISH_CHIP_FIELD_ID]
    return serialize_aggregate(candidate_root) == source


def require_fish_chip_write_compatibility(source: bytes, target: int, candidate: bytes) -> None:
    if prepare_fish_chip_edit(source, target).candidate != candidate:
        raise OutdatedFishChipDraft(
            "El respaldo usa un borrador antiguo. Prepara de nuevo la edición antes de subirla."
        )

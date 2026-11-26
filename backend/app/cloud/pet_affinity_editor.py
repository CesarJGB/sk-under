"""Editor experimental de afinidad de mascotas.

La afinidad vive en ``statisticData.event2Count`` con las claves
``pet_<numeric_id>_intimacy`` y ``pet_<numeric_id>_full_intimacy``. Los máximos
conocidos proceden de una muestra privada completa: 180 para los ids 30/31, 300
para el 34 y 240 para el resto de ids observados 0..55 excepto el 27. Los ids
27, 56 y 57 no tienen máximo demostrado y permanecen en solo lectura.

El escritor únicamente sube la intimidad. Si la mascota está desbloqueada en
``gameData.petUnlock`` pero nunca recibió alimento, crea la clave de intimidad
con valor 0 (ausencia = afinidad inicial). Al alcanzar el máximo conocido crea o
activa ``full_intimacy = 1``, que es el único indicador observado en todas las
mascotas maximizadas. No toca ``action_unlock``, el contador global ni ninguna
otra clave.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from hashlib import sha256
from typing import Any, Mapping

from ..catalogs.pets import load_pet_catalog
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

AFFINITY_PATH = "statisticData.event2Count"
AFFINITY_MIN = 0
MAX_VALUE = 2_147_483_647
MAX_PETS = 58

# Observado en la muestra completa autorizada: todos los ids 0..55 salvo el 27
# estaban presentes y mostraban 240, excepto 30/31 (180) y 34 (300).
AFFINITY_MAX_OVERRIDES = {30: 180, 31: 180, 34: 300}
AFFINITY_DEFAULT_MAX = 240
AFFINITY_OBSERVED_NUMERIC_IDS = frozenset(
    set(range(0, 27)) | set(range(28, 56))
)
AFFINITY_UNKNOWN_NUMERIC_IDS = frozenset({27, 56, 57})

AFFINITY_LIMITATION = (
    "Máximos derivados de una muestra completa: 180 para Cat4/Dog2, 300 para Cat5 "
    "y 240 para el resto de ids observados 0..55 salvo Serenade. La ausencia de "
    "claves de intimidad en una mascota desbloqueada se interpreta como 0: la cuenta "
    "nueva tiene Cat desbloqueada y ningún registro de afinidad. La configuración "
    "PetsLevelUpConfig/PetIntimacyConfig no se pudo deserializar; Serenade, "
    "EscapeMonkey y FishChipKing quedan en solo lectura. La eficacia del escritor "
    "todavía no se validó dentro del juego."
)

_MISSING = object()


def _unlocked_pets(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    game = payload.get("gameData")
    unlock = game.get("petUnlock") if isinstance(game, dict) else None
    return unlock if isinstance(unlock, dict) else {}


class PetAffinityEditError(CloudSaveError):
    code = "pet_affinity_edit"


class InvalidPetAffinityPlan(PetAffinityEditError):
    code = "pet_affinity_plan_invalid"


class UnsupportedPetAffinitySerialization(PetAffinityEditError):
    code = "pet_affinity_unsupported_serialization"


class PetAffinityFieldMissing(PetAffinityEditError):
    code = "pet_affinity_field_missing"


class PetAffinityFieldIncompatible(PetAffinityEditError):
    code = "pet_affinity_field_incompatible"


class PetAffinityCatalogMissing(PetAffinityEditError):
    code = "pet_affinity_catalog_missing"


class PetAffinityVerificationError(PetAffinityEditError):
    code = "pet_affinity_verification"


class OutdatedPetAffinityDraft(PetAffinityEditError):
    code = "pet_affinity_outdated"


def _validated_document(source: bytes) -> tuple[JsonObject, int, bytes]:
    try:
        raw = source.encode("utf-8") if isinstance(source, str) else bytes(source)
    except (UnicodeEncodeError, TypeError):
        raise UnsupportedPetAffinitySerialization("El guardado no es UTF-8 válido.") from None
    if not raw or len(raw) > MAX_INPUT_BYTES:
        raise UnsupportedPetAffinitySerialization("El tamaño del guardado no es válido.")
    try:
        reconstruct_cloud_save(raw)
        encoding, document = unpack_cloud_save(raw)
    except AggregateFormatError as exc:
        raise UnsupportedPetAffinitySerialization(str(exc)) from exc
    if encoding != "json":
        raise UnsupportedPetAffinitySerialization("El guardado no usa el formato JSON esperado.")
    try:
        root = parse_json(document)
    except (ValueError, RecursionError) as exc:
        raise UnsupportedPetAffinitySerialization("El guardado no contiene JSON válido.") from exc
    if not isinstance(root, dict):
        raise UnsupportedPetAffinitySerialization("El guardado no contiene un objeto raíz.")
    if not isinstance(root.get("serialzedVersion"), int):
        raise UnsupportedPetAffinitySerialization("El guardado no declara serialzedVersion.")
    try:
        serialized = serialize_aggregate(root)
    except (TypeError, ValueError) as exc:
        raise UnsupportedPetAffinitySerialization(f"No se pudo serializar el guardado: {exc}") from exc
    if serialized != raw:
        raise UnsupportedPetAffinitySerialization(
            "La serialización canónica no coincide con el guardado descargado."
        )
    return root, root["serialzedVersion"], raw


def _catalog() -> dict[str, object]:
    catalog = load_pet_catalog()
    if not catalog.get("available"):
        raise PetAffinityCatalogMissing("El catálogo de mascotas no está disponible.")
    return catalog


def affinity_max(numeric_id: int) -> int | None:
    if numeric_id not in AFFINITY_OBSERVED_NUMERIC_IDS:
        return None
    return AFFINITY_MAX_OVERRIDES.get(numeric_id, AFFINITY_DEFAULT_MAX)


def _pet_by_code(catalog: Mapping[str, object], code: str) -> Mapping[str, object] | None:
    pets = catalog.get("pets")
    row = pets.get(code) if isinstance(pets, dict) else None
    return row if isinstance(row, dict) else None


def normalize_pet_affinity_plan(raw: object) -> dict[str, int]:
    if not isinstance(raw, Mapping):
        raise InvalidPetAffinityPlan("pet_affinity debe ser un mapa de código a afinidad.")
    if len(raw) > MAX_PETS:
        raise InvalidPetAffinityPlan(f"pet_affinity supera el máximo de {MAX_PETS} mascotas.")
    catalog = _catalog()
    result: dict[str, int] = {}
    for code, value in raw.items():
        if not isinstance(code, str):
            raise InvalidPetAffinityPlan("pet_affinity contiene un código inválido.")
        row = _pet_by_code(catalog, code)
        if row is None:
            raise InvalidPetAffinityPlan(f"{code!r} no pertenece al catálogo de mascotas 8.8.0.")
        numeric_id = row.get("numeric_id")
        assert type(numeric_id) is int
        maximum = affinity_max(numeric_id)
        if maximum is None:
            raise InvalidPetAffinityPlan(
                f"{code} no tiene un máximo de afinidad demostrado y queda en solo lectura."
            )
        if type(value) is not int or not AFFINITY_MIN <= value <= maximum:
            raise InvalidPetAffinityPlan(
                f"{code} debe tener una afinidad entera entre {AFFINITY_MIN} y {maximum}."
            )
        result[code] = value
    if not result:
        raise InvalidPetAffinityPlan("pet_affinity no contiene ningún cambio.")
    return dict(sorted(result.items()))


@dataclass
class PetAffinityChange:
    path: str
    before: object
    after: object

    def summary(self) -> dict[str, object]:
        return {"path": self.path, "before": self.before, "after": self.after}


@dataclass
class PetAffinityEdit:
    plan: dict[str, int]
    changes: list[PetAffinityChange]
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
            "field": "pet_affinity",
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


def _counts(root: Mapping[str, Any]) -> dict[str, Any]:
    statistic = root.get("statisticData")
    counts = statistic.get("event2Count") if isinstance(statistic, dict) else None
    if not isinstance(counts, dict):
        raise PetAffinityFieldMissing("No existe statisticData.event2Count como mapa de contadores.")
    return counts


def pet_progression_snapshot(payload: Mapping[str, Any]) -> dict[str, object]:
    catalog = _catalog()
    statistic = payload.get("statisticData")
    counts = statistic.get("event2Count") if isinstance(statistic, dict) else None
    available = isinstance(counts, dict)
    counts = counts if isinstance(counts, dict) else {}
    rows_by_id = catalog["pets"]
    assert isinstance(rows_by_id, dict)
    unlock = _unlocked_pets(payload)
    entries: list[dict[str, object]] = []
    for pet_id in catalog["ordered_pets"]:  # type: ignore[union-attr]
        row = rows_by_id[pet_id]
        numeric_id = row["numeric_id"]
        assert type(numeric_id) is int
        prefix = f"pet_{numeric_id}_"
        intimacy_key = f"{prefix}intimacy"
        full_key = f"{prefix}full_intimacy"
        action_key = f"{prefix}action_unlock"
        intimacy = counts.get(intimacy_key)
        full_raw = counts.get(full_key)
        action = counts.get(action_key)
        maximum = affinity_max(numeric_id)
        unlocked = unlock.get(pet_id) is True
        intimacy_key_present = intimacy_key in counts
        full_key_present = full_key in counts
        present = intimacy_key_present or full_key_present
        intimacy_valid = type(intimacy) is int and AFFINITY_MIN <= intimacy <= MAX_VALUE
        initial = not intimacy_key_present and unlocked
        current = intimacy if intimacy_valid else (0 if initial else None)
        full_valid = type(full_raw) is int and full_raw in (0, 1)
        action_valid = type(action) is int and action in (0, 1)
        max_known = maximum is not None
        coherent_full = not full_key_present or full_valid
        not_premature_full = not (full_key_present and full_raw == 1 and current is not None and current < (maximum or 0))
        editable = (
            available
            and unlocked
            and max_known
            and current is not None
            and current < (maximum or 0)
            and coherent_full
            and not_premature_full
        )
        if maximum is None:
            reason = "Máximo no demostrado para esta mascota; solo lectura."
        elif not unlocked:
            reason = "La mascota no está desbloqueada en gameData.petUnlock; desbloquéala primero."
        elif initial:
            reason = "Sin registro de afinidad; se creará con 0 y podrás subirla."
        elif not intimacy_valid:
            reason = "La intimidad no es un entero válido."
        elif current is not None and current >= maximum:
            reason = "La afinidad ya está en el máximo conocido."
        elif full_key_present and not full_valid:
            reason = "El indicador full_intimacy no es 0/1."
        elif not not_premature_full:
            reason = "Estado incoherente: full_intimacy está activo antes del máximo."
        else:
            reason = None
        entries.append(
            {
                "id": pet_id,
                "numeric_id": numeric_id,
                "name": row["name"],
                "present": present,
                "unlocked": unlocked,
                "intimacy": current,
                "full": bool(full_raw) if full_valid else None,
                "action_unlocked": bool(action) if action_valid else None,
                "value_type": None if intimacy_valid else type(intimacy).__name__ if intimacy is not None else None,
                "max": maximum,
                "max_note": AFFINITY_LIMITATION,
                "editable": editable,
                "creatable": initial,
                "reason": reason,
                "path": f"{AFFINITY_PATH}.{intimacy_key}",
                "full_path": f"{AFFINITY_PATH}.{full_key}",
            }
        )
    full_count = counts.get("pet_full_intimacy")
    return {
        "available": available,
        "path": AFFINITY_PATH,
        "read_only": False,
        "global_full_count": full_count if type(full_count) is int else None,
        "full_count_key": "pet_full_intimacy",
        "entries": entries,
        "note": (
            "Afinidad individual y máxima para mascotas desbloqueadas con límite observado. "
            "Una mascota desbloqueada sin registros empieza en 0; al máximo se crea "
            "full_intimacy = 1. No se modifica action_unlock ni el contador global "
            "pet_full_intimacy."
        ),
        "limitation": AFFINITY_LIMITATION,
        "experimental": True,
        "evidence_level": "E2",
    }


def read_pet_affinity(source: bytes) -> dict[str, object]:
    root, _, _ = _validated_document(source)
    return pet_progression_snapshot(root)


def prepare_pet_affinity_edit(source: bytes, plan: object) -> PetAffinityEdit:
    root, version, source = _validated_document(source)
    normalized = normalize_pet_affinity_plan(plan)
    candidate = deepcopy(root)
    counts = _counts(candidate)
    catalog = _catalog()
    unlock = _unlocked_pets(candidate)
    changes: list[PetAffinityChange] = []
    originals: list[tuple[str, object]] = []

    for code, requested in normalized.items():
        row = _pet_by_code(catalog, code)
        assert row is not None
        numeric_id = row["numeric_id"]
        assert type(numeric_id) is int
        maximum = affinity_max(numeric_id)
        assert maximum is not None
        intimacy_key = f"pet_{numeric_id}_intimacy"
        full_key = f"pet_{numeric_id}_full_intimacy"
        if intimacy_key not in counts and unlock.get(code) is not True:
            raise PetAffinityFieldIncompatible(
                f"{code} no está desbloqueada en gameData.petUnlock; "
                "desbloquéala en la misma edición o antes de subir su afinidad."
            )
        before = counts.get(intimacy_key, 0)
        existed = intimacy_key in counts
        if type(before) is not int or before < AFFINITY_MIN or before > MAX_VALUE:
            raise PetAffinityFieldIncompatible(
                f"{AFFINITY_PATH}.{intimacy_key} no es un entero válido."
            )
        if before > maximum:
            raise PetAffinityFieldIncompatible(
                f"{code} supera el máximo observado y queda en solo lectura."
            )
        if requested < before:
            raise InvalidPetAffinityPlan(
                f"No se reduce la afinidad de {code} de {before} a {requested}."
            )
        full_exists = full_key in counts
        full_before = counts.get(full_key)
        if full_exists and (type(full_before) is not int or full_before not in (0, 1)):
            raise PetAffinityFieldIncompatible(
                f"{AFFINITY_PATH}.{full_key} no es un indicador 0/1."
            )
        if full_exists and full_before == 1 and before < maximum:
            raise PetAffinityFieldIncompatible(
                f"{code} declara full_intimacy activo antes del máximo conocido."
            )
        if before == requested:
            continue
        originals.append((intimacy_key, before if existed else _MISSING))
        counts[intimacy_key] = requested
        changes.append(
            PetAffinityChange(
                f"{AFFINITY_PATH}.{intimacy_key}", before if existed else None, requested
            )
        )
        if requested == maximum and full_before != 1:
            originals.append((full_key, full_before if full_exists else _MISSING))
            counts[full_key] = 1
            changes.append(
                PetAffinityChange(
                    f"{AFFINITY_PATH}.{full_key}", full_before if full_exists else None, 1
                )
            )

    changed_fields = tuple(change.path for change in changes)
    if not changes:
        digest = sha256(source).hexdigest()
        return PetAffinityEdit(
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
        raise PetAffinityVerificationError(f"No se pudo serializar el candidato: {exc}") from exc
    if len(candidate_source) > MAX_INPUT_BYTES:
        raise PetAffinityVerificationError("El guardado candidato supera el tamaño permitido.")

    try:
        reconstruct_cloud_save(candidate_source)
        encoding, document = unpack_cloud_save(candidate_source)
        if encoding != "json":
            raise PetAffinityVerificationError("El candidato no conserva el formato JSON.")
        reopened = parse_json(document)
    except (AggregateFormatError, ValueError) as exc:
        raise PetAffinityVerificationError(f"El candidato no se puede volver a abrir: {exc}") from exc
    if not isinstance(reopened, dict):
        raise PetAffinityVerificationError("El candidato no conserva el objeto raíz.")
    if serialize_aggregate(deepcopy(reopened)) != candidate_source:
        raise PetAffinityVerificationError("El candidato no es estable al reserializarlo.")

    reopened_counts = _counts(reopened)
    for change in changes:
        key = change.path.rsplit(".", 1)[-1]
        if reopened_counts.get(key) != change.after:
            raise PetAffinityVerificationError(f"No se conservó {change.path}.")

    for key, before in originals:
        if before is _MISSING:
            reopened_counts.pop(key, None)
        else:
            reopened_counts[key] = before
    if serialize_aggregate(reopened) != source:
        raise PetAffinityVerificationError(
            "La reversión del plan no reproduce el guardado original; hay cambios colaterales."
        )

    binary = binary_diff(source, candidate_source)
    if binary.first_difference is None:
        raise PetAffinityVerificationError("El plan no produjo una diferencia binaria verificable.")
    return PetAffinityEdit(
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


def require_pet_affinity_write_compatibility(
    source: bytes, plan: object, candidate: bytes
) -> None:
    try:
        expected = prepare_pet_affinity_edit(source, plan).candidate
    except PetAffinityEditError as exc:
        if exc.code == PetAffinityVerificationError.code:
            raise
        raise PetAffinityEditError(f"El borrador de afinidad ya no es compatible: {exc}") from exc
    if expected != candidate:
        raise OutdatedPetAffinityDraft("El borrador de afinidad no coincide con el guardado actual.")
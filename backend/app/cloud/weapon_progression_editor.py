"""Editor experimental de descubrimiento y disponibilidad de forja de armas.

La evidencia comparada de cuentas Android e iOS sitúa el contador amplio de
obtención en ``statisticData.object2ObtainTime``. El mapa incluye armas, anillos,
enemigos y jefes; por tanto solo se modifican identificadores que pertenecen al
catálogo de armas visible del jugador.

Reglas deliberadamente conservadoras:

* Un arma se considera descubierta cuando su contador existe y es mayor que 0.
* Al desbloquear solo se eleva un contador ausente o en 0 hasta 1, el valor
  positivo mínimo observado. Nunca se reduce ni se lleva a un máximo.
* ``itemData.forgeWeapons`` es una cola temporal de cuatro ranuras y no se
  escribe. La disponibilidad de forja se deriva de que el arma sea forjable en
  el catálogo y esté descubierta; sigue siendo una hipótesis E2 hasta la
  validación física.
* Los contadores desconocidos, el resto de ``statisticData`` y cualquier dato
  ajeno se conservan byte a byte.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from hashlib import sha256
from typing import Any, Mapping

from ..catalogs.weapons import load_weapon_catalog
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

STATISTIC_PATH = "statisticData"
OBTAIN_PATH = "statisticData.object2ObtainTime"
FORGE_QUEUE_PATH = "itemData.forgeWeapons"
WEAPON_PROGRESSION_RECORD_FIELD = "weapon_progression"
MAX_WEAPONS = 995
MIN_DISCOVERY_VALUE = 1
FORGE_REQUIREMENT_POLICY = "level_map_with_fusion_proxy"


class WeaponProgressionEditError(CloudSaveError):
    code = "weapon_progression_edit"


class InvalidWeaponSelection(WeaponProgressionEditError):
    code = "invalid_weapon_selection"


class UnknownWeapon(WeaponProgressionEditError):
    code = "unknown_weapon"


class WeaponProgressionStructureMissing(WeaponProgressionEditError):
    code = "weapon_progression_structure_missing"


class UnsupportedWeaponProgressionStructure(WeaponProgressionEditError):
    code = "unsupported_weapon_progression_structure"


class WeaponCatalogMissing(WeaponProgressionEditError):
    code = "weapon_catalog_missing"


class UnsupportedWeaponProgressionSerialization(WeaponProgressionEditError):
    code = "weapon_progression_unsupported_serialization"


class WeaponProgressionVerificationError(WeaponProgressionEditError):
    code = "weapon_progression_verification_failed"


class NotForgeableWeapon(WeaponProgressionEditError):
    code = "not_forgeable_weapon"


class ForgeRequirementPending(WeaponProgressionEditError):
    code = "forge_requirement_pending"


class OutdatedWeaponProgressionDraft(WeaponProgressionEditError):
    code = "outdated_weapon_progression_draft"


@dataclass(frozen=True)
class WeaponCatalog:
    ordered: tuple[str, ...]
    entries: dict[str, dict[str, object]] = field(repr=False)
    order: dict[str, int] = field(repr=False)

    @property
    def total(self) -> int:
        return len(self.ordered)

    @property
    def forgeable_total(self) -> int:
        return sum(1 for entry in self.entries.values() if entry.get("forgeable") is True)


def weapon_catalog() -> WeaponCatalog:
    catalog = load_weapon_catalog()
    if not catalog.get("available"):
        raise WeaponCatalogMissing(
            "No está disponible el catálogo de armas; no se puede validar la selección."
        )
    raw_ordered = catalog.get("ordered_weapons")
    raw_weapons = catalog.get("weapons")
    if not isinstance(raw_ordered, (list, tuple)) or not isinstance(raw_weapons, dict):
        raise WeaponCatalogMissing("El catálogo de armas no contiene filas válidas.")
    ordered: list[str] = []
    entries: dict[str, dict[str, object]] = {}
    for weapon_id in raw_ordered:
        row = raw_weapons.get(weapon_id) if isinstance(weapon_id, str) else None
        if not isinstance(row, dict):
            raise WeaponCatalogMissing("El catálogo contiene un arma inválida.")
        ordered.append(weapon_id)  # type: ignore[arg-type]
        entries[weapon_id] = row  # type: ignore[index]
    if len(ordered) != MAX_WEAPONS or len(entries) != MAX_WEAPONS:
        raise WeaponCatalogMissing("El catálogo de armas no contiene sus 995 filas.")
    return WeaponCatalog(
        ordered=tuple(ordered),
        entries=entries,
        order={weapon_id: position for position, weapon_id in enumerate(ordered)},
    )


def _normalize_selection(catalog: WeaponCatalog, selections: object) -> tuple[str, ...]:
    if not isinstance(selections, (list, tuple)):
        raise InvalidWeaponSelection("Selecciona al menos un arma.")
    if not 1 <= len(selections) <= catalog.total:
        raise InvalidWeaponSelection(
            f"La selección debe contener entre 1 y {catalog.total} armas."
        )
    seen: set[str] = set()
    selected: list[str] = []
    for weapon_id in selections:
        if not isinstance(weapon_id, str) or not weapon_id:
            raise InvalidWeaponSelection("La selección contiene un arma inválida.")
        if weapon_id not in catalog.entries:
            raise UnknownWeapon(f"El arma {weapon_id} no pertenece al catálogo visible.")
        if weapon_id in seen:
            raise InvalidWeaponSelection(f"El arma {weapon_id} está repetida.")
        seen.add(weapon_id)
        selected.append(weapon_id)
    return tuple(sorted(selected, key=lambda weapon_id: catalog.order[weapon_id]))


def _validated_document(source: bytes) -> tuple[JsonObject, int]:
    if not source:
        raise CopyLimitError("La copia está vacía.")
    if len(source) > MAX_INPUT_BYTES:
        raise CopyLimitError("La copia supera el límite permitido.")
    reconstruct_cloud_save(source)
    encoding, document = unpack_cloud_save(source)
    if encoding != "json":
        raise UnsupportedWeaponProgressionSerialization(
            "El editor de progresión de armas solo admite el agregado JSON de la nube."
        )
    try:
        root = parse_json(document)
    except (ValueError, RecursionError):
        raise AggregateFormatError("El documento no contiene JSON UTF-8 válido.") from None
    if not isinstance(root, dict):
        raise AggregateFormatError("Se esperaba un objeto JSON en la raíz.")
    if serialize_aggregate(root) != source:
        raise UnsupportedWeaponProgressionSerialization(
            "La copia no usa la serialización canónica observada; no se puede garantizar "
            "que el cambio sea granular."
        )
    version = root.get("serialzedVersion")
    if isinstance(version, bool) or not isinstance(version, int):
        raise AggregateFormatError("Se requiere serialzedVersion como entero.")
    return root, version


def _statistic(root: JsonObject) -> dict[str, Any]:
    statistic = root.get(STATISTIC_PATH)
    if not isinstance(statistic, dict):
        raise WeaponProgressionStructureMissing(
            "La copia no contiene statisticData como objeto."
        )
    return statistic


def _obtain(root: JsonObject, *, allow_missing: bool = False) -> dict[str, Any]:
    statistic = _statistic(root)
    if allow_missing and "object2ObtainTime" not in statistic:
        return {}
    obtain = statistic.get("object2ObtainTime")
    if not isinstance(obtain, dict):
        raise WeaponProgressionStructureMissing(
            "La copia no contiene statisticData.object2ObtainTime como mapa de contadores."
        )
    for key, value in obtain.items():
        # El mapa real incluye claves no pertenecientes al catálogo de armas,
        # incluida una cadena vacía en la muestra Android avanzada. No se
        # interpretan ni se reescriben; solo se validan sus contadores.
        if not isinstance(key, str):
            raise UnsupportedWeaponProgressionStructure(
                "statisticData.object2ObtainTime contiene un identificador inválido."
            )
        if isinstance(value, bool) or type(value) is not int or value < 0:
            raise UnsupportedWeaponProgressionStructure(
                f"statisticData.object2ObtainTime.{key} no es un contador entero no negativo."
            )
    return obtain


def _forge_queue(root: JsonObject) -> tuple[str, ...]:
    item_data = root.get("itemData")
    if not isinstance(item_data, dict):
        return ()
    value = item_data.get("forgeWeapons")
    if value is None:
        return ()
    if not isinstance(value, list):
        return ()
    queue: list[str] = []
    for entry in value:
        if isinstance(entry, str) and entry and entry not in queue:
            queue.append(entry)
    return tuple(queue)


@dataclass(frozen=True)
class WeaponProgressionSnapshot:
    items: tuple[dict[str, object], ...]
    discovered: tuple[str, ...]
    forge_ready: tuple[str, ...]
    forge_unlock_ready: tuple[str, ...]
    pending_requirements: tuple[str, ...]
    forge_queue: tuple[str, ...]
    unknown_weapon_ids: tuple[str, ...]
    total: int
    forgeable_total: int
    unknown_counter_count: int
    size: int
    sha256: str = field(repr=False)
    serialzed_version: int

    def summary(self) -> dict[str, object]:
        return {
            "field": OBTAIN_PATH,
            "items": list(self.items),
            "discovered": list(self.discovered),
            "discovered_count": len(self.discovered),
            "locked_count": self.total - len(self.discovered),
            "total_weapons": self.total,
            "forgeable_total": self.forgeable_total,
            "forge_ready": list(self.forge_ready),
            "forge_ready_count": len(self.forge_ready),
            "forge_unlock_ready": list(self.forge_unlock_ready),
            "forge_unlock_ready_count": len(self.forge_unlock_ready),
            "pending_requirements": list(self.pending_requirements),
            "pending_requirements_count": len(self.pending_requirements),
            "requirement_policy": FORGE_REQUIREMENT_POLICY,
            "obtain_counter_evidence": "E3",
            "forge_queue": list(self.forge_queue),
            "forge_queue_path": FORGE_QUEUE_PATH,
            "unknown_weapon_ids": list(self.unknown_weapon_ids),
            "unknown_counter_count": self.unknown_counter_count,
            "size": self.size,
            "sha256": self.sha256,
            "serialzed_version": self.serialzed_version,
            "discovery_value": MIN_DISCOVERY_VALUE,
            "forge_policy": "derived_experimental",
            "evidence": "E2",
        }


@dataclass(frozen=True)
class WeaponProgressionEdit:
    original_discovered: tuple[str, ...]
    selected_weapons: tuple[str, ...]
    newly_discovered: tuple[str, ...]
    new_discovered: tuple[str, ...]
    new_forge_ready: tuple[str, ...]
    total: int
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
            "field": OBTAIN_PATH,
            "original_discovered_count": len(self.original_discovered),
            "new_discovered_count": len(self.new_discovered),
            "total_weapons": self.total,
            "selected_weapons": list(self.selected_weapons),
            "newly_discovered": list(self.newly_discovered),
            "new_forge_ready": list(self.new_forge_ready),
            "changed": self.changed,
            "original_size": len(self.original),
            "candidate_size": len(self.candidate),
            "original_sha256": self.original_sha256,
            "candidate_sha256": self.candidate_sha256,
            "serialzed_version": self.serialzed_version,
            "binary": self.binary.as_dict(),
            "changed_fields": list(self.changed_fields),
            "discovery_value": MIN_DISCOVERY_VALUE,
            "forge_policy": "derived_experimental",
            "evidence": "E2",
        }


def _forge_requirement(entry: Mapping[str, object]) -> dict[str, object]:
    required = entry.get("required_obtains")
    recommended = entry.get("recommended_obtains")
    return {
        "required_obtains": required if type(required) is int else None,
        "recommended_obtains": recommended if type(recommended) is int else None,
        "requirement_status": entry.get("requirement_status"),
        "requirement_basis": entry.get("requirement_basis"),
        "unlock_method": entry.get("unlock_method"),
        "requirement_evidence": entry.get("requirement_evidence"),
        "additional_requirements": list(entry.get("additional_requirements") or []),  # type: ignore[arg-type]
        "requirement_source": entry.get("requirement_source"),
    }


def _forge_state(can_forge: bool, count: int | None, required: int | None) -> str:
    if not can_forge:
        return "not_forgeable"
    if required is None:
        return "pending_research"
    if count is not None and count >= required:
        return "ready"
    return "requires_obtains"


def read_weapon_progression(source: bytes) -> WeaponProgressionSnapshot:
    root, version = _validated_document(source)
    catalog = weapon_catalog()
    obtain = _obtain(root, allow_missing=True)
    queue = _forge_queue(root)
    discovered: list[str] = []
    forge_ready: list[str] = []
    forge_unlock_ready: list[str] = []
    pending_requirements: list[str] = []
    items: list[dict[str, object]] = []
    for weapon_id in catalog.ordered:
        entry = catalog.entries[weapon_id]
        raw_count = obtain.get(weapon_id)
        count = raw_count if type(raw_count) is int else None
        is_discovered = count is not None and count > 0
        can_forge = entry.get("forgeable") is True
        requirement = _forge_requirement(entry)
        required = requirement["required_obtains"]
        recommended = requirement["recommended_obtains"]
        if is_discovered:
            discovered.append(weapon_id)
        if is_discovered and can_forge:
            forge_ready.append(weapon_id)
        unlock_state = _forge_state(can_forge, count, required)
        if unlock_state == "ready":
            forge_unlock_ready.append(weapon_id)
        if can_forge and required is None:
            pending_requirements.append(weapon_id)
        if not can_forge:
            forge_status = "not_forgeable"
        elif is_discovered:
            forge_status = "ready"
        else:
            forge_status = "requires_discovery"
        proposed_forge = (
            max(count or 0, recommended)
            if can_forge and type(recommended) is int
            else None
        )
        items.append(
            {
                "id": weapon_id,
                "name_en": entry["name"].get("en"),  # type: ignore[union-attr]
                "name_es": entry["name"].get("es"),  # type: ignore[union-attr]
                "subcategory": entry.get("subcategory"),
                "level": entry.get("level"),
                "forgeable": can_forge,
                "drop_level": entry.get("drop_level"),
                "discovered": is_discovered,
                "count": count,
                "proposed_count": count if is_discovered else MIN_DISCOVERY_VALUE,
                "proposed_forge_count": proposed_forge,
                "forge_status": forge_status,
                "forge_ready": is_discovered and can_forge,
                "forge_unlock_status": unlock_state,
                "forge_unlock_ready": unlock_state == "ready",
                "in_forge_queue": weapon_id in queue,
                **requirement,
            }
        )
    unknown = tuple(
        sorted(
            key
            for key in obtain
            if key not in catalog.entries and (key.startswith("weapon_") or key.startswith("ring_"))
        )
    )
    return WeaponProgressionSnapshot(
        items=tuple(items),
        discovered=tuple(discovered),
        forge_ready=tuple(forge_ready),
        forge_unlock_ready=tuple(forge_unlock_ready),
        pending_requirements=tuple(pending_requirements),
        forge_queue=queue,
        unknown_weapon_ids=unknown,
        total=catalog.total,
        forgeable_total=catalog.forgeable_total,
        unknown_counter_count=len(obtain) - sum(
            1 for key in obtain if key in catalog.entries
        ),
        size=len(source),
        sha256=sha256(source).hexdigest(),
        serialzed_version=version,
    )


def prepare_weapon_progression_edit(source: bytes, selections: object) -> WeaponProgressionEdit:
    catalog = weapon_catalog()
    selected = _normalize_selection(catalog, selections)
    root, version = _validated_document(source)
    statistic = _statistic(root)
    had_obtain = "object2ObtainTime" in statistic
    had_statistic = STATISTIC_PATH in root
    obtain = _obtain(root, allow_missing=True)
    original_sha = sha256(source).hexdigest()
    original_snapshot = read_weapon_progression(source)
    original_discovered = original_snapshot.discovered
    discovered_set = set(original_discovered)
    newly_discovered = tuple(
        weapon_id
        for weapon_id in selected
        if weapon_id not in discovered_set
    )
    new_discovered = tuple(
        weapon_id
        for weapon_id in catalog.ordered
        if weapon_id in discovered_set or weapon_id in set(selected)
    )
    new_forge_ready = tuple(
        weapon_id
        for weapon_id in newly_discovered
        if catalog.entries[weapon_id].get("forgeable") is True
    )

    if not newly_discovered:
        return WeaponProgressionEdit(
            original_discovered=original_discovered,
            selected_weapons=selected,
            newly_discovered=(),
            new_discovered=original_discovered,
            new_forge_ready=(),
            total=catalog.total,
            changed=False,
            original=source,
            candidate=source,
            original_sha256=original_sha,
            candidate_sha256=original_sha,
            binary=binary_diff(source, source),
            serialzed_version=version,
        )

    modified = deepcopy(root)
    modified_statistic = _statistic(modified)
    if "object2ObtainTime" not in modified_statistic:
        modified_statistic["object2ObtainTime"] = {}
    modified_obtain = modified_statistic["object2ObtainTime"]
    if not isinstance(modified_obtain, dict):
        raise WeaponProgressionStructureMissing(
            "La copia no contiene statisticData.object2ObtainTime como mapa de contadores."
        )
    for weapon_id in newly_discovered:
        current = modified_obtain.get(weapon_id)
        if type(current) is not int or current < MIN_DISCOVERY_VALUE:
            modified_obtain[weapon_id] = MIN_DISCOVERY_VALUE

    candidate = serialize_aggregate(modified)
    if len(candidate) > MAX_INPUT_BYTES:
        raise CopyLimitError("La copia editada supera el límite permitido.")
    reconstruct_cloud_save(candidate)
    try:
        reopened = parse_json(unpack_cloud_save(candidate)[1])
    except (ValueError, RecursionError):
        raise WeaponProgressionVerificationError(
            "La copia editada no se puede volver a abrir."
        ) from None
    if reopened != modified:
        raise WeaponProgressionVerificationError(
            "La copia reabierta no coincide con la copia editada."
        )
    if serialize_aggregate(reopened) != candidate:
        raise WeaponProgressionVerificationError(
            "La copia editada no es estable al serializarla de nuevo."
        )
    reopened_snapshot = read_weapon_progression(candidate)
    if reopened_snapshot.discovered != new_discovered:
        raise WeaponProgressionVerificationError(
            "La copia editada no contiene exactamente las armas solicitadas."
        )
    # Restaurar el subárbol original debe reproducir la copia byte a byte.
    reopened_statistic = _statistic(reopened)
    if had_obtain:
        reopened_statistic["object2ObtainTime"] = statistic["object2ObtainTime"]
    else:
        reopened_statistic.pop("object2ObtainTime", None)
    if not had_statistic:
        reopened.pop(STATISTIC_PATH, None)
    if serialize_aggregate(reopened) != source:
        raise WeaponProgressionVerificationError(
            "La edición afectó a datos fuera de statisticData.object2ObtainTime."
        )
    binary = binary_diff(source, candidate)
    if binary.first_difference is None:
        raise WeaponProgressionVerificationError("La copia editada es idéntica al original.")

    return WeaponProgressionEdit(
        original_discovered=original_discovered,
        selected_weapons=selected,
        newly_discovered=newly_discovered,
        new_discovered=new_discovered,
        new_forge_ready=new_forge_ready,
        total=catalog.total,
        changed=True,
        original=source,
        candidate=candidate,
        original_sha256=original_sha,
        candidate_sha256=sha256(candidate).hexdigest(),
        binary=binary,
        serialzed_version=version,
        changed_fields=tuple(
            f"{OBTAIN_PATH}.{weapon_id}" for weapon_id in newly_discovered
        ),
    )


@dataclass(frozen=True)
class WeaponForgeUnlockEdit:
    original_forge_ready: tuple[str, ...]
    selected_weapons: tuple[str, ...]
    newly_forge_ready: tuple[str, ...]
    new_forge_ready: tuple[str, ...]
    pending_requirements: tuple[str, ...]
    total: int
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
            "field": OBTAIN_PATH,
            "original_forge_ready_count": len(self.original_forge_ready),
            "new_forge_ready_count": len(self.new_forge_ready),
            "total_weapons": self.total,
            "selected_weapons": list(self.selected_weapons),
            "newly_forge_ready": list(self.newly_forge_ready),
            "pending_requirements": list(self.pending_requirements),
            "changed": self.changed,
            "original_size": len(self.original),
            "candidate_size": len(self.candidate),
            "original_sha256": self.original_sha256,
            "candidate_sha256": self.candidate_sha256,
            "serialzed_version": self.serialzed_version,
            "binary": self.binary.as_dict(),
            "changed_fields": list(self.changed_fields),
            "requirement_policy": FORGE_REQUIREMENT_POLICY,
            "forge_policy": "obtain_threshold_experimental",
            "evidence": "E2",
            "obtain_counter_evidence": "E3",
        }


def _normalize_forge_selection(
    catalog: WeaponCatalog, selections: object
) -> tuple[str, ...]:
    selected = _normalize_selection(catalog, selections)
    for weapon_id in selected:
        entry = catalog.entries[weapon_id]
        if entry.get("forgeable") is not True:
            raise NotForgeableWeapon(
                f"El arma {weapon_id} no es forjable y no se puede preparar para forja."
            )
        if type(entry.get("recommended_obtains")) is not int:
            raise ForgeRequirementPending(
                f"El arma {weapon_id} no tiene un umbral de forja confirmado."
            )
    return selected


def prepare_weapon_forge_unlock_edit(
    source: bytes, selections: object
) -> WeaponForgeUnlockEdit:
    catalog = weapon_catalog()
    selected = _normalize_forge_selection(catalog, selections)
    root, version = _validated_document(source)
    statistic = _statistic(root)
    had_obtain = "object2ObtainTime" in statistic
    had_statistic = STATISTIC_PATH in root
    obtain = _obtain(root, allow_missing=True)
    original_sha = sha256(source).hexdigest()
    before = read_weapon_progression(source)
    before_ready = set(before.forge_unlock_ready)

    changed_ids: list[str] = []
    targets: dict[str, int] = {}
    for weapon_id in selected:
        current = obtain.get(weapon_id)
        current_count = current if type(current) is int else 0
        target = max(current_count, catalog.entries[weapon_id]["recommended_obtains"])  # type: ignore[arg-type]
        targets[weapon_id] = target
        if current_count < target:
            changed_ids.append(weapon_id)

    if not changed_ids:
        return WeaponForgeUnlockEdit(
            original_forge_ready=before.forge_unlock_ready,
            selected_weapons=selected,
            newly_forge_ready=(),
            new_forge_ready=before.forge_unlock_ready,
            pending_requirements=before.pending_requirements,
            total=catalog.total,
            changed=False,
            original=source,
            candidate=source,
            original_sha256=original_sha,
            candidate_sha256=original_sha,
            binary=binary_diff(source, source),
            serialzed_version=version,
        )

    modified = deepcopy(root)
    modified_statistic = _statistic(modified)
    if "object2ObtainTime" not in modified_statistic:
        modified_statistic["object2ObtainTime"] = {}
    modified_obtain = modified_statistic["object2ObtainTime"]
    if not isinstance(modified_obtain, dict):
        raise WeaponProgressionStructureMissing(
            "La copia no contiene statisticData.object2ObtainTime como mapa de contadores."
        )
    for weapon_id in changed_ids:
        modified_obtain[weapon_id] = targets[weapon_id]

    candidate = serialize_aggregate(modified)
    if len(candidate) > MAX_INPUT_BYTES:
        raise CopyLimitError("La copia editada supera el límite permitido.")
    reconstruct_cloud_save(candidate)
    try:
        reopened = parse_json(unpack_cloud_save(candidate)[1])
    except (ValueError, RecursionError):
        raise WeaponProgressionVerificationError(
            "La copia editada no se puede volver a abrir."
        ) from None
    if reopened != modified:
        raise WeaponProgressionVerificationError(
            "La copia reabierta no coincide con la copia editada."
        )
    if serialize_aggregate(reopened) != candidate:
        raise WeaponProgressionVerificationError(
            "La copia editada no es estable al serializarla de nuevo."
        )
    reopened_snapshot = read_weapon_progression(candidate)
    reopened_obtain = _obtain(reopened)
    for weapon_id in selected:
        current = reopened_obtain.get(weapon_id)
        if type(current) is not int or current < targets[weapon_id]:
            raise WeaponProgressionVerificationError(
                f"La copia editada no alcanza el contador de forja de {weapon_id}."
            )
        original = obtain.get(weapon_id)
        if type(original) is int and current < original:
            raise WeaponProgressionVerificationError(
                f"La edición redujo el contador de {weapon_id}."
            )
    reopened_statistic = _statistic(reopened)
    if had_obtain:
        reopened_statistic["object2ObtainTime"] = statistic["object2ObtainTime"]
    else:
        reopened_statistic.pop("object2ObtainTime", None)
    if not had_statistic:
        reopened.pop(STATISTIC_PATH, None)
    if serialize_aggregate(reopened) != source:
        raise WeaponProgressionVerificationError(
            "La edición afectó a datos fuera de statisticData.object2ObtainTime."
        )
    binary = binary_diff(source, candidate)
    if binary.first_difference is None:
        raise WeaponProgressionVerificationError("La copia editada es idéntica al original.")

    after_ready = set(reopened_snapshot.forge_unlock_ready)
    newly_ready = tuple(
        weapon_id for weapon_id in catalog.ordered
        if weapon_id in after_ready and weapon_id not in before_ready
    )
    return WeaponForgeUnlockEdit(
        original_forge_ready=before.forge_unlock_ready,
        selected_weapons=selected,
        newly_forge_ready=newly_ready,
        new_forge_ready=reopened_snapshot.forge_unlock_ready,
        pending_requirements=reopened_snapshot.pending_requirements,
        total=catalog.total,
        changed=True,
        original=source,
        candidate=candidate,
        original_sha256=original_sha,
        candidate_sha256=sha256(candidate).hexdigest(),
        binary=binary,
        serialzed_version=version,
        changed_fields=tuple(
            f"{OBTAIN_PATH}.{weapon_id}" for weapon_id in changed_ids
        ),
    )


def require_weapon_progression_write_compatibility(
    source: bytes, selections: object, candidate: bytes
) -> None:
    if prepare_weapon_progression_edit(source, selections).candidate != candidate:
        raise OutdatedWeaponProgressionDraft(
            "El respaldo usa un borrador antiguo. Prepara de nuevo la selección de armas."
        )
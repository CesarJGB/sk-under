"""Editor de skins cosméticas de arma.

La evidencia real sitúa el estado cosmético en
``weaponEvolutionData.weapons.<arma>`` con cuatro campos observados:

* ``Name``: identificador del arma.
* ``Level``: nivel de evolución; no se modifica.
* ``CurrentSkinIndex``: índice observado de la skin activa. Su semántica exacta
  (incluido el valor 0) todavía no está confirmada, así que es de solo lectura.
* ``UnlockedSkins``: lista de identificadores ``weapon_XXX_s_N`` poseídos.

Una partida Android 8.8.0 nueva puede tener ``weapons`` vacío o ausente. En ese
caso el editor crea el mapa y el registro mínimo observado (``Level`` 0,
``CurrentSkinIndex`` 0) para poder guardar el desbloqueo. Un registro existente
también puede omitir ``UnlockedSkins``; se trata como lista vacía y se crea al
añadir la primera skin. Crear el registro **no acredita poseer el arma**; la
disponibilidad final depende de ``itemData.forgeWeapons`` y debe validarse en el
cliente. El propietario validó el 2026-11-26 en Android físico que las skins
añadidas aparecen y son reconocidas por el juego; la mutación conserva la lógica
E2 original y se documenta como E3. La correspondencia de ``CurrentSkinIndex`` y
la posesión del arma base siguen sin confirmarse.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from hashlib import sha256
from typing import Any, Mapping

from ..catalogs.weapon_skins import load_weapon_skin_catalog
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

WEAPON_EVOLUTION_PATH = "weaponEvolutionData"
WEAPONS_PATH = "weaponEvolutionData.weapons"
WEAPON_SKINS_RECORD_FIELD = "weapon_skins"
MAX_WEAPON_SKINS = 192
MAX_TEXT = 120


class WeaponSkinEditError(CloudSaveError):
    code = "weapon_skins_edit"


class InvalidWeaponSkinSelection(WeaponSkinEditError):
    code = "invalid_weapon_skin_selection"


class UnknownWeaponSkin(WeaponSkinEditError):
    code = "unknown_weapon_skin"


class WeaponSkinStructureMissing(WeaponSkinEditError):
    code = "weapon_skin_structure_missing"


class UnsupportedWeaponSkinStructure(WeaponSkinEditError):
    code = "unsupported_weapon_skin_structure"


class WeaponSkinCatalogMissing(WeaponSkinEditError):
    code = "weapon_skin_catalog_missing"


class UnsupportedWeaponSkinSerialization(WeaponSkinEditError):
    code = "weapon_skin_unsupported_serialization"


class WeaponSkinVerificationError(WeaponSkinEditError):
    code = "weapon_skin_verification_failed"


class OutdatedWeaponSkinDraft(WeaponSkinEditError):
    code = "outdated_weapon_skin_draft"


@dataclass(frozen=True)
class WeaponSkinCatalog:
    ordered: tuple[str, ...]
    entries: dict[str, dict[str, object]] = field(repr=False)
    order: dict[str, int] = field(repr=False)

    @property
    def total(self) -> int:
        return len(self.ordered)


def weapon_skin_catalog() -> WeaponSkinCatalog:
    catalog = load_weapon_skin_catalog()
    if not catalog.get("available"):
        raise WeaponSkinCatalogMissing(
            "No está disponible el catálogo de skins de arma; no se puede validar la selección."
        )
    raw_ordered = catalog.get("ordered_skins")
    raw_skins = catalog.get("skins")
    if not isinstance(raw_ordered, (list, tuple)) or not isinstance(raw_skins, dict):
        raise WeaponSkinCatalogMissing("El catálogo de skins de arma no contiene filas válidas.")
    ordered: list[str] = []
    entries: dict[str, dict[str, object]] = {}
    for skin_id in raw_ordered:
        row = raw_skins.get(skin_id) if isinstance(skin_id, str) else None
        if not isinstance(row, dict):
            raise WeaponSkinCatalogMissing("El catálogo contiene una skin de arma inválida.")
        ordered.append(skin_id)  # type: ignore[arg-type]
        entries[skin_id] = row  # type: ignore[index]
    if len(ordered) != MAX_WEAPON_SKINS or len(entries) != MAX_WEAPON_SKINS:
        raise WeaponSkinCatalogMissing("El catálogo de skins de arma no contiene sus 192 filas.")
    return WeaponSkinCatalog(
        ordered=tuple(ordered),
        entries=entries,
        order={skin_id: position for position, skin_id in enumerate(ordered)},
    )


def _normalize_selection(catalog: WeaponSkinCatalog, selections: object) -> tuple[str, ...]:
    if not isinstance(selections, (list, tuple)):
        raise InvalidWeaponSkinSelection("Selecciona al menos una skin de arma.")
    if not 1 <= len(selections) <= catalog.total:
        raise InvalidWeaponSkinSelection(
            f"La selección debe contener entre 1 y {catalog.total} skins de arma."
        )
    seen: set[str] = set()
    selected: list[str] = []
    for skin_id in selections:
        if not isinstance(skin_id, str) or not skin_id:
            raise InvalidWeaponSkinSelection("La selección contiene una skin de arma inválida.")
        if skin_id not in catalog.entries:
            raise UnknownWeaponSkin(f"La skin de arma {skin_id} no pertenece al catálogo.")
        if skin_id in seen:
            raise InvalidWeaponSkinSelection(f"La skin de arma {skin_id} está repetida.")
        seen.add(skin_id)
        selected.append(skin_id)
    return tuple(sorted(selected, key=lambda skin_id: catalog.order[skin_id]))


def _validated_document(source: bytes) -> tuple[JsonObject, int]:
    root, version = validated_document(
        source,
        unsupported_error=UnsupportedWeaponSkinSerialization,
        unsupported_message=(
            "La copia no usa la serialización canónica observada; no se puede garantizar "
            "que el cambio sea granular."
        ),
    )
    return root, version
def _evolution(root: JsonObject) -> JsonObject:
    evolution = root.get(WEAPON_EVOLUTION_PATH)
    if not isinstance(evolution, dict):
        raise WeaponSkinStructureMissing("La copia no contiene weaponEvolutionData como objeto.")
    return evolution


def _weapons(root: JsonObject, *, allow_missing: bool = False) -> dict[str, Any]:
    evolution = _evolution(root)
    if allow_missing and "weapons" not in evolution:
        return {}
    weapons = evolution.get("weapons")
    if not isinstance(weapons, dict):
        raise WeaponSkinStructureMissing(
            "La copia no contiene weaponEvolutionData.weapons como mapa de armas."
        )
    return weapons


def _validated_record(weapon_id: str, record: object) -> dict[str, Any]:
    if not isinstance(record, dict):
        raise UnsupportedWeaponSkinStructure(
            f"weaponEvolutionData.weapons.{weapon_id} no es un objeto."
        )
    if "UnlockedSkins" in record:
        skins = record["UnlockedSkins"]
        if not isinstance(skins, list):
            raise UnsupportedWeaponSkinStructure(
                f"weaponEvolutionData.weapons.{weapon_id}.UnlockedSkins no es una lista."
            )
        for skin_id in skins:
            if not isinstance(skin_id, str) or not skin_id or len(skin_id) > MAX_TEXT:
                raise UnsupportedWeaponSkinStructure(
                    f"weaponEvolutionData.weapons.{weapon_id}.UnlockedSkins contiene un identificador inválido."
                )
    level = record.get("Level")
    if level is not None and (isinstance(level, bool) or not isinstance(level, int)):
        raise UnsupportedWeaponSkinStructure(
            f"weaponEvolutionData.weapons.{weapon_id}.Level no es un entero."
        )
    current = record.get("CurrentSkinIndex")
    if current is not None and (isinstance(current, bool) or not isinstance(current, int)):
        raise UnsupportedWeaponSkinStructure(
            f"weaponEvolutionData.weapons.{weapon_id}.CurrentSkinIndex no es un entero."
        )
    return record


def _validated_weapons(root: JsonObject, *, allow_missing: bool = False) -> dict[str, Any]:
    weapons = _weapons(root, allow_missing=allow_missing)
    for weapon_id, record in weapons.items():
        if not isinstance(weapon_id, str) or not weapon_id or len(weapon_id) > MAX_TEXT:
            raise UnsupportedWeaponSkinStructure(
                "weaponEvolutionData.weapons contiene un identificador de arma inválido."
            )
        _validated_record(weapon_id, record)
    return weapons


def _unknown_unlocked(weapons: Mapping[str, Any], catalog: WeaponSkinCatalog) -> tuple[str, ...]:
    unknown: list[str] = []
    seen: set[str] = set()
    for record in weapons.values():
        for skin_id in record.get("UnlockedSkins", ()):
            if skin_id not in catalog.entries and skin_id not in seen:
                seen.add(skin_id)
                unknown.append(skin_id)
    return tuple(unknown)


@dataclass(frozen=True)
class WeaponSkinSnapshot:
    items: tuple[dict[str, object], ...]
    unlocked: tuple[str, ...]
    total: int
    weapons_with_data: int
    unknown_weapon_ids: tuple[str, ...]
    unknown_skin_ids: tuple[str, ...]
    size: int
    sha256: str = field(repr=False)
    serialzed_version: int

    def summary(self) -> dict[str, object]:
        return {
            "field": WEAPONS_PATH,
            "items": list(self.items),
            "unlocked": list(self.unlocked),
            "unlocked_count": len(self.unlocked),
            "locked_count": self.total - len(self.unlocked),
            "total_skins": self.total,
            "weapons_with_data": self.weapons_with_data,
            "unknown_weapon_ids": list(self.unknown_weapon_ids),
            "unknown_skin_ids": list(self.unknown_skin_ids),
            "size": self.size,
            "sha256": self.sha256,
            "serialzed_version": self.serialzed_version,
            "equip_policy": "read_only_unconfirmed",
            "evidence": "E3",
        }


@dataclass(frozen=True)
class WeaponSkinEdit:
    original_unlocked: tuple[str, ...]
    selected_skins: tuple[str, ...]
    newly_unlocked: tuple[str, ...]
    new_unlocked: tuple[str, ...]
    total: int
    affected_weapons: tuple[str, ...]
    created_weapons: tuple[str, ...]
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
            "field": WEAPONS_PATH,
            "original_unlocked_count": len(self.original_unlocked),
            "new_unlocked_count": len(self.new_unlocked),
            "total_skins": self.total,
            "selected_skins": list(self.selected_skins),
            "newly_unlocked_skins": list(self.newly_unlocked),
            "affected_weapons": list(self.affected_weapons),
            "created_weapons": list(self.created_weapons),
            "changed": self.changed,
            "original_size": len(self.original),
            "candidate_size": len(self.candidate),
            "original_sha256": self.original_sha256,
            "candidate_sha256": self.candidate_sha256,
            "serialzed_version": self.serialzed_version,
            "binary": self.binary.as_dict(),
            "changed_fields": list(self.changed_fields),
            "evidence": "E3",
        }


def read_weapon_skins(source: bytes) -> WeaponSkinSnapshot:
    root, version = _validated_document(source)
    catalog = weapon_skin_catalog()
    weapons = _validated_weapons(root, allow_missing=True)
    unlocked: list[str] = []
    unlocked_set: set[str] = set()
    for skin_id in catalog.ordered:
        weapon_id = str(catalog.entries[skin_id]["weapon_id"])
        record = weapons.get(weapon_id)
        if record is None:
            continue
        if skin_id in record.get("UnlockedSkins", ()):
            unlocked.append(skin_id)
            unlocked_set.add(skin_id)
    items: list[dict[str, object]] = []
    for skin_id in catalog.ordered:
        entry = catalog.entries[skin_id]
        weapon_id = str(entry["weapon_id"])
        record = weapons.get(weapon_id)
        current_index = record.get("CurrentSkinIndex") if isinstance(record, dict) else None
        skin_index = entry["skin_index"]
        items.append(
            {
                "id": skin_id,
                "name_en": entry["name"].get("en"),  # type: ignore[union-attr]
                "name_es": entry["name"].get("es"),  # type: ignore[union-attr]
                "weapon_id": weapon_id,
                "weapon_name_en": entry["weapon_name"].get("en"),  # type: ignore[union-attr]
                "weapon_name_es": entry["weapon_name"].get("es"),  # type: ignore[union-attr]
                "skin_index": skin_index,
                "unlocked": skin_id in unlocked_set,
                "current_skin_index": current_index,
                "equipped": current_index == skin_index if type(current_index) is int else False,
                "level": record.get("Level") if isinstance(record, dict) else None,
            }
        )
    unknown_weapons = tuple(
        sorted(
            weapon_id
            for weapon_id in weapons
            if weapon_id
            not in {
                str(entry["weapon_id"])
                for entry in catalog.entries.values()
            }
        )
    )
    return WeaponSkinSnapshot(
        items=tuple(items),
        unlocked=tuple(unlocked),
        total=catalog.total,
        weapons_with_data=len(weapons),
        unknown_weapon_ids=unknown_weapons,
        unknown_skin_ids=_unknown_unlocked(weapons, catalog),
        size=len(source),
        sha256=sha256(source).hexdigest(),
        serialzed_version=version,
    )


def prepare_weapon_skin_unlock_edit(source: bytes, selections: object) -> WeaponSkinEdit:
    catalog = weapon_skin_catalog()
    selected = _normalize_selection(catalog, selections)
    root, version = _validated_document(source)
    evolution = _evolution(root)
    had_weapons = "weapons" in evolution
    weapons = _validated_weapons(root, allow_missing=True)
    original_sha = sha256(source).hexdigest()
    original_snapshot = read_weapon_skins(source)
    original_unlocked = original_snapshot.unlocked
    unlocked_set = set(original_unlocked)
    newly_unlocked = tuple(skin_id for skin_id in selected if skin_id not in unlocked_set)
    new_unlocked = tuple(skin_id for skin_id in catalog.ordered if skin_id in unlocked_set | set(selected))

    created_weapons: list[str] = []
    affected: list[str] = []
    for skin_id in newly_unlocked:
        weapon_id = str(catalog.entries[skin_id]["weapon_id"])
        if weapon_id not in affected:
            affected.append(weapon_id)
        if weapon_id not in weapons:
            created_weapons.append(weapon_id)

    if not newly_unlocked:
        return WeaponSkinEdit(
            original_unlocked=original_unlocked,
            selected_skins=selected,
            newly_unlocked=(),
            new_unlocked=original_unlocked,
            total=catalog.total,
            affected_weapons=(),
            created_weapons=(),
            changed=False,
            original=source,
            candidate=source,
            original_sha256=original_sha,
            candidate_sha256=original_sha,
            binary=binary_diff(source, source),
            serialzed_version=version,
        )

    modified = deepcopy(root)
    modified_evolution = _evolution(modified)
    if "weapons" not in modified_evolution:
        modified_evolution["weapons"] = {}
    modified_weapons = _validated_weapons(modified)
    for skin_id in newly_unlocked:
        weapon_id = str(catalog.entries[skin_id]["weapon_id"])
        record = modified_weapons.get(weapon_id)
        if record is None:
            record = {
                "Name": weapon_id,
                "Level": 0,
                "CurrentSkinIndex": 0,
                "UnlockedSkins": [],
            }
            modified_weapons[weapon_id] = record
        if "UnlockedSkins" not in record:
            record["UnlockedSkins"] = []
        if skin_id not in record["UnlockedSkins"]:
            record["UnlockedSkins"].append(skin_id)

    candidate = serialize_aggregate(modified)
    if len(candidate) > MAX_INPUT_BYTES:
        raise CopyLimitError("La copia editada supera el límite permitido.")
    reconstruct_cloud_save(candidate)
    try:
        reopened = parse_json(unpack_cloud_save(candidate)[1])
    except (ValueError, RecursionError):
        raise WeaponSkinVerificationError("La copia editada no se puede volver a abrir.") from None
    if reopened != modified:
        raise WeaponSkinVerificationError("La copia reabierta no coincide con la copia editada.")
    if serialize_aggregate(reopened) != candidate:
        raise WeaponSkinVerificationError("La copia editada no es estable al serializarla de nuevo.")
    reopened_snapshot = read_weapon_skins(candidate)
    if reopened_snapshot.unlocked != new_unlocked:
        raise WeaponSkinVerificationError(
            "La copia editada no contiene exactamente las skins de arma solicitadas."
        )
    # Restaurar el mapa original completo debe reproducir la copia byte a byte:
    # así se demuestra que no cambió ningún dato ajeno a las skins de arma.
    reopened_evolution = _evolution(reopened)
    if had_weapons:
        reopened_evolution["weapons"] = evolution["weapons"]
    else:
        reopened_evolution.pop("weapons", None)
    if serialize_aggregate(reopened) != source:
        raise WeaponSkinVerificationError(
            "La edición afectó a datos fuera de weaponEvolutionData.weapons."
        )
    binary = binary_diff(source, candidate)
    if binary.first_difference is None:
        raise WeaponSkinVerificationError("La copia editada es idéntica al original.")

    changed_fields = tuple(
        f"{WEAPONS_PATH}.{weapon_id}.UnlockedSkins" for weapon_id in affected
    )
    return WeaponSkinEdit(
        original_unlocked=original_unlocked,
        selected_skins=selected,
        newly_unlocked=newly_unlocked,
        new_unlocked=new_unlocked,
        total=catalog.total,
        affected_weapons=tuple(affected),
        created_weapons=tuple(created_weapons),
        changed=True,
        original=source,
        candidate=candidate,
        original_sha256=original_sha,
        candidate_sha256=sha256(candidate).hexdigest(),
        binary=binary,
        serialzed_version=version,
        changed_fields=changed_fields,
    )


def require_weapon_skin_write_compatibility(
    source: bytes, selections: object, candidate: bytes
) -> None:
    if prepare_weapon_skin_unlock_edit(source, selections).candidate != candidate:
        raise OutdatedWeaponSkinDraft(
            "El respaldo usa un borrador antiguo. Prepara de nuevo la selección antes de subirla."
        )

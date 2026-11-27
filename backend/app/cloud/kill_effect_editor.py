"""Editor de efectos de eliminación.

La partida guarda dos campos independientes dentro de ``miscData``:

* ``unlockedKillEffectIds``: lista de enteros poseídos. Las muestras observadas
  incluyen 0-10; el catálogo local solo puede nombrar y validar 0-8. Los valores
  desconocidos se conservan intactos.
* ``equippedKillEffectIdByScene``: pares ``{Key, Value}`` por escena. El
  significado de las escenas y la selección activa no están confirmados, por lo
  que este editor nunca los modifica.

Si ``miscData`` o ``unlockedKillEffectIds`` no existen, se tratan como un
inventario vacío y la edición crea únicamente el campo mínimo evidenciado. El
resto de claves de ``miscData``, incluidas las escenas equipadas, se conserva
intacto. El propietario validó el 2026-11-26 en Android físico que los efectos
añadidos son reconocidos por el juego; la mutación conserva la lógica E2 original
y se documenta como E3. La semántica de las escenas sigue sin confirmarse.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
from typing import Any

from ..catalogs.kill_effects import load_kill_effect_catalog
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
from .lab import BinaryDiff, binary_diff, clone_json

MISC_PATH = "miscData"
UNLOCKED_PATH = "miscData.unlockedKillEffectIds"
EQUIPPED_PATH = "miscData.equippedKillEffectIdByScene"
KILL_EFFECTS_RECORD_FIELD = "kill_effects"
MAX_KILL_EFFECTS = 9


class KillEffectEditError(CloudSaveError):
    code = "kill_effects_edit"


class InvalidKillEffectSelection(KillEffectEditError):
    code = "invalid_kill_effect_selection"


class UnknownKillEffect(KillEffectEditError):
    code = "unknown_kill_effect"


class KillEffectStructureMissing(KillEffectEditError):
    code = "kill_effect_structure_missing"


class UnsupportedKillEffectStructure(KillEffectEditError):
    code = "unsupported_kill_effect_structure"


class KillEffectCatalogMissing(KillEffectEditError):
    code = "kill_effect_catalog_missing"


class UnsupportedKillEffectSerialization(KillEffectEditError):
    code = "kill_effect_unsupported_serialization"


class KillEffectVerificationError(KillEffectEditError):
    code = "kill_effect_verification_failed"


class OutdatedKillEffectDraft(KillEffectEditError):
    code = "outdated_kill_effect_draft"


@dataclass(frozen=True)
class KillEffectCatalog:
    ordered: tuple[int, ...]
    entries: dict[int, dict[str, object]] = field(repr=False)

    @property
    def total(self) -> int:
        return len(self.ordered)


def kill_effect_catalog() -> KillEffectCatalog:
    catalog = load_kill_effect_catalog()
    if not catalog.get("available"):
        raise KillEffectCatalogMissing(
            "No está disponible el catálogo de efectos de eliminación."
        )
    raw_ordered = catalog.get("ordered_effects")
    raw_effects = catalog.get("effects")
    if not isinstance(raw_ordered, (list, tuple)) or not isinstance(raw_effects, dict):
        raise KillEffectCatalogMissing(
            "El catálogo de efectos de eliminación no contiene filas válidas."
        )
    ordered: list[int] = []
    entries: dict[int, dict[str, object]] = {}
    for effect_id in raw_ordered:
        row = raw_effects.get(effect_id) if type(effect_id) is int else None
        if not isinstance(row, dict):
            raise KillEffectCatalogMissing(
                "El catálogo contiene un efecto de eliminación inválido."
            )
        ordered.append(effect_id)  # type: ignore[arg-type]
        entries[effect_id] = row  # type: ignore[index]
    if len(ordered) != MAX_KILL_EFFECTS or len(entries) != MAX_KILL_EFFECTS:
        raise KillEffectCatalogMissing(
            "El catálogo de efectos de eliminación no contiene sus 9 filas."
        )
    return KillEffectCatalog(ordered=tuple(ordered), entries=entries)


def _normalize_selection(catalog: KillEffectCatalog, selections: object) -> tuple[int, ...]:
    if not isinstance(selections, (list, tuple)):
        raise InvalidKillEffectSelection("Selecciona al menos un efecto de eliminación.")
    if not 1 <= len(selections) <= catalog.total:
        raise InvalidKillEffectSelection(
            f"La selección debe contener entre 1 y {catalog.total} efectos."
        )
    seen: set[int] = set()
    selected: list[int] = []
    for effect_id in selections:
        if isinstance(effect_id, bool) or type(effect_id) is not int:
            raise InvalidKillEffectSelection("La selección contiene un efecto inválido.")
        if effect_id not in catalog.entries:
            raise UnknownKillEffect(
                f"El efecto de eliminación {effect_id} no pertenece al catálogo evidenciado."
            )
        if effect_id in seen:
            raise InvalidKillEffectSelection(f"El efecto de eliminación {effect_id} está repetido.")
        seen.add(effect_id)
        selected.append(effect_id)
    return tuple(sorted(selected))


def _validated_document(source: bytes) -> tuple[JsonObject, int]:
    root, version = validated_document(
        source,
        unsupported_error=UnsupportedKillEffectSerialization,
        unsupported_message=(
            "La copia no usa la serialización canónica observada; no se puede garantizar "
            "que el cambio sea granular."
        ),
    )
    return root, version
def _misc(root: JsonObject) -> dict[str, Any]:
    misc = root.get(MISC_PATH)
    if not isinstance(misc, dict):
        raise KillEffectStructureMissing("La copia no contiene miscData como objeto.")
    return misc


def _misc_or_none(root: JsonObject) -> dict[str, Any] | None:
    if MISC_PATH not in root:
        return None
    return _misc(root)


def _unlocked(root: JsonObject, *, allow_missing: bool = False) -> list[int]:
    if allow_missing:
        misc = _misc_or_none(root)
        if misc is None or "unlockedKillEffectIds" not in misc:
            return []
    else:
        misc = _misc(root)
        if "unlockedKillEffectIds" not in misc:
            raise KillEffectStructureMissing(
                "La copia no contiene miscData.unlockedKillEffectIds."
            )
    value = misc["unlockedKillEffectIds"]
    if not isinstance(value, list):
        raise UnsupportedKillEffectStructure(
            "miscData.unlockedKillEffectIds no es una lista de enteros."
        )
    seen: set[int] = set()
    for effect_id in value:
        if isinstance(effect_id, bool) or type(effect_id) is not int:
            raise UnsupportedKillEffectStructure(
                "miscData.unlockedKillEffectIds contiene un valor que no es un entero."
            )
        if effect_id in seen:
            raise UnsupportedKillEffectStructure(
                f"miscData.unlockedKillEffectIds repite el identificador {effect_id}."
            )
        seen.add(effect_id)
    return value


def _equipped(root: JsonObject) -> tuple[dict[str, int], ...]:
    misc = _misc_or_none(root)
    if misc is None:
        return ()
    value = misc.get("equippedKillEffectIdByScene")
    if value is None:
        return ()
    if not isinstance(value, list):
        raise UnsupportedKillEffectStructure(
            "miscData.equippedKillEffectIdByScene no es una lista de escenas."
        )
    scenes: list[dict[str, int]] = []
    seen: set[int] = set()
    for entry in value:
        if not isinstance(entry, dict):
            raise UnsupportedKillEffectStructure(
                "miscData.equippedKillEffectIdByScene contiene una entrada inválida."
            )
        key = entry.get("Key")
        effect_id = entry.get("Value")
        if (
            isinstance(key, bool)
            or type(key) is not int
            or isinstance(effect_id, bool)
            or type(effect_id) is not int
        ):
            raise UnsupportedKillEffectStructure(
                "miscData.equippedKillEffectIdByScene contiene valores no enteros."
            )
        if key in seen:
            raise UnsupportedKillEffectStructure(
                f"miscData.equippedKillEffectIdByScene repite la escena {key}."
            )
        seen.add(key)
        scenes.append({"scene": key, "effect_id": effect_id})
    return tuple(scenes)


@dataclass(frozen=True)
class KillEffectSnapshot:
    items: tuple[dict[str, object], ...]
    unlocked: tuple[int, ...]
    total: int
    equipped: tuple[dict[str, int], ...]
    unknown_unlocked_ids: tuple[int, ...]
    size: int
    sha256: str = field(repr=False)
    serialzed_version: int

    def summary(self) -> dict[str, object]:
        return {
            "field": UNLOCKED_PATH,
            "items": list(self.items),
            "unlocked": list(self.unlocked),
            "unlocked_count": len(self.unlocked),
            "locked_count": self.total - len(self.unlocked),
            "total_effects": self.total,
            "equipped": list(self.equipped),
            "unknown_unlocked_ids": list(self.unknown_unlocked_ids),
            "size": self.size,
            "sha256": self.sha256,
            "serialzed_version": self.serialzed_version,
            "equip_policy": "read_only_unconfirmed",
            "scene_semantics": "unconfirmed",
            "evidence": "E3",
        }


@dataclass(frozen=True)
class KillEffectEdit:
    original_unlocked: tuple[int, ...]
    selected_effects: tuple[int, ...]
    newly_unlocked: tuple[int, ...]
    new_unlocked: tuple[int, ...]
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
            "field": UNLOCKED_PATH,
            "original_unlocked_count": len(self.original_unlocked),
            "new_unlocked_count": len(self.new_unlocked),
            "total_effects": self.total,
            "selected_effects": list(self.selected_effects),
            "newly_unlocked_effects": list(self.newly_unlocked),
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


def read_kill_effects(source: bytes) -> KillEffectSnapshot:
    root, version = _validated_document(source)
    catalog = kill_effect_catalog()
    unlocked = _unlocked(root, allow_missing=True)
    equipped = _equipped(root)
    unlocked_set = set(unlocked)
    items: list[dict[str, object]] = []
    for effect_id in catalog.ordered:
        entry = catalog.entries[effect_id]
        items.append(
            {
                "id": effect_id,
                "item_id": entry["item_id"],
                "name_en": entry["name"].get("en"),  # type: ignore[union-attr]
                "name_es": entry["name"].get("es"),  # type: ignore[union-attr]
                "icon": entry["icon"],
                "acquisition": entry["acquisition"],
                "is_default": effect_id == 0,
                "unlocked": effect_id in unlocked_set,
            }
        )
    unknowns = tuple(sorted(effect_id for effect_id in unlocked_set if effect_id not in catalog.entries))
    return KillEffectSnapshot(
        items=tuple(items),
        unlocked=tuple(effect_id for effect_id in unlocked if effect_id in catalog.entries),
        total=catalog.total,
        equipped=equipped,
        unknown_unlocked_ids=unknowns,
        size=len(source),
        sha256=sha256(source).hexdigest(),
        serialzed_version=version,
    )


def prepare_kill_effect_unlock_edit(source: bytes, selections: object) -> KillEffectEdit:
    catalog = kill_effect_catalog()
    selected = _normalize_selection(catalog, selections)
    root, version = _validated_document(source)
    misc = _misc_or_none(root)
    had_misc = misc is not None
    had_unlocked = had_misc and "unlockedKillEffectIds" in misc
    original = _unlocked(root, allow_missing=True)
    original_sha = sha256(source).hexdigest()
    original_set = set(original)
    newly_unlocked = tuple(effect_id for effect_id in selected if effect_id not in original_set)
    new_unlocked = tuple(
        effect_id for effect_id in original + list(newly_unlocked) if effect_id in catalog.entries
    )
    if not newly_unlocked:
        return KillEffectEdit(
            original_unlocked=tuple(original),
            selected_effects=selected,
            newly_unlocked=(),
            new_unlocked=tuple(original),
            total=catalog.total,
            changed=False,
            original=source,
            candidate=source,
            original_sha256=original_sha,
            candidate_sha256=original_sha,
            binary=binary_diff(source, source),
            serialzed_version=version,
        )

    modified = clone_json(root)
    if not had_misc:
        modified[MISC_PATH] = {}
    modified_misc = _misc(modified)
    if "unlockedKillEffectIds" not in modified_misc:
        modified_misc["unlockedKillEffectIds"] = []
    modified_unlocked = _unlocked(modified)
    for effect_id in newly_unlocked:
        if effect_id not in modified_unlocked:
            modified_unlocked.append(effect_id)

    candidate = serialize_aggregate(modified)
    if len(candidate) > MAX_INPUT_BYTES:
        raise CopyLimitError("La copia editada supera el límite permitido.")
    reconstruct_cloud_save(candidate)
    try:
        reopened = parse_json(unpack_cloud_save(candidate)[1])
    except (ValueError, RecursionError):
        raise KillEffectVerificationError("La copia editada no se puede volver a abrir.") from None
    if reopened != modified:
        raise KillEffectVerificationError("La copia reabierta no coincide con la copia editada.")
    if serialize_aggregate(reopened) != candidate:
        raise KillEffectVerificationError("La copia editada no es estable al serializarla de nuevo.")
    reopened_snapshot = read_kill_effects(candidate)
    expected_unlocked = tuple(
        effect_id for effect_id in original + list(newly_unlocked) if effect_id in catalog.entries
    )
    if reopened_snapshot.unlocked != expected_unlocked:
        raise KillEffectVerificationError(
            "La copia editada no contiene exactamente los efectos solicitados."
        )
    if reopened_snapshot.equipped != _equipped(root):
        raise KillEffectVerificationError(
            "La edición alteró miscData.equippedKillEffectIdByScene."
        )
    if had_misc and had_unlocked:
        reopened["miscData"]["unlockedKillEffectIds"] = original
    elif had_misc:
        reopened["miscData"].pop("unlockedKillEffectIds", None)
    else:
        reopened.pop("miscData", None)
    if serialize_aggregate(reopened) != source:
        raise KillEffectVerificationError(
            "La edición afectó a datos fuera de miscData.unlockedKillEffectIds."
        )
    binary = binary_diff(source, candidate)
    if binary.first_difference is None:
        raise KillEffectVerificationError("La copia editada es idéntica al original.")

    return KillEffectEdit(
        original_unlocked=tuple(original),
        selected_effects=selected,
        newly_unlocked=newly_unlocked,
        new_unlocked=new_unlocked,
        total=catalog.total,
        changed=True,
        original=source,
        candidate=candidate,
        original_sha256=original_sha,
        candidate_sha256=sha256(candidate).hexdigest(),
        binary=binary,
        serialzed_version=version,
        changed_fields=(UNLOCKED_PATH,),
    )


def require_kill_effect_write_compatibility(
    source: bytes, selections: object, candidate: bytes
) -> None:
    if prepare_kill_effect_unlock_edit(source, selections).candidate != candidate:
        raise OutdatedKillEffectDraft(
            "El respaldo usa un borrador antiguo. Prepara de nuevo la selección antes de subirla."
        )

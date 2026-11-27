"""Editor atómico de materiales, semillas, moneda de temporada, tarjeta de
renacimiento y progreso local del pase de batalla.

El módulo no toca fichas, gemas, recompensas reclamadas ni recibos. Aplica un
plan completo sobre una copia del agregado, comprueba que solo cambiaron las
rutas solicitadas y revierte el plan para exigir una serialización idéntica al
origen. La escritura remota se realiza únicamente a través del flujo de
confirmación existente.
"""

from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass, field
from hashlib import sha256
from typing import Any, Iterable, Mapping

from ..catalogs.items import load_item_catalog
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
from .blueprint_editor import blueprints_snapshot
from .decoration_editor import decorations_snapshot
from .gems_editor import serialize_aggregate
from .aggregate_cache import validated_document
from .hero_level_editor import hero_levels_snapshot
from .lab import BinaryDiff, binary_diff
from .pet_affinity_editor import pet_progression_snapshot

MATERIALS_PATH = "itemData.materials"
SEEDS_PATH = "itemData.seeds"
SEASON_COIN_PATH = "seasonData.coin"
REBORN_PATH = "gameData.rebornCard"
BATTLE_PASS_PATH = "battlePassSaveData.seasonData"
PETS_PATH = "gameData.petUnlock"
PET_FOOD_IDS = frozenset({"material_grain", "material_battery"})
ADVANCED_RECORD_FIELD = "advanced"
MIN_VALUE = 0
MAX_VALUE = 2_147_483_647  # Límite estructural int32; no es un tope confirmado del juego.
MAX_ITEMS = 400
MAX_CHANGES = 500

REBORN_LIMITATION = (
    "El propietario confirmó en Android físico que gameData.rebornCard = true basta para que la "
    "tarjeta de renacimiento permanente aparezca comprada. La preferencia local "
    "shared_pref:reborn_card = 1 se conserva como referencia de proyección; no se edita directamente."
)


class AdvancedEditError(CloudSaveError):
    code = "advanced_edit"


class InvalidAdvancedPlan(AdvancedEditError):
    code = "advanced_plan_invalid"


class UnsupportedAdvancedSerialization(AdvancedEditError):
    code = "advanced_unsupported_serialization"


class AdvancedFieldMissing(AdvancedEditError):
    code = "advanced_field_missing"


class AdvancedFieldIncompatible(AdvancedEditError):
    code = "advanced_field_incompatible"


class AdvancedSeasonMissing(AdvancedEditError):
    code = "advanced_season_missing"


class AdvancedSeasonDuplicate(AdvancedEditError):
    code = "advanced_season_duplicate"


class AdvancedVerificationError(AdvancedEditError):
    code = "advanced_verification"


class OutdatedAdvancedDraft(AdvancedEditError):
    code = "advanced_outdated"


def _int(value: object, minimum: int = MIN_VALUE, maximum: int = MAX_VALUE) -> int:
    if type(value) is not int or value < minimum or value > maximum:
        raise InvalidAdvancedPlan(
            f"Se esperaba un entero entre {minimum} y {maximum}; se recibió {value!r}."
        )
    return value


def _mapping(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise AdvancedFieldIncompatible(f"{label} no es un objeto JSON.")
    return value


def _plan_map(raw: object, catalog_ids: frozenset[str], label: str) -> dict[str, int]:
    if raw is None:
        return {}
    if isinstance(raw, Mapping):
        entries: list[object] = [
            {"id": item_id, "value": value} for item_id, value in raw.items()
        ]
    elif isinstance(raw, list):
        entries = list(raw)
    else:
        raise InvalidAdvancedPlan(f"{label} debe ser una lista o un mapa de cambios.")
    if len(entries) > MAX_ITEMS:
        raise InvalidAdvancedPlan(f"{label} supera el máximo de {MAX_ITEMS} elementos.")
    result: dict[str, int] = {}
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {"id", "value"}:
            raise InvalidAdvancedPlan(f"{label} contiene un cambio con forma inválida.")
        item_id = entry["id"]
        if not isinstance(item_id, str) or not item_id:
            raise InvalidAdvancedPlan(f"{label} contiene un identificador inválido.")
        if item_id not in catalog_ids:
            raise InvalidAdvancedPlan(f"{item_id} no pertenece al catálogo 8.8.0.")
        if item_id == "material_fish":
            raise InvalidAdvancedPlan(
                "material_fish no se edita aquí: es el espejo de gameData.fishChip."
            )
        if item_id in result:
            raise InvalidAdvancedPlan(f"{label} repite el identificador {item_id}.")
        result[item_id] = _int(entry["value"])
    return dict(sorted(result.items()))


def normalize_advanced_plan(raw: Mapping[str, object]) -> dict[str, object]:
    """Convierte la entrada de la API en un plan determinista y validado."""
    if not isinstance(raw, Mapping):
        raise InvalidAdvancedPlan("El plan debe ser un objeto JSON.")
    allowed = {"materials", "seeds", "season_coin", "reborn_card", "battle_pass", "pets", "pet_food"}
    unknown = set(raw) - allowed
    if unknown:
        raise InvalidAdvancedPlan(f"El plan contiene claves no autorizadas: {sorted(unknown)}.")
    catalog = load_item_catalog()
    if not catalog.get("available"):
        raise AdvancedEditError("El catálogo de materiales y semillas no está disponible.")
    materials = _plan_map(raw.get("materials"), catalog["material_ids"], "materials")  # type: ignore[arg-type]
    seeds = _plan_map(raw.get("seeds"), catalog["seed_ids"], "seeds")  # type: ignore[arg-type]
    pet_catalog = load_pet_catalog()
    if not pet_catalog.get("available"):
        raise AdvancedEditError("El catálogo de mascotas no está disponible.")
    pets = _pet_selection(raw.get("pets"), pet_catalog)
    pet_food = _plan_map(raw.get("pet_food"), catalog["material_ids"], "pet_food")  # type: ignore[arg-type]
    for item_id in pet_food:
        if item_id not in PET_FOOD_IDS:
            raise InvalidAdvancedPlan(f"{item_id} no es un alimento de mascota compatible.")
    for item_id, value in pet_food.items():
        if item_id in materials and materials[item_id] != value:
            raise InvalidAdvancedPlan(
                f"{item_id} se solicita con cantidades distintas en materials y pet_food."
            )
    # El alimento comparte el único escritor de itemData.materials.
    materials.update(pet_food)
    materials = dict(sorted(materials.items()))
    season_coin = raw.get("season_coin")
    if season_coin is not None:
        season_coin = _int(season_coin)
    reborn_card = raw.get("reborn_card")
    if reborn_card is not None and reborn_card is not True:
        raise InvalidAdvancedPlan("reborn_card solo admite true en esta fase.")
    battle_pass_raw = raw.get("battle_pass")
    battle_pass: dict[str, object] | None = None
    if battle_pass_raw is not None:
        if not isinstance(battle_pass_raw, Mapping):
            raise InvalidAdvancedPlan("battle_pass debe ser un objeto JSON.")
        bp_allowed = {"season_id", "cur_level", "cur_exp", "has_buy"}
        unknown = set(battle_pass_raw) - bp_allowed
        if unknown:
            raise InvalidAdvancedPlan(f"battle_pass contiene claves no autorizadas: {sorted(unknown)}.")
        season_id = _int(battle_pass_raw.get("season_id"))
        selected = {"season_id": season_id}
        for key, value in (
            ("cur_level", battle_pass_raw.get("cur_level")),
            ("cur_exp", battle_pass_raw.get("cur_exp")),
        ):
            if value is not None:
                selected[key] = _int(value)
        has_buy = battle_pass_raw.get("has_buy")
        if has_buy is not None:
            if type(has_buy) is not bool:
                raise InvalidAdvancedPlan("has_buy debe ser booleano.")
            selected["has_buy"] = has_buy
        if len(selected) == 1:
            raise InvalidAdvancedPlan("battle_pass no solicita ningún cambio.")
        battle_pass = selected
    if not any((materials, seeds, season_coin is not None, reborn_card is True, battle_pass, pets)):
        raise InvalidAdvancedPlan("El plan no contiene ningún cambio.")
    if len(materials) + len(seeds) + (0 if season_coin is None else 1) + (
        0 if reborn_card is None else 1
    ) + (0 if battle_pass is None else len(battle_pass) - 1) + len(pets) > MAX_CHANGES:
        raise InvalidAdvancedPlan("El plan supera el máximo de cambios.")
    return {
        "materials": materials,
        "seeds": seeds,
        "season_coin": season_coin,
        "reborn_card": True if reborn_card is True else None,
        "battle_pass": battle_pass,
        "pets": pets,
        "pet_food": pet_food,
    }


def _pet_selection(raw: object, catalog: Mapping[str, object]) -> list[str]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise InvalidAdvancedPlan("pets debe ser una lista de códigos.")
    if len(raw) > 70:
        raise InvalidAdvancedPlan("pets supera el máximo de códigos admitido.")
    pet_ids = catalog["pet_ids"]
    skin_ids = catalog["skin_ids"]
    skins = catalog["pet_skins"]
    assert isinstance(pet_ids, frozenset) and isinstance(skin_ids, frozenset)
    selected: set[str] = set()
    seen: set[str] = set()
    for value in raw:
        if not isinstance(value, str) or not value:
            raise InvalidAdvancedPlan("pets contiene un código inválido.")
        if value in seen:
            raise InvalidAdvancedPlan(f"pets repite el código {value}.")
        if value not in pet_ids and value not in skin_ids:
            raise InvalidAdvancedPlan(f"{value} no pertenece al catálogo de mascotas 8.8.0.")
        seen.add(value)
        selected.add(value)
    # Dependencia explícita: una variante seleccionada arrastra su mascota base.
    for skin_id in sorted(selected & skin_ids):
        skin = skins[skin_id]  # type: ignore[index]
        selected.add(str(skin["base_pet"]))  # type: ignore[index]
    return sorted(selected)


def _validated_document(source: bytes) -> tuple[JsonObject, int, bytes]:
    root, version = validated_document(
        source,
        unsupported_error=UnsupportedAdvancedSerialization,
        unsupported_message=(
            "La copia no usa la serialización canónica observada; no se puede garantizar "
            "que el cambio sea granular."
        ),
    )
    return root, version, bytes(source)
def _load_catalog(context: str = "advanced") -> dict[str, object]:
    catalog = load_item_catalog()
    if not catalog.get("available"):
        raise AdvancedEditError("El catálogo de materiales y semillas no está disponible.")
    return catalog


def _bp_records(root: Mapping[str, Any]) -> tuple[dict[str, Any], list[Any]]:
    container = root.get("battlePassSaveData")
    if not isinstance(container, dict) or not isinstance(container.get("seasonData"), list):
        raise AdvancedFieldMissing("No existe battlePassSaveData.seasonData en este guardado.")
    records = container["seasonData"]
    if len(records) > MAX_ITEMS:
        raise AdvancedFieldIncompatible("battlePassSaveData.seasonData supera el tamaño admitido.")
    return container, records


def _bp_value(record: object) -> Mapping[str, Any] | None:
    if not isinstance(record, dict):
        return None
    value = record.get("Value")
    return value if isinstance(value, dict) else None


def _max_level(value: Mapping[str, Any]) -> int | None:
    for key in ("maxLevel", "max_level", "levelMax"):
        candidate = value.get(key)
        if type(candidate) is int and MIN_VALUE <= candidate <= MAX_VALUE:
            return candidate
    return None


@dataclass
class AdvancedChange:
    path: str
    before: object
    after: object

    def summary(self) -> dict[str, object]:
        return {"path": self.path, "before": self.before, "after": self.after}


@dataclass
class AdvancedEdit:
    plan: dict[str, object]
    changes: list[AdvancedChange]
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
            "field": ADVANCED_RECORD_FIELD,
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


def _set_original(originals: list[tuple[str, object, bool]], path: str, value: object, existed: bool) -> None:
    originals.append((path, value, existed))


def _restore_originals(root: dict[str, Any], originals: Iterable[tuple[str, object, bool]]) -> None:
    for path, value, existed in originals:
        parts = path.split(".")
        current: Any = root
        for part in parts[:-1]:
            current = current[int(part)] if isinstance(current, list) else current[part]
        leaf = parts[-1]
        if isinstance(current, list):
            index = int(leaf)
            if existed:
                current[index] = value
        elif existed:
            current[leaf] = value
        else:
            current.pop(leaf, None)


def prepare_advanced_edit(source: bytes, plan: Mapping[str, object]) -> AdvancedEdit:
    root, version, source = _validated_document(source)
    normalized = normalize_advanced_plan(plan)
    candidate = deepcopy(root)
    catalog = _load_catalog()
    changes: list[AdvancedChange] = []
    originals: list[tuple[str, object, bool]] = []

    for key, path, ids, label in (
        ("materials", MATERIALS_PATH, catalog["material_ids"], "itemData.materials"),
        ("seeds", SEEDS_PATH, catalog["seed_ids"], "itemData.seeds"),
    ):
        requested = normalized[key]
        assert isinstance(requested, dict)
        if not requested:
            continue
        parent_name, map_name = path.split(".")
        parent = candidate.get(parent_name)
        if not isinstance(parent, dict) or not isinstance(parent.get(map_name), dict):
            raise AdvancedFieldMissing(f"No existe {label} como mapa de cantidades.")
        target = parent[map_name]
        if len(target) + len(requested) > MAX_ITEMS + 100:
            raise AdvancedFieldIncompatible(f"{label} tiene demasiados elementos.")
        for item_id, value in requested.items():
            assert isinstance(item_id, str) and type(value) is int
            existed = item_id in target
            before = target.get(item_id)
            if existed and type(before) is not int:
                raise AdvancedFieldIncompatible(
                    f"{label}.{item_id} no es un entero y no se puede sobrescribir."
                )
            if existed and before == value:
                continue
            _set_original(originals, f"{path}.{item_id}", before, existed)
            target[item_id] = value
            changes.append(AdvancedChange(f"{path}.{item_id}", before if existed else None, value))

    season_coin = normalized["season_coin"]
    if season_coin is not None:
        season = candidate.get("seasonData")
        if not isinstance(season, dict) or "coin" not in season:
            raise AdvancedFieldMissing("No existe seasonData.coin en este guardado.")
        before = season["coin"]
        if type(before) is not int:
            raise AdvancedFieldIncompatible("seasonData.coin no es un entero.")
        if before != season_coin:
            _set_original(originals, SEASON_COIN_PATH, before, True)
            season["coin"] = season_coin
            changes.append(AdvancedChange(SEASON_COIN_PATH, before, season_coin))

    if normalized["reborn_card"] is True:
        game = candidate.get("gameData")
        if not isinstance(game, dict) or "rebornCard" not in game:
            raise AdvancedFieldMissing("No existe gameData.rebornCard en este guardado.")
        before = game["rebornCard"]
        if type(before) is not bool:
            raise AdvancedFieldIncompatible("gameData.rebornCard no es booleano.")
        if before is not True:
            _set_original(originals, REBORN_PATH, before, True)
            game["rebornCard"] = True
            changes.append(AdvancedChange(REBORN_PATH, before, True))

    selected_pets = normalized["pets"]
    assert isinstance(selected_pets, list)
    if selected_pets:
        game = candidate.get("gameData")
        if not isinstance(game, dict) or not isinstance(game.get("petUnlock"), dict):
            raise AdvancedFieldMissing("No existe gameData.petUnlock como mapa de desbloqueos.")
        unlocks = game["petUnlock"]
        if len(unlocks) + len(selected_pets) > MAX_ITEMS:
            raise AdvancedFieldIncompatible("gameData.petUnlock tiene demasiados elementos.")
        for pet_id in selected_pets:
            before = unlocks.get(pet_id)
            if pet_id in unlocks and type(before) is not bool:
                raise AdvancedFieldIncompatible(
                    f"gameData.petUnlock.{pet_id} no es booleano y no se puede sobrescribir."
                )
            if before is True:
                continue
            _set_original(originals, f"{PETS_PATH}.{pet_id}", before, pet_id in unlocks)
            unlocks[pet_id] = True
            changes.append(AdvancedChange(f"{PETS_PATH}.{pet_id}", before if pet_id in unlocks else None, True))

    battle_pass = normalized["battle_pass"]
    if isinstance(battle_pass, dict):
        _, records = _bp_records(candidate)
        season_id = battle_pass["season_id"]
        matches = [
            index
            for index, record in enumerate(records)
            if isinstance(_bp_value(record), Mapping) and _bp_value(record).get("seasonID") == season_id
        ]
        if not matches:
            raise AdvancedSeasonMissing(f"No existe un pase con seasonID {season_id}.")
        if len(matches) > 1:
            raise AdvancedSeasonDuplicate(f"Hay más de un pase con seasonID {season_id}.")
        index = matches[0]
        value = _bp_value(records[index])
        assert value is not None
        for key in ("curLevel", "curExp", "freeClaimedLevel", "paidClaimedLevel"):
            if type(value.get(key)) is not int:
                raise AdvancedFieldIncompatible(f"El pase {season_id} no declara {key} como entero.")
        claimed_level = max(value["freeClaimedLevel"], value["paidClaimedLevel"])
        if "cur_level" in battle_pass:
            requested_level = battle_pass["cur_level"]
            assert type(requested_level) is int
            if requested_level < claimed_level:
                raise InvalidAdvancedPlan(
                    f"curLevel no puede ser menor que el progreso reclamado ({claimed_level})."
                )
            if value["curLevel"] != requested_level:
                _set_original(originals, f"{BATTLE_PASS_PATH}.{index}.Value.curLevel", value["curLevel"], True)
                value["curLevel"] = requested_level
                changes.append(
                    AdvancedChange(f"{BATTLE_PASS_PATH}.{index}.Value.curLevel", value["curLevel"], requested_level)
                )
        if "cur_exp" in battle_pass:
            requested_exp = battle_pass["cur_exp"]
            assert type(requested_exp) is int
            if value["curExp"] != requested_exp:
                _set_original(originals, f"{BATTLE_PASS_PATH}.{index}.Value.curExp", value["curExp"], True)
                before_exp = value["curExp"]
                value["curExp"] = requested_exp
                changes.append(
                    AdvancedChange(f"{BATTLE_PASS_PATH}.{index}.Value.curExp", before_exp, requested_exp)
                )
        if "has_buy" in battle_pass:
            requested_buy = battle_pass["has_buy"]
            assert type(requested_buy) is bool
            if requested_buy is False and value["paidClaimedLevel"] > 0:
                raise InvalidAdvancedPlan(
                    "No se puede desactivar hasBuy mientras existan recompensas premium reclamadas."
                )
            if value["hasBuy"] is not requested_buy:
                _set_original(originals, f"{BATTLE_PASS_PATH}.{index}.Value.hasBuy", value["hasBuy"], True)
                value["hasBuy"] = requested_buy
                changes.append(
                    AdvancedChange(f"{BATTLE_PASS_PATH}.{index}.Value.hasBuy", not requested_buy, requested_buy)
                )

    # Corrige los "before" de las rutas del pase usando el valor realmente original.
    root_records = _bp_records(root)[1]
    for change in changes:
        if change.path.startswith(f"{BATTLE_PASS_PATH}."):
            parts = change.path.split(".")
            original_value = _bp_value(root_records[int(parts[2])])
            assert original_value is not None
            change.before = original_value.get(parts[-1])

    changed_fields = tuple(change.path for change in changes)
    if not changes:
        digest = sha256(source).hexdigest()
        return AdvancedEdit(
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
        raise AdvancedVerificationError(f"No se pudo serializar el candidato: {exc}") from exc
    if len(candidate_source) > MAX_INPUT_BYTES:
        raise AdvancedVerificationError("El guardado candidato supera el tamaño permitido.")

    try:
        reconstruct_cloud_save(candidate_source)
        encoding, document = unpack_cloud_save(candidate_source)
        if encoding != "json":
            raise AdvancedVerificationError("El candidato no conserva el formato JSON.")
        reopened_root = parse_json(document)
    except (AggregateFormatError, ValueError) as exc:
        raise AdvancedVerificationError(f"El candidato no se puede volver a abrir: {exc}") from exc
    if not isinstance(reopened_root, dict):
        raise AdvancedVerificationError("El candidato no conserva el objeto raíz.")
    if serialize_aggregate(deepcopy(reopened_root)) != candidate_source:
        raise AdvancedVerificationError("El candidato no es estable al reserializarlo.")

    # Comprueba cada valor solicitado sobre la copia reabierta.
    for item_id, value in normalized["materials"].items():  # type: ignore[union-attr]
        if reopened_root["itemData"]["materials"][item_id] != value:
            raise AdvancedVerificationError(f"No se conservó itemData.materials.{item_id}.")
    for item_id, value in normalized["seeds"].items():  # type: ignore[union-attr]
        if reopened_root["itemData"]["seeds"][item_id] != value:
            raise AdvancedVerificationError(f"No se conservó itemData.seeds.{item_id}.")
    if normalized["season_coin"] is not None and reopened_root["seasonData"]["coin"] != normalized["season_coin"]:
        raise AdvancedVerificationError("No se conservó seasonData.coin.")
    if normalized["reborn_card"] is True and reopened_root["gameData"]["rebornCard"] is not True:
        raise AdvancedVerificationError("No se conservó gameData.rebornCard.")
    for pet_id in normalized["pets"]:  # type: ignore[union-attr]
        if reopened_root["gameData"]["petUnlock"][pet_id] is not True:
            raise AdvancedVerificationError(f"No se conservó gameData.petUnlock.{pet_id}.")

    _restore_originals(reopened_root, originals)
    if serialize_aggregate(reopened_root) != source:
        raise AdvancedVerificationError(
            "La reversión del plan no reproduce el guardado original; hay cambios colaterales."
        )

    binary = binary_diff(source, candidate_source)
    if binary.first_difference is None:
        raise AdvancedVerificationError("El plan no produjo una diferencia binaria verificable.")
    return AdvancedEdit(
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


def require_advanced_write_compatibility(source: bytes, plan: Mapping[str, object], candidate: bytes) -> None:
    try:
        expected = prepare_advanced_edit(source, plan).candidate
    except AdvancedEditError as exc:
        if exc.code == AdvancedVerificationError.code:
            raise
        raise AdvancedEditError(f"El borrador avanzado ya no es compatible: {exc}") from exc
    if expected != candidate:
        raise OutdatedAdvancedDraft("El borrador avanzado no coincide con el guardado actual.")


def _count_value(value: object) -> tuple[int | None, str | None]:
    if type(value) is int and MIN_VALUE <= value <= MAX_VALUE:
        return value, None
    return None, type(value).__name__


def _item_rows(
    root_map: Mapping[str, Any],
    catalog_rows: Mapping[str, dict[str, object]],
    ordered: Iterable[str],
    path: str,
    available: bool = True,
) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for item_id in ordered:
        row = catalog_rows[item_id]
        exists = item_id in root_map
        count, value_type = _count_value(root_map.get(item_id)) if exists else (None, None)
        editable = available and bool(row["editable"]) and (not exists or count is not None)
        reason = row.get("reason")
        if not available:
            reason = f"No existe {path} como mapa de cantidades; no se puede insertar."
        elif exists and count is None:
            reason = "El valor guardado no es un entero; se conserva sin editar."
        result.append({
            "id": item_id,
            "name": row["name"],
            "subcategory": row["subcategory"],
            "plant_id": row.get("plant_id") if isinstance(row.get("plant_id"), str) else None,
            "count": count,
            "value_type": value_type,
            "owned": exists,
            "known": True,
            "editable": editable,
            "insertable": available and bool(row["insertable"]) and not exists,
            "reason": reason,
            "path": f"{path}.{item_id}",
        })
    known = set(ordered)
    for item_id in sorted(key for key in root_map if key not in known):
        count, value_type = _count_value(root_map.get(item_id))
        result.append({
            "id": item_id,
            "name": {"en": None, "es": None},
            "subcategory": None,
            "plant_id": None,
            "count": count,
            "value_type": value_type,
            "owned": True,
            "known": False,
            "editable": False,
            "insertable": False,
            "reason": "Identificador desconocido; se conserva intacto y no se edita.",
            "path": f"{path}.{item_id}",
        })
    return result


def read_advanced_source(source: bytes) -> dict[str, object]:
    root, _, _ = _validated_document(source)
    return read_advanced_snapshot(root)


def read_advanced_snapshot(payload: Mapping[str, Any]) -> dict[str, object]:
    catalog = _load_catalog("snapshot")
    item_data = payload.get("itemData")
    material_map = item_data.get("materials") if isinstance(item_data, dict) else None
    seed_map = item_data.get("seeds") if isinstance(item_data, dict) else None
    material_map = material_map if isinstance(material_map, dict) else {}
    seed_map = seed_map if isinstance(seed_map, dict) else {}
    material_map_available = isinstance(item_data, dict) and isinstance(item_data.get("materials"), dict)
    seed_map_available = isinstance(item_data, dict) and isinstance(item_data.get("seeds"), dict)
    materials = _item_rows(
        material_map, catalog["materials"], catalog["ordered_materials"], MATERIALS_PATH,
        material_map_available,
    )  # type: ignore[arg-type]
    seeds = _item_rows(
        seed_map, catalog["seeds"], catalog["ordered_seeds"], SEEDS_PATH,
        seed_map_available,
    )  # type: ignore[arg-type]

    season = payload.get("seasonData")
    season = season if isinstance(season, dict) else {}
    coin = season.get("coin")
    coin_valid = type(coin) is int and MIN_VALUE <= coin <= MAX_VALUE
    season_coin = {
        "value": coin if coin_valid else None,
        "value_type": None if coin_valid else type(coin).__name__ if "coin" in season else None,
        "available": "coin" in season and coin_valid,
        "path": SEASON_COIN_PATH,
        "min": MIN_VALUE,
        "max": MAX_VALUE,
        "owner_reference": "season_data:coin",
        "note": "Moneda de temporada; no es gema, ficha de pesca ni experiencia del pase.",
    }

    game = payload.get("gameData")
    game = game if isinstance(game, dict) else {}
    reborn = game.get("rebornCard")
    reborn_valid = type(reborn) is bool
    reborn_card = {
        "value": reborn if reborn_valid else None,
        "available": "rebornCard" in game and reborn_valid,
        "path": REBORN_PATH,
        "experimental": False,
        "local_reference": "shared_pref:reborn_card = 1 (entero, por perfil)",
        "remote_representation": "gameData.rebornCard (booleano)",
        "projection": "CoverPlayerPref / CoverPlayerPrefSafely",
        "limitation": REBORN_LIMITATION,
        "evidence_level": "E3",
    }

    try:
        _, records = _bp_records(payload)
    except AdvancedEditError:
        records = []
    bp_rows: list[dict[str, object]] = []
    selected: int | None = None
    for index, record in enumerate(records):
        value = _bp_value(record)
        row: dict[str, object] = {"index": index, "key": record.get("Key") if isinstance(record, dict) else None}
        if value is None:
            row.update({"editable": False, "error": "Registro sin Value válido."})
            bp_rows.append(row)
            continue
        season_id = value.get("seasonID")
        fields = ("curLevel", "curExp", "freeClaimedLevel", "paidClaimedLevel")
        valid = type(season_id) is int and all(type(value.get(key)) is int for key in fields) and type(value.get("hasBuy")) is bool
        row.update({
            "season_id": season_id if type(season_id) is int else None,
            "cur_level": value.get("curLevel"),
            "cur_exp": value.get("curExp"),
            "has_buy": value.get("hasBuy"),
            "free_claimed_level": value.get("freeClaimedLevel"),
            "paid_claimed_level": value.get("paidClaimedLevel"),
            "max_level": _max_level(value),
            "editable": valid,
            "error": None if valid else "El registro no declara todos los campos esperados.",
        })
        if valid:
            selected = season_id if selected is None else max(selected, season_id)
        bp_rows.append(row)
    active = season.get("seasonID") if type(season.get("seasonID")) is int else None
    battle_pass = {
        "records": bp_rows,
        "selected_season_id": selected,
        "active_season_id": active,
        "active_matches_selected": active == selected if active is not None else None,
        "note": "Se selecciona el seasonID más alto por defecto; solo se editan registros existentes.",
    }

    pet_catalog = load_pet_catalog()
    pets, pet_skins, pet_food = _pet_snapshot(
        game, material_map, materials, pet_catalog
    )
    pet_progression = pet_progression_snapshot(payload)

    return {
        "materials": materials,
        "seeds": seeds,
        "season_coin": season_coin,
        "reborn_card": reborn_card,
        "battle_pass": battle_pass,
        "pets": pets,
        "pet_skins": pet_skins,
        "pet_food": pet_food,
        "pet_progression": pet_progression,
        "hero_levels": hero_levels_snapshot(payload),
        "blueprints": blueprints_snapshot(payload),
        "decorations": decorations_snapshot(payload),
        "pet_policy": {
            "field": "pets",
            "experimental": False,
            "evidence_level": "E3",
            "path": PETS_PATH,
            "skin_note": (
                "No se encontró un mapa de bloqueo de skins separado. Las variantes Cat1..Cat7, "
                "Dog1..Dog3, Pig1 y Rabbit1 se desbloquean mediante gameData.petUnlock.<variante>; "
                "seleccionar una variante incluye su mascota base."
            ),
            "food_note": (
                "Los alimentos material_grain y material_battery comparten el escritor de "
                "itemData.materials; no se crea un escritor paralelo."
            ),
            "progression_note": (
                "La intimidad se puede subir solo cuando existe un máximo observado para esa "
                "mascota. Serenade y EscapeMonkey permanecen en solo lectura porque "
                "no se recuperó su límite; FishChipKing tiene máximo observado 240."
            ),
        },
        "policy": {
            "field": ADVANCED_RECORD_FIELD,
            "experimental": True,
            "evidence_level": "E2",
            "min": MIN_VALUE,
            "max": MAX_VALUE,
            "max_note": "Límite estructural int32; no se ha confirmado un tope del juego.",
            "material_fish_note": "material_fish se excluye por ser espejo de gameData.fishChip.",
            "confirmed_functions": ["materials", "seeds", "season_coin", "reborn_card", "pets", "pet_food", "pet_skins"],
            "experimental_functions": ["battle_pass"],
        },
    }


def _pet_snapshot(
    game: Mapping[str, Any],
    material_map: Mapping[str, Any],
    material_rows: list[dict[str, object]],
    catalog: Mapping[str, object],
) -> tuple[list[dict[str, object]], list[dict[str, object]], list[dict[str, object]]]:
    unlocks = game.get("petUnlock") if isinstance(game, dict) else None
    available = isinstance(unlocks, dict)
    unlocks = unlocks if isinstance(unlocks, dict) else {}
    pet_rows_by_id = catalog["pets"]
    skin_rows_by_id = catalog["pet_skins"]
    assert isinstance(pet_rows_by_id, dict) and isinstance(skin_rows_by_id, dict)
    skins_by_pet: dict[str, list[str]] = {}
    for skin_id, skin in skin_rows_by_id.items():
        skins_by_pet.setdefault(str(skin["base_pet"]), []).append(skin_id)  # type: ignore[index]
    pets: list[dict[str, object]] = []
    for pet_id in catalog["ordered_pets"]:  # type: ignore[union-attr]
        row = pet_rows_by_id[pet_id]
        exists = pet_id in unlocks
        value = unlocks.get(pet_id)
        valid = exists and type(value) is bool
        pets.append({
            "id": pet_id,
            "numeric_id": row["numeric_id"],
            "name": row["name"],
            "unlocked": True if valid and value is True else False if valid else None,
            "present": exists,
            "value_type": type(value).__name__ if exists else None,
            "editable": available and (not exists or valid),
            "insertable": available and not exists,
            "path": f"{PETS_PATH}.{pet_id}",
            "skins": sorted(skins_by_pet.get(pet_id, [])),
            "reason": None if available else f"No existe {PETS_PATH} como mapa booleano.",
        })
    pet_skins: list[dict[str, object]] = []
    for skin_id in catalog["ordered_skins"]:  # type: ignore[union-attr]
        row = skin_rows_by_id[skin_id]
        exists = skin_id in unlocks
        value = unlocks.get(skin_id)
        valid = exists and type(value) is bool
        base = str(row["base_pet"])  # type: ignore[index]
        base_value = unlocks.get(base)
        pet_skins.append({
            "id": skin_id,
            "pet_code": row["pet_code"],
            "base_pet": base,
            "skin_index": row["skin_index"],
            "name": row["name"],
            "unlocked": True if valid and value is True else False if valid else None,
            "present": exists,
            "value_type": type(value).__name__ if exists else None,
            "editable": available and (not exists or valid),
            "insertable": available and not exists,
            "path": f"{PETS_PATH}.{skin_id}",
            "base_unlocked": True if base_value is True else False if type(base_value) is bool else None,
            "dependency_note": (
                "Seleccionar esta variante también desbloquea su mascota base si está pendiente."
            ),
        })
    food_rows = []
    for row in material_rows:
        if row.get("id") in PET_FOOD_IDS:
            food_rows.append({
                "id": row["id"],
                "name": row["name"],
                "count": row["count"],
                "value_type": row["value_type"],
                "owned": row["owned"],
                "editable": row["editable"],
                "insertable": row["insertable"],
                "path": row["path"],
                "field": "itemData.materials",
                "population": "itemData.materials",
                "reason": row.get("reason"),
            })
    return pets, pet_skins, food_rows

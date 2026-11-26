"""Composición atómica de los editores existentes en un único candidato.

La Fase 8.0 conserva cada escritor granular y los encadena sobre los mismos
bytes. Así una edición rápida que cambia gemas, desbloquea personajes y ajusta
materiales produce un solo respaldo, una sola subida y una sola verificación,
sin volver a descargar ni reconstruir la partida entre pasos.

El plan normalizado es determinista y se guarda en el respaldo para poder
reproducir exactamente el candidato antes de confirmarlo o restaurarlo.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
from typing import Mapping

from ..cloud_save import CloudSaveError
from .advanced_editor import (
    AdvancedEdit,
    normalize_advanced_plan,
    prepare_advanced_edit,
)
from .blueprint_editor import (
    BlueprintEdit,
    normalize_blueprint_plan,
    prepare_blueprint_edit,
)
from .decoration_editor import (
    DecorationEdit,
    normalize_decoration_plan,
    prepare_decoration_edit,
)
from .character_editor import (
    CharacterEdit,
    prepare_character_unlock_edit,
)
from .hero_level_editor import (
    HeroLevelEdit,
    normalize_hero_level_plan,
    prepare_hero_level_edit,
)
from .pet_affinity_editor import (
    PetAffinityEdit,
    normalize_pet_affinity_plan,
    prepare_pet_affinity_edit,
)
from .fish_chip_editor import (
    FishChipEdit,
    prepare_fish_chip_edit,
)
from .fish_progress_editor import (
    FishProgressEdit,
    prepare_fish_progress_edit,
)
from .gems_editor import GemsEdit, prepare_gems_edit
from .lab import BinaryDiff, binary_diff
from .kill_effect_editor import (
    KillEffectEdit,
    prepare_kill_effect_unlock_edit,
)
from .skill_editor import SkillEdit, prepare_skill_unlock_edit
from .skin_editor import SkinEdit, prepare_skin_unlock_edit
from .weapon_skin_editor import (
    WeaponSkinEdit,
    prepare_weapon_skin_unlock_edit,
)

UNIFIED_RECORD_FIELD = "unified"
MAX_CHARACTERS = 42
MAX_SKILLS = 105
MAX_SKINS = 802
MAX_WEAPON_SKINS = 192
MAX_KILL_EFFECTS = 9

# Fuente única de las categorías que puede producir el editor unificado. El
# almacén de respaldos valida con este mismo conjunto las categorías de sus
# registros para que ambos lados no vuelvan a desincronizarse.
UNIFIED_CATEGORY_KEYS = frozenset(
    {
        "gems",
        "fish_chip",
        "fish_progress",
        "characters",
        "skills",
        "skins",
        "weapon_skins",
        "kill_effects",
        "advanced",
        "hero_levels",
        "pet_affinity",
        "blueprints",
        "decorations",
    }
)

# Categorías incorporadas después de la Fase 8.0. Los planes históricos pueden
# no declararlas; el lector de respaldos solo las completa al leer un registro.
UNIFIED_OPTIONAL_DEFAULTS: dict[str, object] = {
    "hero_levels": None,
    "pet_affinity": None,
    "blueprints": None,
    "decorations": None,
    "weapon_skins": [],
    "kill_effects": [],
}
UNIFIED_OPTIONAL_CATEGORY_KEYS = frozenset(UNIFIED_OPTIONAL_DEFAULTS)


class UnifiedEditError(CloudSaveError):
    code = "unified_edit"


class InvalidUnifiedPlan(UnifiedEditError):
    code = "invalid_unified_plan"


class UnifiedOverlap(UnifiedEditError):
    code = "unified_overlap"


class UnifiedVerificationError(UnifiedEditError):
    code = "unified_verification_failed"


def _optional_int(value: object, label: str) -> int | None:
    if value is None:
        return None
    if type(value) is not int:
        raise InvalidUnifiedPlan(f"{label} debe ser un entero o null.")
    return value


def _refs(value: object, label: str, maximum: int) -> list[dict[str, object]]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise InvalidUnifiedPlan(f"{label} debe ser una lista.")
    if len(value) > maximum:
        raise InvalidUnifiedPlan(f"{label} supera el máximo de {maximum} elementos.")
    result: list[dict[str, object]] = []
    seen: set[tuple[str, int]] = set()
    for item in value:
        if not isinstance(item, Mapping):
            raise InvalidUnifiedPlan(f"{label} contiene una referencia inválida.")
        code = item.get("code")
        index = item.get("index")
        if not isinstance(code, str) or not code or type(index) is not int:
            raise InvalidUnifiedPlan(f"{label} contiene una referencia inválida.")
        key = (code, index)
        if key in seen:
            raise InvalidUnifiedPlan(f"{label} repite la referencia {code}:{index}.")
        seen.add(key)
        result.append({"code": code, "index": index})
    return sorted(result, key=lambda ref: (str(ref["code"]), int(ref["index"])))  # type: ignore[arg-type]


def _characters(value: object) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or len(value) > MAX_CHARACTERS:
        raise InvalidUnifiedPlan("characters debe ser una lista dentro del máximo admitido.")
    result: list[str] = []
    for code in value:
        if not isinstance(code, str) or not code:
            raise InvalidUnifiedPlan("characters contiene un código inválido.")
        if code in result:
            raise InvalidUnifiedPlan(f"characters repite el código {code}.")
        result.append(code)
    return result


def _weapon_skins(value: object) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or len(value) > MAX_WEAPON_SKINS:
        raise InvalidUnifiedPlan(
            "weapon_skins debe ser una lista dentro del máximo admitido."
        )
    result: list[str] = []
    for skin_id in value:
        if not isinstance(skin_id, str) or not skin_id:
            raise InvalidUnifiedPlan("weapon_skins contiene un identificador inválido.")
        if skin_id in result:
            raise InvalidUnifiedPlan(f"weapon_skins repite la skin {skin_id}.")
        result.append(skin_id)
    return result


def _kill_effects(value: object) -> list[int]:
    if value is None:
        return []
    if not isinstance(value, list) or len(value) > MAX_KILL_EFFECTS:
        raise InvalidUnifiedPlan(
            "kill_effects debe ser una lista dentro del máximo admitido."
        )
    result: list[int] = []
    for effect_id in value:
        if isinstance(effect_id, bool) or type(effect_id) is not int:
            raise InvalidUnifiedPlan("kill_effects contiene un identificador inválido.")
        if effect_id in result:
            raise InvalidUnifiedPlan(f"kill_effects repite el efecto {effect_id}.")
        result.append(effect_id)
    return result


def _advanced(value: object) -> dict[str, object] | None:
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise InvalidUnifiedPlan("advanced debe ser un objeto JSON o null.")
    # Un formulario vacío se trata como ausente, no como un plan sin cambios.
    meaningful = (
        bool(value.get("materials"))
        or bool(value.get("seeds"))
        or value.get("season_coin") is not None
        or value.get("reborn_card") is True
        or value.get("battle_pass") is not None
        or bool(value.get("pets"))
        or bool(value.get("pet_food"))
    )
    if not meaningful:
        return None
    return normalize_advanced_plan(value)


def _code_map(
    value: object, label: str, id_key: str, value_key: str, normalizer
) -> dict[str, object] | None:
    if value is None:
        return None
    if isinstance(value, Mapping):
        entries = value
    elif isinstance(value, list):
        entries = {}
        for item in value:
            if not isinstance(item, Mapping):
                raise InvalidUnifiedPlan(f"{label} contiene un elemento inválido.")
            item_id = item.get(id_key)
            item_value = item.get(value_key)
            if not isinstance(item_id, str) or not item_id:
                raise InvalidUnifiedPlan(f"{label} contiene un identificador inválido.")
            if item_id in entries:
                raise InvalidUnifiedPlan(f"{label} repite el identificador {item_id}.")
            entries[item_id] = item_value
    else:
        raise InvalidUnifiedPlan(f"{label} debe ser un objeto o una lista de cambios.")
    if not entries:
        return None
    try:
        return normalizer(entries)
    except CloudSaveError as exc:
        raise InvalidUnifiedPlan(str(exc)) from exc


def _decorations(value: object) -> dict[str, object] | None:
    if value is None:
        return None
    if isinstance(value, Mapping):
        if not value.get("objects") and not value.get("levels"):
            return None
    try:
        return normalize_decoration_plan(value)
    except CloudSaveError as exc:
        raise InvalidUnifiedPlan(str(exc)) from exc


def _blueprints(value: object) -> dict[str, str] | None:
    if value is None:
        return None
    if isinstance(value, Mapping) and not value:
        return None
    if isinstance(value, list) and not value:
        return None
    try:
        return normalize_blueprint_plan(value)
    except CloudSaveError as exc:
        raise InvalidUnifiedPlan(str(exc)) from exc


def normalize_unified_plan(raw: Mapping[str, object]) -> dict[str, object]:
    """Valida y ordena el plan compuesto que se guarda con el respaldo."""
    if not isinstance(raw, Mapping):
        raise InvalidUnifiedPlan("El plan debe ser un objeto JSON.")
    unknown = set(raw) - UNIFIED_CATEGORY_KEYS
    if unknown:
        raise InvalidUnifiedPlan(f"El plan contiene claves no autorizadas: {sorted(unknown)}.")
    plan = {
        "gems": _optional_int(raw.get("gems"), "gems"),
        "fish_chip": _optional_int(raw.get("fish_chip"), "fish_chip"),
        "fish_progress": _optional_int(raw.get("fish_progress"), "fish_progress"),
        "characters": _characters(raw.get("characters")),
        "skills": _refs(raw.get("skills"), "skills", MAX_SKILLS),
        "skins": _refs(raw.get("skins"), "skins", MAX_SKINS),
        "weapon_skins": _weapon_skins(raw.get("weapon_skins")),
        "kill_effects": _kill_effects(raw.get("kill_effects")),
        "advanced": _advanced(raw.get("advanced")),
        "hero_levels": _code_map(
            raw.get("hero_levels"), "hero_levels", "code", "level", normalize_hero_level_plan
        ),
        "pet_affinity": _code_map(
            raw.get("pet_affinity"), "pet_affinity", "code", "value", normalize_pet_affinity_plan
        ),
        "blueprints": _blueprints(raw.get("blueprints")),
        "decorations": _decorations(raw.get("decorations")),
    }
    if not any(
        (
            plan["gems"] is not None,
            plan["fish_chip"] is not None,
            plan["fish_progress"] is not None,
            plan["characters"],
            plan["skills"],
            plan["skins"],
            plan["weapon_skins"],
            plan["kill_effects"],
            plan["advanced"],
            plan["hero_levels"],
            plan["pet_affinity"],
            plan["blueprints"],
            plan["decorations"],
        )
    ):
        raise InvalidUnifiedPlan("El plan no contiene ninguna edición.")
    return plan


@dataclass(frozen=True)
class UnifiedCategory:
    key: str
    label: str
    changes: int
    detail: dict[str, object]

    def summary(self) -> dict[str, object]:
        return {
            "key": self.key,
            "label": self.label,
            "changes": self.changes,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class UnifiedEdit:
    plan: dict[str, object]
    categories: tuple[UnifiedCategory, ...]
    changed: bool
    original: bytes = field(repr=False)
    candidate: bytes = field(repr=False)
    original_sha256: str = field(repr=False)
    candidate_sha256: str = field(repr=False)
    binary: BinaryDiff = field(repr=False)
    changed_fields: tuple[str, ...] = ()
    steps: tuple[str, ...] = ()

    @property
    def original_size(self) -> int:
        return len(self.original)

    @property
    def candidate_size(self) -> int:
        return len(self.candidate)

    @property
    def change_count(self) -> int:
        return sum(category.changes for category in self.categories)

    def summary(self) -> dict[str, object]:
        return {
            "field": UNIFIED_RECORD_FIELD,
            "plan": self.plan,
            "categories": [category.summary() for category in self.categories],
            "steps": list(self.steps),
            "change_count": self.change_count,
            "changed": self.changed,
            "original_size": self.original_size,
            "candidate_size": self.candidate_size,
            "original_sha256": self.original_sha256,
            "candidate_sha256": self.candidate_sha256,
            "serialzed_version": 0,
            "binary": self.binary.as_dict(),
            "changed_fields": list(self.changed_fields),
        }


def _category(
    key: str,
    label: str,
    edits: list[
        GemsEdit
        | FishChipEdit
        | FishProgressEdit
        | CharacterEdit
        | SkillEdit
        | SkinEdit
        | WeaponSkinEdit
        | KillEffectEdit
        | AdvancedEdit
        | HeroLevelEdit
        | PetAffinityEdit
        | BlueprintEdit
        | DecorationEdit
    ],
) -> UnifiedCategory:
    edit = edits[0]
    if isinstance(edit, GemsEdit):
        detail = {
            "original": edit.original_gems,
            "new": edit.new_gems,
            "kind": "replace",
        }
    elif isinstance(edit, FishChipEdit):
        detail = {
            "original": edit.original_fish_chip,
            "new": edit.new_fish_chip,
            "material_fish_original": edit.original_material_fish,
            "material_fish_new": edit.new_material_fish,
            "kind": "replace",
        }
    elif isinstance(edit, FishProgressEdit):
        detail = {
            "original": edit.original_cumulative_fish_count,
            "new": edit.new_cumulative_fish_count,
            "kind": "replace",
        }
    elif isinstance(edit, CharacterEdit):
        detail = {
            "original": len(edit.original_unlocked),
            "new": len(edit.new_unlocked),
            "newly_unlocked": list(edit.newly_unlocked),
            "kind": "unlock",
        }
    elif isinstance(edit, SkillEdit):
        detail = {
            "original": len(edit.original_unlocked),
            "new": len(edit.new_unlocked),
            "newly_unlocked": [ref.as_dict() for ref in edit.newly_unlocked],
            "kind": "unlock",
        }
    elif isinstance(edit, SkinEdit):
        detail = {
            "original": len(edit.original_unlocked),
            "new": len(edit.new_unlocked),
            "newly_unlocked": [ref.as_dict() for ref in edit.newly_unlocked],
            "kind": "unlock",
        }
    elif isinstance(edit, WeaponSkinEdit):
        detail = {
            "original": len(edit.original_unlocked),
            "new": len(edit.new_unlocked),
            "newly_unlocked": list(edit.newly_unlocked),
            "created_weapons": list(edit.created_weapons),
            "kind": "unlock",
        }
    elif isinstance(edit, KillEffectEdit):
        detail = {
            "original": len(edit.original_unlocked),
            "new": len(edit.new_unlocked),
            "newly_unlocked": list(edit.newly_unlocked),
            "kind": "unlock",
        }
    else:
        detail = {
            "original": 0,
            "new": len(edit.changes),
            "changes": [change.summary() for change in edit.changes],
            "kind": "explicit",
        }
    return UnifiedCategory(key=key, label=label, changes=len(edit.changed_fields), detail=detail)


def prepare_unified_edit(source: bytes, raw_plan: Mapping[str, object]) -> UnifiedEdit:
    """Aplica los escritores existentes en orden determinista sobre los mismos bytes."""
    plan = normalize_unified_plan(raw_plan)
    current = bytes(source)
    changed_fields: list[str] = []
    categories: list[UnifiedCategory] = []
    steps: list[str] = []

    def apply(key: str, label: str, editor) -> None:
        nonlocal current
        edit = editor(current)
        if edit.original_sha256 != sha256(current).hexdigest():
            raise UnifiedVerificationError("Un paso no partió del candidato anterior.")
        overlap = set(edit.changed_fields) & set(changed_fields)
        if overlap:
            raise UnifiedOverlap(
                "Dos operaciones intentan cambiar el mismo campo: " + ", ".join(sorted(overlap)) + "."
            )
        category = _category(key, label, [edit])
        if category.changes:
            categories.append(category)
            changed_fields.extend(edit.changed_fields)
            steps.append(key)
        current = edit.candidate

    if plan["gems"] is not None:
        apply("gems", "Gemas", lambda value: prepare_gems_edit(value, plan["gems"]))
    if plan["fish_chip"] is not None:
        apply("fish_chip", "Fichas de pesca", lambda value: prepare_fish_chip_edit(value, plan["fish_chip"]))
    if plan["fish_progress"] is not None:
        apply(
            "fish_progress",
            "Recompensas de pesca",
            lambda value: prepare_fish_progress_edit(value, plan["fish_progress"]),
        )
    if plan["characters"]:
        apply(
            "characters",
            "Personajes",
            lambda value: prepare_character_unlock_edit(value, plan["characters"]),
        )
    if plan["skills"]:
        apply("skills", "Habilidades", lambda value: prepare_skill_unlock_edit(value, plan["skills"]))
    if plan["skins"]:
        apply("skins", "Skins", lambda value: prepare_skin_unlock_edit(value, plan["skins"]))
    if plan["weapon_skins"]:
        apply(
            "weapon_skins",
            "Skins de arma",
            lambda value: prepare_weapon_skin_unlock_edit(value, plan["weapon_skins"]),
        )
    if plan["kill_effects"]:
        apply(
            "kill_effects",
            "Efectos de eliminación",
            lambda value: prepare_kill_effect_unlock_edit(value, plan["kill_effects"]),
        )
    if plan["advanced"] is not None:
        apply("advanced", "Materiales y progreso", lambda value: prepare_advanced_edit(value, plan["advanced"]))
    if plan["hero_levels"] is not None:
        apply(
            "hero_levels",
            "Niveles de personaje",
            lambda value: prepare_hero_level_edit(value, plan["hero_levels"]),
        )
    if plan["pet_affinity"] is not None:
        apply(
            "pet_affinity",
            "Afinidad de mascotas",
            lambda value: prepare_pet_affinity_edit(value, plan["pet_affinity"]),
        )
    if plan["blueprints"] is not None:
        apply(
            "blueprints",
            "Planos",
            lambda value: prepare_blueprint_edit(value, plan["blueprints"]),
        )
    if plan["decorations"] is not None:
        apply(
            "decorations",
            "Decoraciones",
            lambda value: prepare_decoration_edit(value, plan["decorations"]),
        )

    candidate = current
    return UnifiedEdit(
        plan=plan,
        categories=tuple(categories),
        changed=candidate != source,
        original=bytes(source),
        candidate=candidate,
        original_sha256=sha256(source).hexdigest(),
        candidate_sha256=sha256(candidate).hexdigest(),
        binary=binary_diff(source, candidate),
        changed_fields=tuple(changed_fields),
        steps=tuple(steps),
    )


def require_unified_write_compatibility(
    original: bytes, plan: Mapping[str, object], candidate: bytes
) -> None:
    """Rechaza un candidato que no se reproduce exactamente desde el plan."""
    try:
        current = prepare_unified_edit(original, plan)
    except CloudSaveError as exc:
        raise UnifiedVerificationError(
            "El candidato del respaldo no es reproducible desde su plan."
        ) from exc
    if current.candidate != candidate:
        raise UnifiedVerificationError(
            "El candidato del respaldo no coincide con la composición de su plan."
        )
"""Editor conservador de niveles permanentes de personaje.

``gameData.heroLevel`` es un mapa ``código -> entero``. La semántica del campo
está respaldada por una mejora legítima del Caballero (0 -> 1). El máximo
documentado del sistema clásico de mejoras es 7; el nivel 8 perteneció a un
sistema retirado y no se habilita. No se infiere un máximo distinto por
personaje ni se modifica ``heroUnlock`` de forma implícita.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from hashlib import sha256
from typing import Any, Mapping

from ..catalogs import load_character_catalog
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

HERO_LEVEL_PATH = "gameData.heroLevel"
HERO_UNLOCK_PATH = "gameData.heroUnlock"
HERO_LEVEL_MIN = 0
HERO_LEVEL_MAX = 7
MAX_CHARACTERS = 42

HERO_LEVEL_LIMITATION = (
    "El máximo 7 corresponde al sistema clásico documentado de siete mejoras "
    "(500/1000/1500/2000/2500/5000/8000 gemas). La configuración CharactersLevelUpData "
    "declara un MaxLevel por personaje, pero sus valores no se recuperaron; por eso no se "
    "ofrecen máximos distintos ni el nivel 8. La eficacia del escritor aún no se validó en el juego."
)


class HeroLevelEditError(CloudSaveError):
    code = "hero_level_edit"


class InvalidHeroLevelPlan(HeroLevelEditError):
    code = "hero_level_plan_invalid"


class UnsupportedHeroLevelSerialization(HeroLevelEditError):
    code = "hero_level_unsupported_serialization"


class HeroLevelFieldMissing(HeroLevelEditError):
    code = "hero_level_field_missing"


class HeroLevelFieldIncompatible(HeroLevelEditError):
    code = "hero_level_field_incompatible"


class HeroLevelCatalogMissing(HeroLevelEditError):
    code = "hero_level_catalog_missing"


class HeroLevelVerificationError(HeroLevelEditError):
    code = "hero_level_verification"


class OutdatedHeroLevelDraft(HeroLevelEditError):
    code = "hero_level_outdated"


def _validated_document(source: bytes) -> tuple[JsonObject, int, bytes]:
    try:
        raw = source.encode("utf-8") if isinstance(source, str) else bytes(source)
    except (UnicodeEncodeError, TypeError):
        raise UnsupportedHeroLevelSerialization("El guardado no es UTF-8 válido.") from None
    if not raw or len(raw) > MAX_INPUT_BYTES:
        raise UnsupportedHeroLevelSerialization("El tamaño del guardado no es válido.")
    try:
        reconstruct_cloud_save(raw)
        encoding, document = unpack_cloud_save(raw)
    except AggregateFormatError as exc:
        raise UnsupportedHeroLevelSerialization(str(exc)) from exc
    if encoding != "json":
        raise UnsupportedHeroLevelSerialization("El guardado no usa el formato JSON esperado.")
    try:
        root = parse_json(document)
    except (ValueError, RecursionError) as exc:
        raise UnsupportedHeroLevelSerialization("El guardado no contiene JSON válido.") from exc
    if not isinstance(root, dict):
        raise UnsupportedHeroLevelSerialization("El guardado no contiene un objeto raíz.")
    if not isinstance(root.get("serialzedVersion"), int):
        raise UnsupportedHeroLevelSerialization("El guardado no declara serialzedVersion.")
    try:
        serialized = serialize_aggregate(root)
    except (TypeError, ValueError) as exc:
        raise UnsupportedHeroLevelSerialization(f"No se pudo serializar el guardado: {exc}") from exc
    if serialized != raw:
        raise UnsupportedHeroLevelSerialization(
            "La serialización canónica no coincide con el guardado descargado."
        )
    return root, root["serialzedVersion"], raw


def _catalog() -> dict[str, object]:
    catalog = load_character_catalog()
    if not catalog.get("available"):
        raise HeroLevelCatalogMissing("El catálogo de personajes no está disponible.")
    return catalog


def _character_name(catalog: Mapping[str, object], code: str) -> str:
    characters = catalog.get("characters")
    entry = characters.get(code) if isinstance(characters, dict) else None
    skins = entry.get("skins") if isinstance(entry, dict) else None
    if isinstance(skins, list):
        for skin in skins:
            if isinstance(skin, dict) and isinstance(skin.get("name"), str) and skin["name"]:
                return skin["name"]
    return code


def normalize_hero_level_plan(raw: object) -> dict[str, int]:
    """Valida ``código -> nivel`` sin aceptar códigos ni valores especulativos."""
    if not isinstance(raw, Mapping):
        raise InvalidHeroLevelPlan("hero_levels debe ser un mapa de código a nivel.")
    if len(raw) > MAX_CHARACTERS:
        raise InvalidHeroLevelPlan(f"hero_levels supera el máximo de {MAX_CHARACTERS} personajes.")
    catalog = _catalog()
    codes = catalog["codes"]
    assert isinstance(codes, list)
    allowed = set(codes)
    result: dict[str, int] = {}
    for code, value in raw.items():
        if not isinstance(code, str) or code not in allowed:
            raise InvalidHeroLevelPlan(f"{code!r} no pertenece al catálogo de personajes 8.8.0.")
        if type(value) is not int or not HERO_LEVEL_MIN <= value <= HERO_LEVEL_MAX:
            raise InvalidHeroLevelPlan(
                f"{code} debe tener un nivel entero entre {HERO_LEVEL_MIN} y {HERO_LEVEL_MAX}."
            )
        result[code] = value
    if not result:
        raise InvalidHeroLevelPlan("hero_levels no contiene ningún cambio.")
    return dict(sorted(result.items()))


@dataclass
class HeroLevelChange:
    path: str
    before: object
    after: object

    def summary(self) -> dict[str, object]:
        return {"path": self.path, "before": self.before, "after": self.after}


@dataclass
class HeroLevelEdit:
    plan: dict[str, int]
    changes: list[HeroLevelChange]
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
            "field": "hero_levels",
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


def _level_map(root: Mapping[str, Any]) -> dict[str, Any]:
    game = root.get("gameData")
    if not isinstance(game, dict) or not isinstance(game.get("heroLevel"), dict):
        raise HeroLevelFieldMissing("No existe gameData.heroLevel como mapa de niveles.")
    return game["heroLevel"]


def hero_levels_snapshot(payload: Mapping[str, Any]) -> dict[str, object]:
    catalog = _catalog()
    game = payload.get("gameData")
    game = game if isinstance(game, dict) else {}
    levels = game.get("heroLevel")
    levels_available = isinstance(levels, dict)
    levels = levels if isinstance(levels, dict) else {}
    unlocks = game.get("heroUnlock")
    unlocks = unlocks if isinstance(unlocks, dict) else {}
    codes = catalog["codes"]
    assert isinstance(codes, list)
    entries: list[dict[str, object]] = []
    for code in codes:
        present = code in levels
        value = levels.get(code)
        valid = present and type(value) is int and HERO_LEVEL_MIN <= value <= HERO_LEVEL_MAX
        unlocked = unlocks.get(code)
        entries.append(
            {
                "id": code,
                "name": _character_name(catalog, code),
                "level": value if valid else None,
                "value_type": None if valid else type(value).__name__ if present else None,
                "present": present,
                "editable": levels_available and valid,
                "unlocked": unlocked if type(unlocked) is bool else None,
                "path": f"{HERO_LEVEL_PATH}.{code}",
                "reason": (
                    None
                    if valid
                    else "El personaje no tiene un nivel entero dentro del intervalo documentado."
                ),
            }
        )
    return {
        "available": levels_available,
        "path": HERO_LEVEL_PATH,
        "min": HERO_LEVEL_MIN,
        "max": HERO_LEVEL_MAX,
        "max_note": HERO_LEVEL_LIMITATION,
        "experimental": True,
        "evidence_level": "E3",
        "entries": entries,
        "note": (
            "Nivel permanente del personaje. Editar el nivel no desbloquea al personaje; "
            "el desbloqueo puede combinarse en el mismo lote."
        ),
    }


def read_hero_levels(source: bytes) -> dict[str, object]:
    root, _, _ = _validated_document(source)
    return hero_levels_snapshot(root)


def prepare_hero_level_edit(source: bytes, plan: object) -> HeroLevelEdit:
    root, version, source = _validated_document(source)
    normalized = normalize_hero_level_plan(plan)
    candidate = deepcopy(root)
    target = _level_map(candidate)
    changes: list[HeroLevelChange] = []
    originals: list[tuple[str, object]] = []

    for code, requested in normalized.items():
        if code not in target:
            raise HeroLevelFieldIncompatible(
                f"gameData.heroLevel no contiene la clave {code}; no se insertan niveles ausentes."
            )
        before = target[code]
        if type(before) is not int:
            raise HeroLevelFieldIncompatible(
                f"gameData.heroLevel.{code} no es un entero y no se puede sobrescribir."
            )
        if not HERO_LEVEL_MIN <= before <= HERO_LEVEL_MAX:
            raise HeroLevelFieldIncompatible(
                f"gameData.heroLevel.{code} está fuera del intervalo documentado y queda en solo lectura."
            )
        if before == requested:
            continue
        if requested < before:
            raise InvalidHeroLevelPlan(
                f"No se reduce gameData.heroLevel.{code} de {before} a {requested}."
            )
        originals.append((code, before))
        target[code] = requested
        changes.append(HeroLevelChange(f"{HERO_LEVEL_PATH}.{code}", before, requested))

    changed_fields = tuple(change.path for change in changes)
    if not changes:
        digest = sha256(source).hexdigest()
        return HeroLevelEdit(
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
        raise HeroLevelVerificationError(f"No se pudo serializar el candidato: {exc}") from exc
    if len(candidate_source) > MAX_INPUT_BYTES:
        raise HeroLevelVerificationError("El guardado candidato supera el tamaño permitido.")

    try:
        reconstruct_cloud_save(candidate_source)
        encoding, document = unpack_cloud_save(candidate_source)
        if encoding != "json":
            raise HeroLevelVerificationError("El candidato no conserva el formato JSON.")
        reopened = parse_json(document)
    except (AggregateFormatError, ValueError) as exc:
        raise HeroLevelVerificationError(f"El candidato no se puede volver a abrir: {exc}") from exc
    if not isinstance(reopened, dict):
        raise HeroLevelVerificationError("El candidato no conserva el objeto raíz.")
    if serialize_aggregate(deepcopy(reopened)) != candidate_source:
        raise HeroLevelVerificationError("El candidato no es estable al reserializarlo.")

    reopened_levels = _level_map(reopened)
    for code, value in normalized.items():
        if reopened_levels.get(code) != value:
            raise HeroLevelVerificationError(f"No se conservó gameData.heroLevel.{code}.")

    for code, before in originals:
        reopened_levels[code] = before
    if serialize_aggregate(reopened) != source:
        raise HeroLevelVerificationError(
            "La reversión del plan no reproduce el guardado original; hay cambios colaterales."
        )

    binary = binary_diff(source, candidate_source)
    if binary.first_difference is None:
        raise HeroLevelVerificationError("El plan no produjo una diferencia binaria verificable.")
    return HeroLevelEdit(
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


def require_hero_level_write_compatibility(
    source: bytes, plan: object, candidate: bytes
) -> None:
    try:
        expected = prepare_hero_level_edit(source, plan).candidate
    except HeroLevelEditError as exc:
        if exc.code == HeroLevelVerificationError.code:
            raise
        raise HeroLevelEditError(f"El borrador de niveles ya no es compatible: {exc}") from exc
    if expected != candidate:
        raise OutdatedHeroLevelDraft("El borrador de niveles no coincide con el guardado actual.")
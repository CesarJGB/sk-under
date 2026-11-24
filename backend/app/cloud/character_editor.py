"""Desbloqueo determinista de personajes en ``gameData.heroUnlock``.

La Fase 6.16 reutiliza la evidencia de estructura de las fases anteriores. En
las copias reales de 8.8.0 el mapa ``heroUnlock`` contiene los 42 códigos del
catálogo y solo los personajes disponibles aparecen como ``true``. Los
personajes bloqueados conservan ``heroLevel``, ``heroSkill``,
``heroSkillUnlock`` y ``skinLock`` con la misma forma que los disponibles, por
lo que esta operación solo cambia las entradas seleccionadas de ``heroUnlock``.

No se modifican niveles, habilidades, skins, materiales ni otros campos. La
evidencia de persistencia y efecto dentro del cliente todavía no se ha validado
en un dispositivo físico para esta operación; por eso la función se publica
como experimental y conserva el flujo de respaldo, confirmación y restauración.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from hashlib import sha256

from ..catalogs import load_character_catalog
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

CHARACTER_FIELD_ID = "heroUnlock"
CHARACTER_PATH = "gameData.heroUnlock"
CHARACTER_RECORD_FIELD = "characters"
MAX_CHARACTERS = 42


class CharacterEditError(CloudSaveError):
    code = "characters_edit"


class InvalidCharacterSelection(CharacterEditError):
    code = "invalid_character_selection"


class UnknownCharacter(CharacterEditError):
    code = "unknown_character"


class CharacterFieldMissing(CharacterEditError):
    code = "character_field_missing"


class UnsupportedCharacterStructure(CharacterEditError):
    code = "unsupported_characters_structure"


class CharacterCatalogMissing(CharacterEditError):
    code = "character_catalog_missing"


class UnsupportedCharacterSerialization(CharacterEditError):
    code = "unsupported_serialization"


class CharacterVerificationError(CharacterEditError):
    code = "character_verification_failed"


class OutdatedCharacterDraft(CharacterEditError):
    code = "outdated_character_draft"


def character_catalog_codes() -> tuple[str, ...]:
    """Códigos del catálogo local, sin depender del contenido de la partida."""
    catalog = load_character_catalog()
    codes = catalog.get("codes")
    if not isinstance(codes, list) or not codes:
        raise CharacterCatalogMissing(
            "No está disponible el catálogo de personajes; no se puede validar la selección."
        )
    normalized: list[str] = []
    for code in codes:
        if not isinstance(code, str) or not code or code in normalized:
            raise CharacterCatalogMissing("El catálogo de personajes contiene códigos inválidos.")
        normalized.append(code)
    if len(normalized) > MAX_CHARACTERS:
        raise CharacterCatalogMissing("El catálogo de personajes supera el tamaño admitido.")
    return tuple(normalized)


@dataclass(frozen=True)
class CharacterSnapshot:
    """Estado de disponibilidad y huella del agregado, sin conservar el mapa."""

    unlocked: tuple[str, ...]
    total: int
    size: int
    sha256: str = field(repr=False)
    serialzed_version: int

    def summary(self) -> dict[str, object]:
        return {
            "unlocked": list(self.unlocked),
            "unlocked_count": len(self.unlocked),
            "total": self.total,
            "character_path": CHARACTER_PATH,
            "size": self.size,
            "sha256": self.sha256,
            "serialzed_version": self.serialzed_version,
        }


@dataclass(frozen=True)
class CharacterEdit:
    """Resultado determinista de preparar un desbloqueo de personajes."""

    original_unlocked: tuple[str, ...]
    selected_codes: tuple[str, ...]
    newly_unlocked: tuple[str, ...]
    new_unlocked: tuple[str, ...]
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
            "field": CHARACTER_PATH,
            "original_unlocked_count": len(self.original_unlocked),
            "new_unlocked_count": len(self.new_unlocked),
            "total_characters": self.total,
            "selected_codes": list(self.selected_codes),
            "newly_unlocked_codes": list(self.newly_unlocked),
            "changed": self.changed,
            "original_size": len(self.original),
            "candidate_size": len(self.candidate),
            "original_sha256": self.original_sha256,
            "candidate_sha256": self.candidate_sha256,
            "serialzed_version": self.serialzed_version,
            "binary": self.binary.as_dict(),
            "changed_fields": list(self.changed_fields),
        }


def _validated_document(source: bytes) -> tuple[JsonObject, int]:
    if not source:
        raise CopyLimitError("La copia está vacía.")
    if len(source) > MAX_INPUT_BYTES:
        raise CopyLimitError("La copia supera el límite permitido.")
    reconstruct_cloud_save(source)
    encoding, document = unpack_cloud_save(source)
    if encoding != "json":
        raise UnsupportedCharacterSerialization(
            "El editor de personajes solo admite el agregado JSON que usa el sobre de nube."
        )
    try:
        root = parse_json(document)
    except (ValueError, RecursionError):
        raise AggregateFormatError("El documento no contiene JSON UTF-8 válido.") from None
    if not isinstance(root, dict):
        raise AggregateFormatError("Se esperaba un objeto JSON en la raíz.")
    if serialize_aggregate(root) != source:
        raise UnsupportedCharacterSerialization(
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


def _unlock_map(root: JsonObject) -> JsonObject:
    game_data = _game_data(root)
    if CHARACTER_FIELD_ID not in game_data:
        raise CharacterFieldMissing("La copia no contiene gameData.heroUnlock.")
    unlock = game_data[CHARACTER_FIELD_ID]
    if not isinstance(unlock, dict):
        raise UnsupportedCharacterStructure(
            "gameData.heroUnlock no es un objeto de códigos a valores booleanos."
        )
    for code, value in unlock.items():
        if not isinstance(code, str) or not code:
            raise UnsupportedCharacterStructure(
                "gameData.heroUnlock contiene una clave de personaje inválida."
            )
        if not isinstance(value, bool):
            raise UnsupportedCharacterStructure(
                "gameData.heroUnlock contiene un valor que no es booleano; no se "
                "sobrescribe una estructura de otro tipo."
            )
    return unlock


def _catalog_and_selection(codes: object) -> tuple[tuple[str, ...], tuple[str, ...]]:
    catalog = character_catalog_codes()
    if not isinstance(codes, (list, tuple)):
        raise InvalidCharacterSelection("Selecciona al menos un personaje bloqueado.")
    if not 1 <= len(codes) <= len(catalog):
        raise InvalidCharacterSelection(
            f"La selección debe contener entre 1 y {len(catalog)} personajes."
        )
    known = set(catalog)
    selected: list[str] = []
    seen: set[str] = set()
    for code in codes:
        if not isinstance(code, str) or not code:
            raise InvalidCharacterSelection("La selección contiene un código de personaje inválido.")
        if code not in known:
            raise UnknownCharacter(f"El personaje {code} no pertenece al catálogo.")
        if code in seen:
            raise InvalidCharacterSelection(f"El personaje {code} está repetido en la selección.")
        seen.add(code)
        selected.append(code)
    return catalog, tuple(selected)


def read_characters(source: bytes) -> CharacterSnapshot:
    """Lee la disponibilidad declarada por ``gameData.heroUnlock``."""
    root, version = _validated_document(source)
    unlock = _unlock_map(root)
    catalog = character_catalog_codes()
    unlocked = tuple(code for code in catalog if unlock.get(code) is True)
    return CharacterSnapshot(
        unlocked=unlocked,
        total=len(catalog),
        size=len(source),
        sha256=sha256(source).hexdigest(),
        serialzed_version=version,
    )


def prepare_character_unlock_edit(source: bytes, codes: object) -> CharacterEdit:
    """Prepara un candidato que solo activa los códigos seleccionados.

    Los códigos ya disponibles se conservan tal cual. Si un código del catálogo
    no aparece en ``heroUnlock``, se añade como ``true`` únicamente cuando fue
    seleccionado, respetando el mapa observado en las copias reales.
    """
    catalog, selected = _catalog_and_selection(codes)
    root, version = _validated_document(source)
    unlock = _unlock_map(root)
    original_sha = sha256(source).hexdigest()
    original_unlocked = tuple(code for code in catalog if unlock.get(code) is True)
    newly_unlocked = tuple(code for code in selected if unlock.get(code) is not True)
    new_unlocked = original_unlocked + tuple(
        code for code in newly_unlocked if code not in original_unlocked
    )

    if not newly_unlocked:
        return CharacterEdit(
            original_unlocked=original_unlocked,
            selected_codes=selected,
            newly_unlocked=(),
            new_unlocked=original_unlocked,
            total=len(catalog),
            changed=False,
            original=source,
            candidate=source,
            original_sha256=original_sha,
            candidate_sha256=original_sha,
            binary=binary_diff(source, source),
            serialzed_version=version,
        )

    modified = deepcopy(root)
    modified_unlock = _unlock_map(modified)
    for code in selected:
        modified_unlock[code] = True

    candidate = serialize_aggregate(modified)
    if len(candidate) > MAX_INPUT_BYTES:
        raise CopyLimitError("La copia editada supera el límite permitido.")
    reconstruct_cloud_save(candidate)
    try:
        reopened = parse_json(unpack_cloud_save(candidate)[1])
    except (ValueError, RecursionError):
        raise CharacterVerificationError("La copia editada no se puede volver a abrir.") from None
    if reopened != modified:
        raise CharacterVerificationError("La copia reabierta no coincide con la copia editada.")
    if serialize_aggregate(reopened) != candidate:
        raise CharacterVerificationError("La copia editada no es estable al serializarla de nuevo.")
    reopened_snapshot = read_characters(candidate)
    expected_unlocked = tuple(code for code in catalog if code in set(new_unlocked))
    if reopened_snapshot.unlocked != expected_unlocked:
        raise CharacterVerificationError(
            "La copia editada no contiene exactamente los personajes solicitados."
        )
    # Restaurar el mapa original completo debe reproducir el documento byte a byte.
    reopened["gameData"][CHARACTER_FIELD_ID] = unlock
    if serialize_aggregate(reopened) != source:
        raise CharacterVerificationError(
            "La edición afectó a datos fuera de gameData.heroUnlock."
        )
    binary = binary_diff(source, candidate)
    if binary.first_difference is None:
        raise CharacterVerificationError("La copia editada es idéntica al original.")

    return CharacterEdit(
        original_unlocked=original_unlocked,
        selected_codes=selected,
        newly_unlocked=newly_unlocked,
        new_unlocked=new_unlocked,
        total=len(catalog),
        changed=True,
        original=source,
        candidate=candidate,
        original_sha256=original_sha,
        candidate_sha256=sha256(candidate).hexdigest(),
        binary=binary,
        serialzed_version=version,
        changed_fields=tuple(f"{CHARACTER_PATH}.{code}" for code in newly_unlocked),
    )


def require_character_write_compatibility(
    source: bytes, selected_codes: object, candidate: bytes
) -> None:
    if prepare_character_unlock_edit(source, selected_codes).candidate != candidate:
        raise OutdatedCharacterDraft(
            "El respaldo usa un borrador antiguo. Prepara de nuevo la selección antes de subirla."
        )
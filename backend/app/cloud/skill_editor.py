"""Desbloqueo granular de habilidades en ``gameData.heroSkillUnlock``.

La Fase 6.17 parte de una observación consistente en copias reales de 8.8.0 y
en las preferencias del cliente Android: ``heroSkillUnlock`` es un mapa de
código de personaje a una lista ordenada de entradas ``{Key, Value}``. Los
índices de ``Key`` coinciden con los índices del catálogo local y ``Value`` es
booleano. Solo el índice 0 aparece como ``true`` en las copias observadas, por
lo que la escritura de otros índices permanece en nivel experimental E2.

``heroSkill`` es el índice de la habilidad equipada. Este editor lo conserva
sin modificarlo. Tampoco crea listas o entradas ausentes: si la estructura no
contiene la posición solicitada, la operación se rechaza de forma controlada.
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

SKILL_FIELD_ID = "heroSkillUnlock"
SKILL_PATH = "gameData.heroSkillUnlock"
SKILL_RECORD_FIELD = "skills"
MAX_SKILLS = 105


class SkillEditError(CloudSaveError):
    code = "skills_edit"


class InvalidSkillSelection(SkillEditError):
    code = "invalid_skill_selection"


class UnknownSkillCharacter(SkillEditError):
    code = "unknown_skill_character"


class UnknownSkillIndex(SkillEditError):
    code = "unknown_skill_index"


class SkillFieldMissing(SkillEditError):
    code = "skill_field_missing"


class IncompleteSkillStructure(SkillEditError):
    code = "incomplete_skill_structure"


class UnsupportedSkillStructure(SkillEditError):
    code = "unsupported_skills_structure"


class SkillCatalogMissing(SkillEditError):
    code = "skill_catalog_missing"


class UnsupportedSkillSerialization(SkillEditError):
    code = "unsupported_serialization"


class SkillVerificationError(SkillEditError):
    code = "skill_verification_failed"


class OutdatedSkillDraft(SkillEditError):
    code = "outdated_skill_draft"


@dataclass(frozen=True, order=True)
class SkillRef:
    """Referencia estable a una habilidad de un personaje."""

    code: str
    index: int

    def as_dict(self) -> dict[str, object]:
        return {"code": self.code, "index": self.index}


@dataclass(frozen=True)
class SkillCatalog:
    """Vista ordenada del catálogo de habilidades del backend."""

    codes: tuple[str, ...]
    indices: dict[str, tuple[int, ...]] = field(repr=False)
    names: dict[tuple[str, int], str] = field(repr=False)

    @property
    def total(self) -> int:
        return sum(len(group) for group in self.indices.values())


def skill_catalog() -> SkillCatalog:
    """Carga el catálogo empaquetado y valida sus índices de habilidad."""
    catalog = load_character_catalog()
    if not catalog.get("available"):
        raise SkillCatalogMissing(
            "No está disponible el catálogo de personajes y habilidades; no se puede "
            "validar la selección."
        )
    raw_codes = catalog.get("codes")
    raw_characters = catalog.get("characters")
    if not isinstance(raw_codes, list) or not raw_codes or not isinstance(raw_characters, dict):
        raise SkillCatalogMissing("El catálogo no contiene códigos y habilidades válidos.")

    codes: list[str] = []
    indices: dict[str, tuple[int, ...]] = {}
    names: dict[tuple[str, int], str] = {}
    seen_codes: set[str] = set()
    total = 0
    for code in raw_codes:
        if not isinstance(code, str) or not code or code in seen_codes:
            raise SkillCatalogMissing("El catálogo contiene códigos de personaje inválidos.")
        entry = raw_characters.get(code)
        if not isinstance(entry, dict):
            raise SkillCatalogMissing(f"El catálogo no contiene el personaje {code}.")
        raw_skills = entry.get("skills")
        if not isinstance(raw_skills, list) or not raw_skills:
            raise SkillCatalogMissing(f"El catálogo no contiene habilidades para {code}.")
        group: list[int] = []
        for skill in raw_skills:
            if not isinstance(skill, dict):
                raise SkillCatalogMissing(f"El catálogo contiene una habilidad inválida en {code}.")
            index = skill.get("index")
            name = skill.get("name")
            if type(index) is not int or index < 0 or index in group:
                raise SkillCatalogMissing(
                    f"El catálogo contiene un índice de habilidad inválido en {code}."
                )
            if not isinstance(name, str) or not name:
                raise SkillCatalogMissing(
                    f"El catálogo contiene un nombre de habilidad inválido en {code}."
                )
            group.append(index)
            names[(code, index)] = name
        total += len(group)
        if total > MAX_SKILLS:
            raise SkillCatalogMissing("El catálogo de habilidades supera el tamaño admitido.")
        seen_codes.add(code)
        codes.append(code)
        indices[code] = tuple(group)

    if total == 0:
        raise SkillCatalogMissing("El catálogo no contiene habilidades.")
    return SkillCatalog(codes=tuple(codes), indices=indices, names=names)


def _normalize_selection(
    catalog: SkillCatalog, selections: object
) -> tuple[SkillRef, ...]:
    if not isinstance(selections, (list, tuple)):
        raise InvalidSkillSelection("Selecciona al menos una habilidad bloqueada.")
    if not 1 <= len(selections) <= catalog.total:
        raise InvalidSkillSelection(
            f"La selección debe contener entre 1 y {catalog.total} habilidades."
        )
    known_codes = set(catalog.codes)
    seen: set[SkillRef] = set()
    selected: list[SkillRef] = []
    for selection in selections:
        if isinstance(selection, SkillRef):
            code, index = selection.code, selection.index
        elif isinstance(selection, dict):
            code, index = selection.get("code"), selection.get("index")
        elif isinstance(selection, (list, tuple)) and len(selection) == 2:
            code, index = selection
        else:
            raise InvalidSkillSelection("La selección contiene una habilidad inválida.")
        if not isinstance(code, str) or not code:
            raise InvalidSkillSelection("La selección contiene un código de personaje inválido.")
        if type(index) is not int or index < 0:
            raise InvalidSkillSelection("La selección contiene un índice de habilidad inválido.")
        if code not in known_codes:
            raise UnknownSkillCharacter(f"El personaje {code} no pertenece al catálogo.")
        if index not in catalog.indices[code]:
            raise UnknownSkillIndex(
                f"La habilidad {index} no pertenece al catálogo de {code}."
            )
        ref = SkillRef(code=code, index=index)
        if ref in seen:
            raise InvalidSkillSelection(
                f"La habilidad {index} de {code} está repetida en la selección."
            )
        seen.add(ref)
        selected.append(ref)
    order = {code: position for position, code in enumerate(catalog.codes)}
    return tuple(sorted(selected, key=lambda ref: (order[ref.code], ref.index)))


@dataclass(frozen=True)
class SkillSnapshot:
    """Estado observado de las habilidades de la partida."""

    unlocked: tuple[SkillRef, ...]
    total: int
    selected: tuple[SkillRef, ...]
    characters_with_data: int
    size: int
    sha256: str = field(repr=False)
    serialzed_version: int

    def summary(self) -> dict[str, object]:
        return {
            "field": SKILL_PATH,
            "unlocked": [ref.as_dict() for ref in self.unlocked],
            "unlocked_count": len(self.unlocked),
            "locked_count": self.total - len(self.unlocked),
            "selected": [ref.as_dict() for ref in self.selected],
            "selected_count": len(self.selected),
            "total_skills": self.total,
            "characters_with_data": self.characters_with_data,
            "size": self.size,
            "sha256": self.sha256,
            "serialzed_version": self.serialzed_version,
        }


@dataclass(frozen=True)
class SkillEdit:
    """Resultado determinista de preparar un desbloqueo de habilidades."""

    original_unlocked: tuple[SkillRef, ...]
    selected_skills: tuple[SkillRef, ...]
    newly_unlocked: tuple[SkillRef, ...]
    new_unlocked: tuple[SkillRef, ...]
    total: int
    affected_codes: tuple[str, ...]
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
            "field": SKILL_PATH,
            "original_unlocked_count": len(self.original_unlocked),
            "new_unlocked_count": len(self.new_unlocked),
            "total_skills": self.total,
            "selected_skills": [ref.as_dict() for ref in self.selected_skills],
            "newly_unlocked_skills": [ref.as_dict() for ref in self.newly_unlocked],
            "affected_codes": list(self.affected_codes),
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
        raise UnsupportedSkillSerialization(
            "El editor de habilidades solo admite el agregado JSON que usa el sobre de nube."
        )
    try:
        root = parse_json(document)
    except (ValueError, RecursionError):
        raise AggregateFormatError("El documento no contiene JSON UTF-8 válido.") from None
    if not isinstance(root, dict):
        raise AggregateFormatError("Se esperaba un objeto JSON en la raíz.")
    if serialize_aggregate(root) != source:
        raise UnsupportedSkillSerialization(
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


def _skill_map(root: JsonObject) -> JsonObject:
    game_data = _game_data(root)
    if SKILL_FIELD_ID not in game_data:
        raise SkillFieldMissing("La copia no contiene gameData.heroSkillUnlock.")
    skill_map = game_data[SKILL_FIELD_ID]
    if not isinstance(skill_map, dict):
        raise UnsupportedSkillStructure(
            "gameData.heroSkillUnlock no es un objeto de códigos a listas de habilidades."
        )
    for code, entries in skill_map.items():
        if not isinstance(code, str) or not code:
            raise UnsupportedSkillStructure(
                "gameData.heroSkillUnlock contiene una clave de personaje inválida."
            )
        if not isinstance(entries, list):
            raise UnsupportedSkillStructure(
                f"gameData.heroSkillUnlock.{code} no es una lista de habilidades."
            )
        seen: set[int] = set()
        for entry in entries:
            if not isinstance(entry, dict):
                raise UnsupportedSkillStructure(
                    f"gameData.heroSkillUnlock.{code} contiene una entrada que no es un objeto."
                )
            key = entry.get("Key")
            value = entry.get("Value")
            if type(key) is not int or key < 0:
                raise UnsupportedSkillStructure(
                    f"gameData.heroSkillUnlock.{code} contiene un Key inválido."
                )
            if key in seen:
                raise UnsupportedSkillStructure(
                    f"gameData.heroSkillUnlock.{code} repite la posición {key}."
                )
            if not isinstance(value, bool):
                raise UnsupportedSkillStructure(
                    f"gameData.heroSkillUnlock.{code}[{key}] no contiene un booleano."
                )
            seen.add(key)
    return skill_map


def _selected_by_character(root: JsonObject, catalog: SkillCatalog) -> tuple[SkillRef, ...]:
    game_data = _game_data(root)
    raw = game_data.get("heroSkill")
    if raw is None:
        return ()
    if not isinstance(raw, dict):
        raise UnsupportedSkillStructure("gameData.heroSkill no es un objeto de índices.")
    selected: list[SkillRef] = []
    for code in catalog.codes:
        index = raw.get(code)
        if type(index) is int and not isinstance(index, bool) and index in catalog.indices[code]:
            selected.append(SkillRef(code=code, index=index))
    return tuple(selected)


def _unlocked_known(
    skill_map: JsonObject, catalog: SkillCatalog
) -> tuple[SkillRef, ...]:
    unlocked: list[SkillRef] = []
    for code in catalog.codes:
        entries = skill_map.get(code)
        if entries is None:
            continue
        values = {
            entry.get("Key"): entry.get("Value")
            for entry in entries
            if isinstance(entry, dict)
        }
        for index in catalog.indices[code]:
            if values.get(index) is True:
                unlocked.append(SkillRef(code=code, index=index))
    return tuple(unlocked)


def read_skills(source: bytes) -> SkillSnapshot:
    """Lee las habilidades desbloqueadas y la habilidad equipada observadas."""
    root, version = _validated_document(source)
    skill_map = _skill_map(root)
    catalog = skill_catalog()
    unlocked = _unlocked_known(skill_map, catalog)
    selected = _selected_by_character(root, catalog)
    present = sum(1 for code in catalog.codes if code in skill_map)
    return SkillSnapshot(
        unlocked=unlocked,
        total=catalog.total,
        selected=selected,
        characters_with_data=present,
        size=len(source),
        sha256=sha256(source).hexdigest(),
        serialzed_version=version,
    )


def prepare_skill_unlock_edit(source: bytes, selections: object) -> SkillEdit:
    """Prepara un candidato que solo activa las habilidades seleccionadas.

    Las habilidades ya disponibles y ``heroSkill`` se conservan. Cada posición
    seleccionada debe existir en la estructura original; no se crean listas ni
    entradas nuevas.
    """
    catalog = skill_catalog()
    selected = _normalize_selection(catalog, selections)
    root, version = _validated_document(source)
    skill_map = _skill_map(root)
    original_sha = sha256(source).hexdigest()
    original_unlocked = _unlocked_known(skill_map, catalog)

    missing_codes: list[str] = []
    missing_entries: list[SkillRef] = []
    for ref in selected:
        if ref.code not in skill_map:
            if ref.code not in missing_codes:
                missing_codes.append(ref.code)
            continue
        entries = skill_map[ref.code]
        if not any(
            isinstance(entry, dict) and entry.get("Key") == ref.index for entry in entries
        ):
            missing_entries.append(ref)
    if missing_codes:
        raise IncompleteSkillStructure(
            "La partida no contiene la estructura de habilidades de: "
            + ", ".join(missing_codes)
            + ". No se crean estructuras ausentes."
        )
    if missing_entries:
        raise IncompleteSkillStructure(
            "La partida no contiene las posiciones solicitadas: "
            + ", ".join(f"{ref.code}[{ref.index}]" for ref in missing_entries)
            + ". No se crean posiciones ausentes."
        )

    unlocked_set = set(original_unlocked)
    newly_unlocked = tuple(ref for ref in selected if ref not in unlocked_set)
    final_set = unlocked_set | set(selected)
    new_unlocked = tuple(
        SkillRef(code=code, index=index)
        for code in catalog.codes
        for index in catalog.indices[code]
        if SkillRef(code=code, index=index) in final_set
    )
    affected_codes = tuple(
        code for code in catalog.codes if any(ref.code == code for ref in newly_unlocked)
    )

    if not newly_unlocked:
        return SkillEdit(
            original_unlocked=original_unlocked,
            selected_skills=selected,
            newly_unlocked=(),
            new_unlocked=original_unlocked,
            total=catalog.total,
            affected_codes=(),
            changed=False,
            original=source,
            candidate=source,
            original_sha256=original_sha,
            candidate_sha256=original_sha,
            binary=binary_diff(source, source),
            serialzed_version=version,
        )

    modified = deepcopy(root)
    modified_map = _skill_map(modified)
    for ref in newly_unlocked:
        for entry in modified_map[ref.code]:
            if isinstance(entry, dict) and entry.get("Key") == ref.index:
                entry["Value"] = True
                break

    candidate = serialize_aggregate(modified)
    if len(candidate) > MAX_INPUT_BYTES:
        raise CopyLimitError("La copia editada supera el límite permitido.")
    reconstruct_cloud_save(candidate)
    try:
        reopened = parse_json(unpack_cloud_save(candidate)[1])
    except (ValueError, RecursionError):
        raise SkillVerificationError("La copia editada no se puede volver a abrir.") from None
    if reopened != modified:
        raise SkillVerificationError("La copia reabierta no coincide con la copia editada.")
    if serialize_aggregate(reopened) != candidate:
        raise SkillVerificationError("La copia editada no es estable al serializarla de nuevo.")
    reopened_snapshot = read_skills(candidate)
    if reopened_snapshot.unlocked != new_unlocked:
        raise SkillVerificationError(
            "La copia editada no contiene exactamente las habilidades solicitadas."
        )
    if reopened_snapshot.selected != _selected_by_character(root, catalog):
        raise SkillVerificationError("La edición alteró gameData.heroSkill.")
    # Restaurar el mapa original completo debe reproducir el documento byte a byte.
    reopened["gameData"][SKILL_FIELD_ID] = skill_map
    if serialize_aggregate(reopened) != source:
        raise SkillVerificationError(
            "La edición afectó a datos fuera de gameData.heroSkillUnlock."
        )
    binary = binary_diff(source, candidate)
    if binary.first_difference is None:
        raise SkillVerificationError("La copia editada es idéntica al original.")

    return SkillEdit(
        original_unlocked=original_unlocked,
        selected_skills=selected,
        newly_unlocked=newly_unlocked,
        new_unlocked=new_unlocked,
        total=catalog.total,
        affected_codes=affected_codes,
        changed=True,
        original=source,
        candidate=candidate,
        original_sha256=original_sha,
        candidate_sha256=sha256(candidate).hexdigest(),
        binary=binary,
        serialzed_version=version,
        changed_fields=tuple(
            f"{SKILL_PATH}.{ref.code}[{ref.index}]" for ref in newly_unlocked
        ),
    )


def require_skill_write_compatibility(
    source: bytes, selections: object, candidate: bytes
) -> None:
    if prepare_skill_unlock_edit(source, selections).candidate != candidate:
        raise OutdatedSkillDraft(
            "El respaldo usa un borrador antiguo. Prepara de nuevo la selección antes de subirla."
        )
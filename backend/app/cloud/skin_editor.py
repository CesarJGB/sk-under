"""Desbloqueo granular de skins confirmado por el propietario en ``gameData.skinLock``.

La Fase 6.19 conserva la política conservadora de las fases anteriores: las
copias reales de 8.8.0 contienen exactamente 802 posiciones ``{Key, Value}``
repartidas en 42 listas por código de personaje, y el catálogo empaquetado
contiene las mismas 802 posiciones en el mismo orden.

La única semántica que se escribe es ``Value = 1`` para una skin concreta. En
las muestras observadas las 42 skins base (``Key = 0``) y una skin adicional de
Warlock tienen ``Value = 1``; el resto usa otros enteros (cero, precios o
códigos negativos) cuya semántica no se ha validado. El propietario confirmó en
Android físico que las skins seleccionadas aparecen disponibles en el cliente
oficial (E3), sin declarar persistencia posterior. El editor no crea posiciones,
no agrega personajes, no modifica ``currentSkinDatas`` (la selección observada)
ni ``heroUnlock`` y exige que cada posición seleccionada exista en la copia
original.
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

SKIN_FIELD_ID = "skinLock"
SKIN_PATH = "gameData.skinLock"
SKIN_RECORD_FIELD = "skins"
SKIN_SELECTION_PATH = "gameData.currentSkinDatas"
UNLOCKED_VALUE = 1
MAX_SKINS = 802


class SkinEditError(CloudSaveError):
    code = "skins_edit"


class InvalidSkinSelection(SkinEditError):
    code = "invalid_skin_selection"


class UnknownSkinCharacter(SkinEditError):
    code = "unknown_skin_character"


class UnknownSkinIndex(SkinEditError):
    code = "unknown_skin_index"


class SkinFieldMissing(SkinEditError):
    code = "skin_field_missing"


class IncompleteSkinStructure(SkinEditError):
    code = "incomplete_skin_structure"


class UnsupportedSkinStructure(SkinEditError):
    code = "unsupported_skins_structure"


class SkinCatalogMissing(SkinEditError):
    code = "skin_catalog_missing"


class UnsupportedSkinSerialization(SkinEditError):
    code = "unsupported_serialization"


class SkinVerificationError(SkinEditError):
    code = "skin_verification_failed"


class OutdatedSkinDraft(SkinEditError):
    code = "outdated_skin_draft"


@dataclass(frozen=True, order=True)
class SkinRef:
    """Referencia estable a una skin de un personaje."""

    code: str
    index: int

    def as_dict(self) -> dict[str, object]:
        return {"code": self.code, "index": self.index}


@dataclass(frozen=True)
class SkinCatalog:
    """Vista ordenada del catálogo de skins del backend."""

    codes: tuple[str, ...]
    indices: dict[str, tuple[int, ...]] = field(repr=False)
    names: dict[tuple[str, int], str] = field(repr=False)
    keys: dict[tuple[str, int], str] = field(repr=False)

    @property
    def total(self) -> int:
        return sum(len(group) for group in self.indices.values())


def skin_catalog() -> SkinCatalog:
    """Carga el catálogo empaquetado y valida sus índices de skin."""
    catalog = load_character_catalog()
    if not catalog.get("available"):
        raise SkinCatalogMissing(
            "No está disponible el catálogo de personajes y skins; no se puede validar la selección."
        )
    raw_codes = catalog.get("codes")
    raw_characters = catalog.get("characters")
    if not isinstance(raw_codes, list) or not raw_codes or not isinstance(raw_characters, dict):
        raise SkinCatalogMissing("El catálogo no contiene códigos y skins válidos.")

    codes: list[str] = []
    indices: dict[str, tuple[int, ...]] = {}
    names: dict[tuple[str, int], str] = {}
    keys: dict[tuple[str, int], str] = {}
    seen_codes: set[str] = set()
    total = 0
    for code in raw_codes:
        if not isinstance(code, str) or not code or code in seen_codes:
            raise SkinCatalogMissing("El catálogo contiene códigos de personaje inválidos.")
        entry = raw_characters.get(code)
        if not isinstance(entry, dict):
            raise SkinCatalogMissing(f"El catálogo no contiene el personaje {code}.")
        raw_skins = entry.get("skins")
        if not isinstance(raw_skins, list) or not raw_skins:
            raise SkinCatalogMissing(f"El catálogo no contiene skins para {code}.")
        group: list[int] = []
        for skin in raw_skins:
            if not isinstance(skin, dict):
                raise SkinCatalogMissing(f"El catálogo contiene una skin inválida en {code}.")
            index = skin.get("index")
            name = skin.get("name")
            key = skin.get("key")
            if type(index) is not int or index < 0 or index in group:
                raise SkinCatalogMissing(f"El catálogo contiene un índice de skin inválido en {code}.")
            if not isinstance(name, str):
                raise SkinCatalogMissing(f"El catálogo contiene un nombre de skin inválido en {code}.")
            if not isinstance(key, str) or not key:
                raise SkinCatalogMissing(f"El catálogo contiene una clave de skin inválida en {code}.")
            group.append(index)
            names[(code, index)] = name
            keys[(code, index)] = key
        total += len(group)
        if total > MAX_SKINS:
            raise SkinCatalogMissing("El catálogo de skins supera el tamaño admitido.")
        seen_codes.add(code)
        codes.append(code)
        indices[code] = tuple(group)

    if total == 0:
        raise SkinCatalogMissing("El catálogo no contiene skins.")
    return SkinCatalog(codes=tuple(codes), indices=indices, names=names, keys=keys)


def skin_catalog_next_index(catalog: SkinCatalog) -> int:
    """Compatibilidad de diagnóstico: máximo índice de skin + 1."""
    return max((index for group in catalog.indices.values() for index in group), default=-1) + 1


def _normalize_selection(catalog: SkinCatalog, selections: object) -> tuple[SkinRef, ...]:
    if not isinstance(selections, (list, tuple)):
        raise InvalidSkinSelection("Selecciona al menos una skin bloqueada.")
    if not 1 <= len(selections) <= catalog.total:
        raise InvalidSkinSelection(f"La selección debe contener entre 1 y {catalog.total} skins.")
    known_codes = set(catalog.codes)
    seen: set[SkinRef] = set()
    selected: list[SkinRef] = []
    for selection in selections:
        if isinstance(selection, SkinRef):
            code, index = selection.code, selection.index
        elif isinstance(selection, dict):
            code, index = selection.get("code"), selection.get("index")
        elif isinstance(selection, (list, tuple)) and len(selection) == 2:
            code, index = selection
        else:
            raise InvalidSkinSelection("La selección contiene una skin inválida.")
        if not isinstance(code, str) or not code:
            raise InvalidSkinSelection("La selección contiene un código de personaje inválido.")
        if type(index) is not int or index < 0:
            raise InvalidSkinSelection("La selección contiene un índice de skin inválido.")
        if code not in known_codes:
            raise UnknownSkinCharacter(f"El personaje {code} no pertenece al catálogo.")
        if index not in catalog.indices[code]:
            raise UnknownSkinIndex(f"La skin {index} no pertenece al catálogo de {code}.")
        ref = SkinRef(code=code, index=index)
        if ref in seen:
            raise InvalidSkinSelection(f"La skin {index} de {code} está repetida en la selección.")
        seen.add(ref)
        selected.append(ref)
    order = {code: position for position, code in enumerate(catalog.codes)}
    return tuple(sorted(selected, key=lambda ref: (order[ref.code], ref.index)))


@dataclass(frozen=True)
class SkinSnapshot:
    """Estado observado de las skins de la partida."""

    unlocked: tuple[SkinRef, ...]
    total: int
    selected: tuple[SkinRef, ...]
    characters_with_data: int
    size: int
    sha256: str = field(repr=False)
    serialzed_version: int

    def summary(self) -> dict[str, object]:
        return {
            "field": SKIN_PATH,
            "unlocked": [ref.as_dict() for ref in self.unlocked],
            "unlocked_count": len(self.unlocked),
            "locked_count": self.total - len(self.unlocked),
            "selected": [ref.as_dict() for ref in self.selected],
            "selected_count": len(self.selected),
            "total_skins": self.total,
            "characters_with_data": self.characters_with_data,
            "size": self.size,
            "sha256": self.sha256,
            "serialzed_version": self.serialzed_version,
        }


@dataclass(frozen=True)
class SkinEdit:
    """Resultado determinista de preparar un desbloqueo de skins."""

    original_unlocked: tuple[SkinRef, ...]
    selected_skins: tuple[SkinRef, ...]
    newly_unlocked: tuple[SkinRef, ...]
    new_unlocked: tuple[SkinRef, ...]
    total: int
    affected_codes: tuple[str, ...]
    locked_character_codes: tuple[str, ...]
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
            "field": SKIN_PATH,
            "original_unlocked_count": len(self.original_unlocked),
            "new_unlocked_count": len(self.new_unlocked),
            "total_skins": self.total,
            "selected_skins": [ref.as_dict() for ref in self.selected_skins],
            "newly_unlocked_skins": [ref.as_dict() for ref in self.newly_unlocked],
            "affected_codes": list(self.affected_codes),
            "locked_character_codes": list(self.locked_character_codes),
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
        raise UnsupportedSkinSerialization(
            "El editor de skins solo admite el agregado JSON que usa el sobre de nube."
        )
    try:
        root = parse_json(document)
    except (ValueError, RecursionError):
        raise AggregateFormatError("El documento no contiene JSON UTF-8 válido.") from None
    if not isinstance(root, dict):
        raise AggregateFormatError("Se esperaba un objeto JSON en la raíz.")
    if serialize_aggregate(root) != source:
        raise UnsupportedSkinSerialization(
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


def _skin_map(root: JsonObject, catalog: SkinCatalog) -> JsonObject:
    game_data = _game_data(root)
    if SKIN_FIELD_ID not in game_data:
        raise SkinFieldMissing("La copia no contiene gameData.skinLock.")
    skin_map = game_data[SKIN_FIELD_ID]
    if not isinstance(skin_map, dict):
        raise UnsupportedSkinStructure(
            "gameData.skinLock no es un objeto de códigos a listas de skins."
        )
    for code, entries in skin_map.items():
        if not isinstance(code, str) or not code:
            raise UnsupportedSkinStructure("gameData.skinLock contiene una clave de personaje inválida.")
        if code not in catalog.indices:
            raise UnsupportedSkinStructure(
                f"gameData.skinLock contiene el personaje desconocido {code}."
            )
        if not isinstance(entries, list):
            raise UnsupportedSkinStructure(f"gameData.skinLock.{code} no es una lista de skins.")
        known = set(catalog.indices[code])
        seen: set[int] = set()
        for entry in entries:
            if not isinstance(entry, dict):
                raise UnsupportedSkinStructure(
                    f"gameData.skinLock.{code} contiene una entrada que no es un objeto."
                )
            key = entry.get("Key")
            value = entry.get("Value")
            if type(key) is not int or key < 0:
                raise UnsupportedSkinStructure(
                    f"gameData.skinLock.{code} contiene un Key inválido."
                )
            if key not in known:
                raise UnsupportedSkinStructure(
                    f"gameData.skinLock.{code} contiene la posición desconocida {key}."
                )
            if key in seen:
                raise UnsupportedSkinStructure(
                    f"gameData.skinLock.{code} repite la posición {key}."
                )
            if type(value) is not int:
                raise UnsupportedSkinStructure(
                    f"gameData.skinLock.{code}[{key}] no contiene un entero."
                )
            seen.add(key)
    return skin_map


def _selected_by_character(root: JsonObject, catalog: SkinCatalog) -> tuple[SkinRef, ...]:
    game_data = _game_data(root)
    raw = game_data.get(SKIN_SELECTION_PATH.removeprefix("gameData."))
    if not isinstance(raw, dict):
        return ()
    selected: list[SkinRef] = []
    for code in catalog.codes:
        index = raw.get(code)
        if type(index) is int and not isinstance(index, bool) and index in catalog.indices[code]:
            selected.append(SkinRef(code=code, index=index))
    return tuple(selected)


def _unlocked_known(skin_map: JsonObject, catalog: SkinCatalog) -> tuple[SkinRef, ...]:
    unlocked: list[SkinRef] = []
    for code in catalog.codes:
        entries = skin_map.get(code)
        if not isinstance(entries, list):
            continue
        values = {
            entry.get("Key"): entry.get("Value")
            for entry in entries
            if isinstance(entry, dict)
        }
        for index in catalog.indices[code]:
            if values.get(index) == UNLOCKED_VALUE:
                unlocked.append(SkinRef(code=code, index=index))
    return tuple(unlocked)


def _locked_character_codes(root: JsonObject, codes: tuple[str, ...]) -> tuple[str, ...]:
    game_data = _game_data(root)
    raw = game_data.get("heroUnlock")
    if not isinstance(raw, dict):
        return codes
    return tuple(code for code in codes if raw.get(code) is not True)


def read_skins(source: bytes) -> SkinSnapshot:
    """Lee las skins desbloqueadas y la selección observada."""
    root, version = _validated_document(source)
    catalog = skin_catalog()
    skin_map = _skin_map(root, catalog)
    unlocked = _unlocked_known(skin_map, catalog)
    selected = _selected_by_character(root, catalog)
    present = sum(1 for code in catalog.codes if code in skin_map)
    return SkinSnapshot(
        unlocked=unlocked,
        total=catalog.total,
        selected=selected,
        characters_with_data=present,
        size=len(source),
        sha256=sha256(source).hexdigest(),
        serialzed_version=version,
    )


def prepare_skin_unlock_edit(source: bytes, selections: object) -> SkinEdit:
    """Prepara un candidato que solo cambia a 1 las skins seleccionadas.

    Las skins ya desbloqueadas, la selección observada en ``currentSkinDatas``,
    los personajes y el resto del agregado se conservan. Cada posición
    seleccionada debe existir en la estructura original; no se crean listas ni
    entradas nuevas.
    """
    catalog = skin_catalog()
    selected = _normalize_selection(catalog, selections)
    root, version = _validated_document(source)
    skin_map = _skin_map(root, catalog)
    original_sha = sha256(source).hexdigest()
    original_unlocked = _unlocked_known(skin_map, catalog)

    missing_codes: list[str] = []
    missing_entries: list[SkinRef] = []
    for ref in selected:
        if ref.code not in skin_map:
            if ref.code not in missing_codes:
                missing_codes.append(ref.code)
            continue
        entries = skin_map[ref.code]
        if not any(
            isinstance(entry, dict) and entry.get("Key") == ref.index for entry in entries
        ):
            missing_entries.append(ref)
    if missing_codes:
        raise IncompleteSkinStructure(
            "La partida no contiene la estructura de skins de: "
            + ", ".join(missing_codes)
            + ". No se crean estructuras ausentes."
        )
    if missing_entries:
        raise IncompleteSkinStructure(
            "La partida no contiene las posiciones solicitadas: "
            + ", ".join(f"{ref.code}[{ref.index}]" for ref in missing_entries)
            + ". No se crean posiciones ausentes."
        )

    unlocked_set = set(original_unlocked)
    newly_unlocked = tuple(ref for ref in selected if ref not in unlocked_set)
    final_set = unlocked_set | set(selected)
    new_unlocked = tuple(
        SkinRef(code=code, index=index)
        for code in catalog.codes
        for index in catalog.indices[code]
        if SkinRef(code=code, index=index) in final_set
    )
    affected_codes = tuple(
        code for code in catalog.codes if any(ref.code == code for ref in newly_unlocked)
    )
    locked_character_codes = _locked_character_codes(root, affected_codes)

    if not newly_unlocked:
        return SkinEdit(
            original_unlocked=original_unlocked,
            selected_skins=selected,
            newly_unlocked=(),
            new_unlocked=original_unlocked,
            total=catalog.total,
            affected_codes=(),
            locked_character_codes=(),
            changed=False,
            original=source,
            candidate=source,
            original_sha256=original_sha,
            candidate_sha256=original_sha,
            binary=binary_diff(source, source),
            serialzed_version=version,
        )

    modified = deepcopy(root)
    modified_map = _skin_map(modified, catalog)
    for ref in newly_unlocked:
        for entry in modified_map[ref.code]:
            if isinstance(entry, dict) and entry.get("Key") == ref.index:
                entry["Value"] = UNLOCKED_VALUE
                break

    candidate = serialize_aggregate(modified)
    if len(candidate) > MAX_INPUT_BYTES:
        raise CopyLimitError("La copia editada supera el límite permitido.")
    reconstruct_cloud_save(candidate)
    try:
        reopened = parse_json(unpack_cloud_save(candidate)[1])
    except (ValueError, RecursionError):
        raise SkinVerificationError("La copia editada no se puede volver a abrir.") from None
    if reopened != modified:
        raise SkinVerificationError("La copia reabierta no coincide con la copia editada.")
    if serialize_aggregate(reopened) != candidate:
        raise SkinVerificationError("La copia editada no es estable al serializarla de nuevo.")
    reopened_snapshot = read_skins(candidate)
    if reopened_snapshot.unlocked != new_unlocked:
        raise SkinVerificationError(
            "La copia editada no contiene exactamente las skins solicitadas."
        )
    if reopened_snapshot.selected != _selected_by_character(root, catalog):
        raise SkinVerificationError("La edición alteró gameData.currentSkinDatas.")
    # Restaurar el mapa original completo debe reproducir el documento byte a byte.
    reopened["gameData"][SKIN_FIELD_ID] = skin_map
    if serialize_aggregate(reopened) != source:
        raise SkinVerificationError("La edición afectó a datos fuera de gameData.skinLock.")
    binary = binary_diff(source, candidate)
    if binary.first_difference is None:
        raise SkinVerificationError("La copia editada es idéntica al original.")

    return SkinEdit(
        original_unlocked=original_unlocked,
        selected_skins=selected,
        newly_unlocked=newly_unlocked,
        new_unlocked=new_unlocked,
        total=catalog.total,
        affected_codes=affected_codes,
        locked_character_codes=locked_character_codes,
        changed=True,
        original=source,
        candidate=candidate,
        original_sha256=original_sha,
        candidate_sha256=sha256(candidate).hexdigest(),
        binary=binary,
        serialzed_version=version,
        changed_fields=tuple(f"{SKIN_PATH}.{ref.code}[{ref.index}]" for ref in newly_unlocked),
    )


def require_skin_write_compatibility(
    source: bytes, selections: object, candidate: bytes
) -> None:
    if prepare_skin_unlock_edit(source, selections).candidate != candidate:
        raise OutdatedSkinDraft(
            "El respaldo usa un borrador antiguo. Prepara de nuevo la selección antes de subirla."
        )
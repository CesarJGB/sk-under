"""Reconstrucción experimental a partir de JSON ya extraído del transporte."""

import math
import zlib
from dataclasses import dataclass, field
from hashlib import sha256
from typing import Literal

from .parsers.json_document import parse_json

type JsonValue = None | bool | int | float | str | list[JsonValue] | dict[str, JsonValue]
type JsonObject = dict[str, JsonValue]
type Encoding = Literal["json", "gzip"]
type SectionState = Literal["present", "null", "missing"]

MAX_INPUT_BYTES = 8 * 1024 * 1024
MAX_JSON_BYTES = 16 * 1024 * 1024
MAX_JSON_DEPTH = 64

OBJECT_SECTIONS = (
    "itemData",
    "statisticData",
    "settingData",
    "taskData",
    "seasonData",
    "mallReloadData",
    "monsterRiseData",
    "weaponEvolutionData",
    "miscData",
    "pvpData",
    "battlePassSaveData",
    "escapeSeasonData",
)
OPTIONAL_SECTIONS = (*OBJECT_SECTIONS, "maps", "sandboxConfig")
RECOGNIZED_FIELDS = frozenset(
    ("serialzedVersion", "cloudSaveId", "platformId", "gameData", *OPTIONAL_SECTIONS)
)


class CloudSaveError(ValueError):
    code = "cloud_save"


class AggregateFormatError(CloudSaveError):
    code = "invalid_aggregate"


class UnsupportedEncoding(CloudSaveError):
    code = "unknown_format"


class CopyLimitError(CloudSaveError):
    code = "size_limit"


@dataclass(frozen=True)
class CloudSaveGameData:
    serialzed_version: int
    cloud_save_id: str = field(repr=False)
    platform_id: str = field(repr=False)
    game_data: JsonObject = field(repr=False)
    optional_sections: JsonObject = field(repr=False)
    extra_fields: JsonObject = field(repr=False)


@dataclass(frozen=True)
class ReconstructedCloudSave:
    encoding: Encoding
    source_size: int
    source_sha256: str = field(repr=False)
    data: CloudSaveGameData = field(repr=False)

    def summary(self) -> dict[str, object]:
        sections: dict[str, SectionState] = {"gameData": "present"}
        for name in OPTIONAL_SECTIONS:
            if name not in self.data.optional_sections:
                sections[name] = "missing"
            elif self.data.optional_sections[name] is None:
                sections[name] = "null"
            else:
                sections[name] = "present"
        return {
            "experimental": True,
            "encoding": self.encoding,
            "serialzed_version": self.data.serialzed_version,
            "sections": sections,
        }


def _unpack(source: bytes) -> tuple[Encoding, bytes]:
    if not source.startswith(b"\x1f\x8b"):
        if len(source) > MAX_JSON_BYTES:
            raise CopyLimitError("El JSON supera el límite permitido.")
        if not source.lstrip(b" \t\r\n").startswith(b"{"):
            raise UnsupportedEncoding("Se esperaba un objeto JSON UTF-8 o gzip.")
        return "json", source

    decoder = zlib.decompressobj(wbits=16 + zlib.MAX_WBITS)
    try:
        document = decoder.decompress(source, MAX_JSON_BYTES + 1)
    except zlib.error:
        raise AggregateFormatError("El gzip está dañado.") from None
    if len(document) > MAX_JSON_BYTES:
        raise CopyLimitError("El JSON supera el límite permitido.")
    if not decoder.eof or decoder.unused_data:
        raise AggregateFormatError("El gzip está truncado o contiene bytes adicionales.")
    return "gzip", document


def _validate_json_tree(value: JsonValue, depth: int = 0) -> None:
    if depth > MAX_JSON_DEPTH:
        raise AggregateFormatError("El JSON supera la profundidad permitida.")
    if isinstance(value, float) and not math.isfinite(value):
        raise AggregateFormatError("El JSON contiene un número fuera de rango.")
    if isinstance(value, dict):
        for member in value.values():
            _validate_json_tree(member, depth + 1)
    elif isinstance(value, list):
        for member in value:
            _validate_json_tree(member, depth + 1)


def _reconstruct(document: bytes) -> CloudSaveGameData:
    try:
        root = parse_json(document)
    except (ValueError, RecursionError):
        raise AggregateFormatError("El documento no contiene JSON UTF-8 válido.") from None
    if not isinstance(root, dict):
        raise AggregateFormatError("Se esperaba un objeto JSON en la raíz.")
    _validate_json_tree(root)

    version = root.get("serialzedVersion")
    if type(version) is not int or version < 0:
        raise AggregateFormatError("Se requiere serialzedVersion como entero no negativo.")
    save_id = root.get("cloudSaveId")
    if not isinstance(save_id, str) or not save_id.strip():
        raise AggregateFormatError("Se requiere cloudSaveId como texto no vacío.")
    platform_id = root.get("platformId")
    if not isinstance(platform_id, str) or not platform_id.strip():
        raise AggregateFormatError("Se requiere platformId como texto no vacío.")
    game_data = root.get("gameData")
    if not isinstance(game_data, dict):
        raise AggregateFormatError("Se requiere gameData como objeto JSON.")
    for name in OBJECT_SECTIONS:
        section = root.get(name)
        if section is not None and not isinstance(section, dict):
            raise AggregateFormatError(f"La sección {name} debe ser un objeto JSON o nula.")

    return CloudSaveGameData(
        serialzed_version=version,
        cloud_save_id=save_id,
        platform_id=platform_id,
        game_data=game_data,
        optional_sections={name: root[name] for name in OPTIONAL_SECTIONS if name in root},
        extra_fields={name: value for name, value in root.items() if name not in RECOGNIZED_FIELDS},
    )


def unpack_cloud_save(source: bytes) -> tuple[Encoding, bytes]:
    """Expone el JSON interno de una copia ya delimitada.

    La edición de campos concretos necesita el documento exacto para comprobar
    que la serialización canónica conserva todos los bytes ajenos al cambio.
    """
    if len(source) > MAX_INPUT_BYTES:
        raise CopyLimitError("La entrada supera el límite permitido.")
    return _unpack(source)


def reconstruct_cloud_save(source: bytes) -> ReconstructedCloudSave:
    """Reconstruye una copia en memoria y calcula la huella de los bytes recibidos."""
    if len(source) > MAX_INPUT_BYTES:
        raise CopyLimitError("La entrada supera el límite permitido.")
    encoding, document = _unpack(source)
    data = _reconstruct(document)
    return ReconstructedCloudSave(encoding, len(source), sha256(source).hexdigest(), data)

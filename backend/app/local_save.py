"""Puente local para las secciones ``.data`` de Soul Knight.

El módulo no abre sockets ni depende de Android. Decodifica un archivo que el
titular ya posee, conserva sus bytes originales y, en el laboratorio, permite
una edición explícita sobre una copia. La compatibilidad con el cliente oficial
no se deduce de este roundtrip.
"""

from __future__ import annotations

import base64
import json
import os
import stat
from copy import deepcopy
from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path
from typing import Literal

from Crypto.Cipher import DES
from Crypto.Util.Padding import pad, unpad

from .cloud.lab import BinaryDiff, _changed_paths, _compatible, _is_within, binary_diff, format_path, parse_path
from .cloud_save import JsonValue
from .parsers.json_document import parse_json
from .parsers.real_save import SCHEMAS, ciphertext, decode_game_data, encode_game_data

type KeyRole = Literal["general", "statistics", "none"]
type SectionStatus = Literal["decoded", "plain_json", "opaque", "unknown"]
type LocalCodec = Literal["base64-des-cbc", "xor-json"]

MAX_LOCAL_FILE_BYTES = 8 * 1024 * 1024
MAX_BUNDLE_FILES = 64
MAX_BUNDLE_BYTES = 32 * 1024 * 1024
PROTECTED_TOP_LEVEL = frozenset(("AppVersion", "version", "gameVersion", "ChillyUid", "cloudSaveId", "platformId"))


def write_private_file(target: Path, data: bytes, *, overwrite: bool = False) -> Path:
    """Escribe un archivo nuevo con permisos 0600 sin seguir enlaces simbólicos."""
    flags = os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW
    flags |= os.O_TRUNC if overwrite else os.O_EXCL
    descriptor = os.open(target, flags, 0o600)
    try:
        view = memoryview(data)
        while view:
            written = os.write(descriptor, view)
            view = view[written:]
        os.fchmod(descriptor, 0o600)
    finally:
        os.close(descriptor)
    return target.absolute()


class LocalSaveError(ValueError):
    code = "local_save"


class LocalFormatError(LocalSaveError):
    code = "local_format"


class LocalVersionError(LocalSaveError):
    code = "unsupported_version"


class LocalLimitError(LocalSaveError):
    code = "size_limit"


class LocalEditError(LocalSaveError):
    code = "invalid_edit"


@dataclass(frozen=True)
class LocalSection:
    name: str
    kind: str
    document: dict[str, JsonValue] = field(repr=False)
    original: bytes = field(repr=False)
    plaintext: bytes = field(repr=False)
    key_role: KeyRole
    version: int | None = None
    codec: LocalCodec = "base64-des-cbc"

    @property
    def sha256(self) -> str:
        return sha256(self.original).hexdigest()

    def summary(self) -> dict[str, object]:
        return {
            "name": self.name,
            "kind": self.kind,
            "format": "xor-json" if self.codec == "xor-json" else "base64-des-cbc-json",
            "key": self.key_role,
            "version": self.version,
            "bytes": len(self.original),
            "sha256": self.sha256,
            "sections": sorted(self.document),
        }


@dataclass(frozen=True)
class LocalChange:
    path: str
    before: JsonValue
    after: JsonValue


@dataclass(frozen=True)
class LocalLabReport:
    kind: str
    changes: tuple[LocalChange, ...]
    binary: BinaryDiff
    unknown_fields_preserved: bool
    roundtrip: bool
    output: bytes = field(repr=False)

    def summary(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "changes": [
                {"path": change.path, "before": change.before, "after": change.after}
                for change in self.changes
            ],
            "binary": self.binary.as_dict(),
            "unknown_fields_preserved": self.unknown_fields_preserved,
            "roundtrip": self.roundtrip,
            "output_bytes": len(self.output),
            "output_sha256": sha256(self.output).hexdigest(),
        }


def kind_from_filename(name: str) -> str | None:
    base = Path(name).name
    for prefix in (
        "weapon_evolution_data", "escape_season_data", "mall_reload_data", "monsrise_data",
        "statistic", "item_data", "season_data", "misc_data", "pvp_data", "task",
        "setting", "bp_data", "game", "sandbox_config", "sandbox_maps",
    ):
        if base.startswith(prefix):
            return "statistic" if prefix == "statistic" else prefix
    return None


def _decrypt(data: bytes, key: bytes, iv: bytes) -> dict[str, JsonValue] | None:
    try:
        plain = unpad(DES.new(key, DES.MODE_CBC, iv).decrypt(data), DES.block_size)
        parsed = parse_json(plain)
        return parsed if isinstance(parsed, dict) else None
    except (ValueError, RecursionError):
        return None


def decode_local_section(
    data: bytes,
    *,
    general_key: bytes,
    statistics_key: bytes,
    iv: bytes,
    name: str = "",
    expected_kind: str | None = None,
) -> LocalSection | None:
    """Reconoce una sección local sin adivinar el esquema.

    Devuelve ``None`` para datos que no son Base64+DES-CBC+JSON o para esquemas
    ambiguos. Un marcador de versión conocido pero no admitido produce
    ``LocalVersionError``; una sección cifrada que no encaja en ningún esquema
    también se rechaza con ``LocalFormatError``.
    """
    if not 0 < len(data) <= MAX_LOCAL_FILE_BYTES:
        raise LocalLimitError("La sección local está vacía o supera el límite.")
    encrypted = ciphertext(data)
    if encrypted is None:
        # La forma de AboGameData es suficientemente específica para reconocer
        # game.data aunque el archivo se haya renombrado.
        game = decode_game_data(data)
        if game is not None:
            return LocalSection(
                name=Path(name).name or "game.data",
                kind="game_data",
                document=game,
                original=data,
                plaintext=json.dumps(game, ensure_ascii=False, separators=(",", ":")).encode(),
                key_role="none",
                version=int(game.get("gameVersion", 0)),
                codec="xor-json",
            )
        return None

    candidates: list[tuple[str, KeyRole, dict[str, JsonValue], bytes]] = []
    version_error: LocalVersionError | None = None
    for key_role, key in (("general", general_key), ("statistics", statistics_key)):
        document = _decrypt(encrypted, key, iv)
        if document is None:
            continue
        for kind, schema in SCHEMAS.items():
            if not schema.matches(document):
                continue
            if schema.version is not None:
                marker = schema.version[0]
                value = document.get(marker)
                if not schema.accepts_version(value):
                    version_error = LocalVersionError(
                        f"El marcador {marker} de {kind} no está en la cobertura verificada."
                    )
                    continue
            candidates.append((kind, key_role, document, encrypted))
        break

    if expected_kind is not None:
        preferred = [item for item in candidates if item[0] == expected_kind]
        if len(preferred) == 1:
            candidates = preferred
        elif not preferred and version_error is not None:
            raise version_error

    if len(candidates) != 1:
        if version_error is not None and not candidates:
            raise version_error
        return None

    kind, key_role, document, _ = candidates[0]
    schema = SCHEMAS[kind]
    version = None
    if schema.version is not None:
        version = int(document[schema.version[0]])
    return LocalSection(
        name=Path(name).name or kind,
        kind=kind,
        document=document,
        original=data,
        plaintext=json.dumps(document, ensure_ascii=False, separators=(",", ":")).encode(),
        key_role=key_role,
        version=version,
    )


def encode_local_section(
    document: dict[str, JsonValue], key: bytes, iv: bytes, *, codec: LocalCodec = "base64-des-cbc"
) -> bytes:
    if codec == "xor-json":
        return encode_game_data(document)
    plain = json.dumps(document, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return base64.b64encode(DES.new(key, DES.MODE_CBC, iv).encrypt(pad(plain, DES.block_size)))


class LocalSaveLab:
    """Copia de trabajo en memoria de una sección local ya decodificada."""

    def __init__(self, section: LocalSection, *, key: bytes, iv: bytes) -> None:
        self.section = section
        self._key = key
        self._iv = iv
        self._baseline = deepcopy(section.document)
        self._changes: list[LocalChange] = []

    @classmethod
    def open(
        cls,
        data: bytes,
        *,
        general_key: bytes,
        statistics_key: bytes,
        iv: bytes,
        name: str = "",
    ) -> LocalSaveLab:
        expected = kind_from_filename(name) if name else None
        section = decode_local_section(
            data,
            general_key=general_key,
            statistics_key=statistics_key,
            iv=iv,
            name=name,
            expected_kind=expected,
        )
        if section is None:
            raise LocalFormatError("El archivo no es una sección local reconocida.")
        key = statistics_key if section.key_role == "statistics" else (b"" if section.key_role == "none" else general_key)
        return cls(section, key=key, iv=iv)

    @property
    def document(self) -> dict[str, JsonValue]:
        return self.section.document

    @property
    def changes(self) -> tuple[LocalChange, ...]:
        return tuple(self._changes)

    def set(self, path: str, value: JsonValue) -> LocalChange:
        segments = parse_path(path)
        if segments[0] in PROTECTED_TOP_LEVEL:
            raise LocalEditError("El marcador de versión o identidad no se puede editar.")
        parent: JsonValue = self.document
        for segment in segments[:-1]:
            if isinstance(segment, int):
                if type(parent) is not list or not 0 <= segment < len(parent):
                    raise LocalEditError(f"La ruta no existe: {path}")
            else:
                if type(parent) is not dict or segment not in parent:
                    raise LocalEditError(f"La ruta no existe: {path}")
            parent = parent[segment]  # type: ignore[index]
        last = segments[-1]
        if isinstance(last, int):
            if type(parent) is not list or not 0 <= last < len(parent):
                raise LocalEditError(f"La ruta no existe: {path}")
            before = parent[last]
        else:
            if type(parent) is not dict or last not in parent:
                raise LocalEditError(f"La ruta no existe: {path}")
            before = parent[last]  # type: ignore[index]
        if type(before) in (dict, list):
            raise LocalEditError("Solo se editan valores escalares; no se reemplaza una colección completa.")
        if not _compatible(before, value):
            raise LocalEditError(f"El tipo de {path} no coincide con el valor enviado.")
        if before == value and type(before) is type(value):
            return LocalChange(path, deepcopy(before), deepcopy(before))
        parent[last] = value  # type: ignore[index]
        change = LocalChange(format_path(segments), deepcopy(before), deepcopy(value))
        self._changes.append(change)
        return change

    def serialize(self) -> bytes:
        if not self._changes:
            return self.section.original
        output = encode_local_section(self.document, self._key, self._iv, codec=self.section.codec)
        reopened = decode_local_section(
            output,
            general_key=self._key,
            statistics_key=self._key,
            iv=self._iv,
            name=self.section.name,
            expected_kind=self.section.kind,
        )
        if reopened is None or reopened.document != self.document:
            raise LocalEditError("La copia reabierta no coincide con la copia de trabajo.")
        return output

    def report(self) -> LocalLabReport:
        output = self.serialize()
        if not self._changes:
            reopened = self.section
        else:
            reopened = decode_local_section(
                output,
                general_key=self._key,
                statistics_key=self._key,
                iv=self._iv,
                name=self.section.name,
                expected_kind=self.section.kind,
            )
            if reopened is None or reopened.document != self.document:
                raise LocalEditError("La copia generada no se puede volver a abrir.")
        changed = _changed_paths(self._baseline, self.document)
        intended = [parse_path(change.path) for change in self._changes]
        if any(not any(_is_within(path, allowed) for allowed in intended) for path in changed):
            raise LocalEditError("Un cambio afectó a una ruta no solicitada.")
        preserved = all(
            value == _value_at(self._baseline, path)
            for path, value in _walk_document(self.document)
            if not any(_is_within(path, allowed) for allowed in intended)
        )
        return LocalLabReport(
            kind=self.section.kind,
            changes=self.changes,
            binary=binary_diff(self.section.original, output),
            unknown_fields_preserved=preserved,
            roundtrip=True,
            output=output,
        )

    def write(self, target: Path, *, overwrite: bool = False) -> LocalLabReport:
        report = self.report()
        write_private_file(target, report.output, overwrite=overwrite)
        return report


def _walk_document(value: JsonValue, prefix: tuple[str | int, ...] = ()):
    if isinstance(value, dict):
        for key, member in value.items():
            yield from _walk_document(member, (*prefix, key))
    elif isinstance(value, list):
        for index, member in enumerate(value):
            yield from _walk_document(member, (*prefix, index))
    else:
        yield prefix, value


def _value_at(document: JsonValue, path: tuple[str | int, ...]) -> JsonValue:
    current = document
    for segment in path:
        current = current[segment]  # type: ignore[index]
    return current


@dataclass(frozen=True)
class LocalFileSummary:
    name: str
    status: SectionStatus
    bytes: int
    sha256: str
    kind: str | None = None
    version: int | None = None
    top_level_keys: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "status": self.status,
            "bytes": self.bytes,
            "sha256": self.sha256,
            "kind": self.kind,
            "version": self.version,
            "top_level_keys": list(self.top_level_keys),
        }


@dataclass(frozen=True)
class LocalBundleSummary:
    directory: str
    files: tuple[LocalFileSummary, ...]
    total_bytes: int

    def as_dict(self) -> dict[str, object]:
        decoded = [item for item in self.files if item.status == "decoded"]
        return {
            "directory": self.directory,
            "total_bytes": self.total_bytes,
            "files": [item.as_dict() for item in self.files],
            "recognized": len(decoded),
            "unknown": len([item for item in self.files if item.status in ("unknown", "opaque")]),
            "kinds": sorted({item.kind for item in decoded if item.kind}),
        }


def _safe_regular_files(directory: Path) -> list[Path]:
    if not directory.is_dir():
        raise LocalFormatError("El proveedor requiere un directorio existente.")
    files: list[Path] = []
    with os.scandir(directory) as entries:
        for entry in entries:
            try:
                info = entry.stat(follow_symlinks=False)
            except OSError:
                continue
            if not stat.S_ISREG(info.st_mode):
                continue
            if not entry.name.endswith((".data", ".json")):
                continue
            files.append(Path(entry.path))
    files.sort(key=lambda item: item.name)
    if len(files) > MAX_BUNDLE_FILES:
        raise LocalLimitError("El directorio contiene demasiados archivos.")
    return files


def inspect_local_directory(
    directory: Path,
    *,
    general_key: bytes,
    statistics_key: bytes,
    iv: bytes,
) -> LocalBundleSummary:
    files = _safe_regular_files(directory)
    summaries: list[LocalFileSummary] = []
    total = 0
    for path in files:
        data = path.read_bytes()
        total += len(data)
        if total > MAX_BUNDLE_BYTES:
            raise LocalLimitError("El directorio supera el límite agregado.")
        if not 0 < len(data) <= MAX_LOCAL_FILE_BYTES:
            raise LocalLimitError("Un archivo del directorio está vacío o supera el límite.")
        digest = sha256(data).hexdigest()
        expected = kind_from_filename(path.name)
        try:
            section = decode_local_section(
                data,
                general_key=general_key,
                statistics_key=statistics_key,
                iv=iv,
                name=path.name,
                expected_kind=expected,
            )
        except LocalVersionError:
            summaries.append(LocalFileSummary(path.name, "unknown", len(data), digest, expected, None, ()))
            continue
        if section is not None:
            summaries.append(
                LocalFileSummary(
                    path.name, "decoded", len(data), digest, section.kind, section.version,
                    tuple(sorted(section.document)),
                )
            )
            continue
        if data.lstrip().startswith(b"{") and expected in ("sandbox_config", "sandbox_maps"):
            try:
                parsed = parse_json(data)
            except (ValueError, RecursionError):
                parsed = None
            if isinstance(parsed, dict):
                summaries.append(
                    LocalFileSummary(path.name, "plain_json", len(data), digest, expected, None, tuple(sorted(parsed)))
                )
                continue
        summaries.append(LocalFileSummary(path.name, "opaque" if expected == "game" else "unknown", len(data), digest, expected, None, ()))
    return LocalBundleSummary(str(directory.resolve()), tuple(summaries), total)

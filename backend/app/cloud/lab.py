"""Laboratorio local de edición y comparación de un agregado ya suministrado.

Nunca escribe el archivo de entrada. Trabaja sobre bytes en memoria, conserva
los campos desconocidos y exige que cada cambio respete el tipo JSON original.
La serialización se vuelve a validar antes de entregar una copia.
"""

from __future__ import annotations

import gzip
import json
from contextvars import ContextVar
from copy import deepcopy
from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path
from typing import Literal

from ..cloud_save import (
    MAX_INPUT_BYTES,
    RECOGNIZED_FIELDS,
    AggregateFormatError,
    CopyLimitError,
    JsonValue,
    _unpack,
    reconstruct_cloud_save,
)
from ..parsers.json_document import parse_json

type Encoding = Literal["json", "gzip"]
type JsonPath = tuple[str | int, ...]


class LabError(ValueError):
    code = "lab_error"


class LabPathError(LabError):
    code = "invalid_path"


class LabTypeError(LabError):
    code = "type_mismatch"


class LabVerificationError(LabError):
    code = "verification_failed"


@dataclass(frozen=True)
class LabChange:
    path: str
    before: JsonValue
    after: JsonValue

    def as_dict(self) -> dict[str, object]:
        return {"path": self.path, "before": self.before, "after": self.after}


# La composición unificada solo conserva la diferencia final. Los editores
# granulares siguen calculándola por defecto, pero durante el encadenamiento se
# suprime para no recorrer catorce veces los mismos megabytes.
_SUPPRESS_INTERMEDIATE_DIFF: ContextVar[bool] = ContextVar(
    "sk_under_suppress_intermediate_diff", default=False
)


@dataclass(frozen=True)
class BinaryDiff:
    original_size: int
    modified_size: int
    first_difference: int | None
    common_prefix: int
    common_suffix: int
    changed_original_bytes: int
    changed_modified_bytes: int
    original_sha256: str
    modified_sha256: str

    def as_dict(self) -> dict[str, object]:
        return {
            "original_size": self.original_size,
            "modified_size": self.modified_size,
            "first_difference": self.first_difference,
            "common_prefix": self.common_prefix,
            "common_suffix": self.common_suffix,
            "changed_original_bytes": self.changed_original_bytes,
            "changed_modified_bytes": self.changed_modified_bytes,
            "original_sha256": self.original_sha256,
            "modified_sha256": self.modified_sha256,
        }


@dataclass(frozen=True)
class LabReport:
    encoding: Encoding
    changes: tuple[LabChange, ...]
    binary: BinaryDiff
    unknown_fields_preserved: bool
    roundtrip: bool
    output_size: int
    output_sha256: str
    output_data: bytes = field(repr=False)

    def as_dict(self) -> dict[str, object]:
        return {
            "encoding": self.encoding,
            "changes": [change.as_dict() for change in self.changes],
            "binary": self.binary.as_dict(),
            "unknown_fields_preserved": self.unknown_fields_preserved,
            "roundtrip": self.roundtrip,
            "output_size": self.output_size,
            "output_sha256": self.output_sha256,
        }


def parse_path(path: str) -> JsonPath:
    if not isinstance(path, str) or not path:
        raise LabPathError("La ruta está vacía.")
    if path.startswith(".") or path.endswith(".") or ".." in path or ".[" in path:
        raise LabPathError("La ruta contiene un separador vacío.")
    segments: list[str | int] = []
    index = 0
    length = len(path)
    while index < length:
        if path[index] == ".":
            index += 1
            continue
        if path[index] == "[":
            end = path.find("]", index + 1)
            if end < 0 or not path[index + 1 : end].isdigit():
                raise LabPathError("Índice de lista inválido.")
            segments.append(int(path[index + 1 : end]))
            index = end + 1
            continue
        start = index
        while index < length and path[index] not in ".[":
            index += 1
        name = path[start:index]
        if not name:
            raise LabPathError("Segmento vacío en la ruta.")
        segments.append(name)
    if not segments:
        raise LabPathError("La ruta no contiene segmentos.")
    return tuple(segments)


def format_path(segments: JsonPath) -> str:
    text = ""
    for segment in segments:
        if isinstance(segment, int):
            text += f"[{segment}]"
        else:
            text += ("." if text else "") + segment
    return text


def _compatible(before: JsonValue, after: JsonValue) -> bool:
    if isinstance(before, bool) or isinstance(after, bool):
        return type(before) is type(after)
    if type(before) is int:
        return type(after) is int
    if type(before) is float:
        return type(after) in (int, float) and not isinstance(after, bool)
    if type(before) is str:
        return type(after) is str
    if before is None:
        return after is None
    if type(before) is list:
        return type(after) is list
    if type(before) is dict:
        return type(after) is dict
    return False


def _walk(value: JsonValue, prefix: JsonPath = ()) -> list[tuple[JsonPath, JsonValue]]:
    leaves: list[tuple[JsonPath, JsonValue]] = []
    if isinstance(value, dict):
        for key, member in value.items():
            leaves.extend(_walk(member, (*prefix, key)))
    elif isinstance(value, list):
        for index, member in enumerate(value):
            leaves.extend(_walk(member, (*prefix, index)))
    else:
        leaves.append((prefix, value))
    return leaves


def _leaf_map(value: JsonValue) -> dict[JsonPath, JsonValue]:
    return dict(_walk(value))


def _changed_paths(before: JsonValue, after: JsonValue) -> list[JsonPath]:
    paths: list[JsonPath] = []
    if isinstance(before, dict) and isinstance(after, dict):
        for key in before.keys() | after.keys():
            if key not in before or key not in after:
                paths.append((key,))
            else:
                paths.extend((key, *rest) for rest in _changed_paths(before[key], after[key]))
        return paths
    if isinstance(before, list) and isinstance(after, list):
        for index in range(max(len(before), len(after))):
            if index >= len(before) or index >= len(after):
                paths.append((index,))
            else:
                paths.extend((index, *rest) for rest in _changed_paths(before[index], after[index]))
        return paths
    if before != after or type(before) is not type(after):
        paths.append(())
    return paths


def _is_within(path: JsonPath, allowed: JsonPath) -> bool:
    return path[: len(allowed)] == allowed


def suppress_intermediate_diff(enabled: bool) -> object:
    """Activa o desactiva la diferencia binaria intermedia en este contexto."""

    return _SUPPRESS_INTERMEDIATE_DIFF.set(enabled)


def reset_intermediate_diff(token: object) -> None:
    _SUPPRESS_INTERMEDIATE_DIFF.reset(token)  # type: ignore[arg-type]


def binary_diff(before: bytes, after: bytes) -> BinaryDiff:
    if _SUPPRESS_INTERMEDIATE_DIFF.get():
        return BinaryDiff(
            original_size=len(before),
            modified_size=len(after),
            first_difference=None if before == after else 0,
            common_prefix=0,
            common_suffix=0,
            changed_original_bytes=0,
            changed_modified_bytes=0,
            original_sha256=sha256(before).hexdigest(),
            modified_sha256=sha256(after).hexdigest(),
        )
    prefix = 0
    limit = min(len(before), len(after))
    while prefix < limit and before[prefix] == after[prefix]:
        prefix += 1
    suffix = 0
    max_suffix = limit - prefix
    while suffix < max_suffix and before[-1 - suffix] == after[-1 - suffix]:
        suffix += 1
    first = prefix if prefix < max(len(before), len(after)) else None
    return BinaryDiff(
        original_size=len(before),
        modified_size=len(after),
        first_difference=first,
        common_prefix=prefix,
        common_suffix=suffix,
        changed_original_bytes=len(before) - prefix - suffix,
        changed_modified_bytes=len(after) - prefix - suffix,
        original_sha256=sha256(before).hexdigest(),
        modified_sha256=sha256(after).hexdigest(),
    )


class SaveLab:
    """Copia de trabajo en memoria de un agregado JSON o gzip."""

    def __init__(self, original: bytes, encoding: Encoding, document: dict[str, JsonValue]) -> None:
        self.original = original
        self.encoding = encoding
        self.document = document
        self._baseline = deepcopy(document)
        self._changes: list[LabChange] = []

    @classmethod
    def open(cls, payload: bytes) -> SaveLab:
        if len(payload) > MAX_INPUT_BYTES:
            raise CopyLimitError("La entrada supera el límite permitido.")
        if not payload:
            raise CopyLimitError("La copia está vacía.")
        encoding, document = _unpack(payload)
        try:
            tree = parse_json(document)
        except (ValueError, RecursionError):
            raise AggregateFormatError("El documento no contiene JSON UTF-8 válido.") from None
        if not isinstance(tree, dict):
            raise AggregateFormatError("Se esperaba un objeto JSON en la raíz.")
        # La validación de contrato se hace antes de permitir cualquier cambio.
        reconstruct_cloud_save(payload)
        return cls(payload, encoding, tree)

    @property
    def changes(self) -> tuple[LabChange, ...]:
        return tuple(self._changes)

    def set(self, path: str, value: JsonValue) -> LabChange:
        segments = parse_path(path)
        if segments[0] not in RECOGNIZED_FIELDS:
            raise LabPathError("Solo se editan secciones reconocidas del agregado.")
        parent: JsonValue = self.document
        for segment in segments[:-1]:
            if isinstance(segment, int):
                if type(parent) is not list or not 0 <= segment < len(parent):
                    raise LabPathError(f"La ruta no existe: {path}")
            else:
                if type(parent) is not dict or segment not in parent:
                    raise LabPathError(f"La ruta no existe: {path}")
            parent = parent[segment]  # type: ignore[index]
        last = segments[-1]
        if isinstance(last, int):
            if type(parent) is not list or not 0 <= last < len(parent):
                raise LabPathError(f"La ruta no existe: {path}")
            before = parent[last]
        else:
            if type(parent) is not dict or last not in parent:
                raise LabPathError(f"La ruta no existe: {path}")
            before = parent[last]  # type: ignore[index]
        if not _compatible(before, value):
            raise LabTypeError(f"El tipo de {path} no coincide con el valor enviado.")
        if not self._same_type_strict(before, value) and type(before) is float and type(value) is int:
            value = float(value)
        if before == value and type(before) is type(value):
            return LabChange(path, deepcopy(before), deepcopy(before))
        parent[last] = value  # type: ignore[index]
        change = LabChange(format_path(segments), deepcopy(before), deepcopy(value))
        self._changes.append(change)
        return change

    @staticmethod
    def _same_type_strict(before: JsonValue, after: JsonValue) -> bool:
        return type(before) is type(after)

    def serialize(self, *, encoding: Encoding | Literal["same"] = "same") -> bytes:
        try:
            document = json.dumps(
                self.document,
                ensure_ascii=False,
                separators=(",", ":"),
                allow_nan=False,
            ).encode("utf-8")
            reconstruct_cloud_save(document)
        except (TypeError, ValueError) as exc:
            raise LabVerificationError("El documento editado no se puede serializar o validar.") from exc
        output_encoding: Encoding = self.encoding if encoding == "same" else encoding
        if not self._changes and output_encoding == self.encoding:
            return self.original
        return gzip.compress(document, mtime=0) if output_encoding == "gzip" else document

    def report(self, *, encoding: Encoding | Literal["same"] = "same") -> LabReport:
        output = self.serialize(encoding=encoding)
        try:
            reopened = parse_json(_unpack(output)[1])
        except (ValueError, RecursionError):
            raise LabVerificationError("La copia generada no se puede volver a abrir.") from None
        if reopened != self.document:
            raise LabVerificationError("La copia reabierta no coincide con la copia de trabajo.")
        changed = _changed_paths(self._baseline, self.document)
        intended = [parse_path(change.path) for change in self._changes]
        if any(not any(_is_within(path, allowed) for allowed in intended) for path in changed):
            raise LabVerificationError("Un cambio afectó a una ruta no solicitada.")
        unknown = set(self._baseline) - RECOGNIZED_FIELDS
        before_unknown = {
            path: value
            for path, value in _leaf_map(self._baseline).items()
            if path and path[0] in unknown
        }
        after_unknown = {
            path: value
            for path, value in _leaf_map(self.document).items()
            if path and path[0] in unknown
        }
        preserved = before_unknown == after_unknown
        return LabReport(
            encoding=self.encoding if encoding == "same" else encoding,
            changes=self.changes,
            binary=binary_diff(self.original, output),
            unknown_fields_preserved=preserved,
            roundtrip=True,
            output_size=len(output),
            output_sha256=sha256(output).hexdigest(),
            output_data=output,
        )

    def write(self, target: Path, *, encoding: Encoding | Literal["same"] = "same", overwrite: bool = False) -> LabReport:
        report = self.report(encoding=encoding)
        target = target.resolve()
        if target.exists() and not overwrite:
            raise FileExistsError(f"El destino ya existe: {target}")
        target.write_bytes(report.output_data)
        return report

"""Importación local de un agregado ya extraído del transporte."""

import argparse
import json
import os
import stat
import sys
from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path
from typing import Protocol

from .cloud.validator import CopyIntegrityError, verify_copy_bytes
from .cloud_save import (
    MAX_INPUT_BYTES,
    OPTIONAL_SECTIONS,
    CloudSaveError,
    CopyLimitError,
    JsonValue,
    ReconstructedCloudSave,
    reconstruct_cloud_save,
)


class CopySourceError(CloudSaveError):
    code = "unreadable_source"


class MissingSection(CloudSaveError):
    code = "absent_section"


@dataclass(frozen=True)
class CopyMetadata:
    """Tamaño y huella esperados de la misma revisión que se va a leer."""

    size: int
    sha256: str = field(repr=False)


class AggregateSource(Protocol):
    """Una instancia representa una copia concreta ya extraída del transporte."""

    def metadata(self) -> CopyMetadata: ...

    def read(self, limit: int) -> bytes:
        """Devuelve la copia completa o falla si supera el límite."""
        ...


@dataclass(frozen=True)
class LocalFileSource:
    path: Path = field(repr=False)
    expected: CopyMetadata | None = None

    def metadata(self) -> CopyMetadata:
        if self.expected is not None:
            return self.expected
        snapshot = self.read(MAX_INPUT_BYTES)
        return CopyMetadata(len(snapshot), sha256(snapshot).hexdigest())

    def read(self, limit: int) -> bytes:
        if not 0 <= limit <= MAX_INPUT_BYTES:
            raise CopyLimitError("Tamaño de copia fuera de los límites.")
        try:
            # O_NONBLOCK permite rechazar también un FIFO sin esperar a un escritor.
            with open(self.path, "rb", opener=lambda p, flags: os.open(p, flags | os.O_NONBLOCK)) as stream:
                info = os.fstat(stream.fileno())
                if not stat.S_ISREG(info.st_mode):
                    raise CopySourceError("Se requiere un archivo regular.")
                if info.st_size > MAX_INPUT_BYTES:
                    raise CopyLimitError("La entrada supera el límite permitido.")
                payload = stream.read(limit + 1)
        except OSError:
            raise CopySourceError("No se pudo leer la copia local.") from None
        if len(payload) > limit:
            if limit == MAX_INPUT_BYTES:
                raise CopyLimitError("La entrada supera el límite permitido.")
            raise CopyIntegrityError("Los bytes difieren de los metadatos de la copia.")
        return payload


@dataclass(frozen=True)
class ImportedCopy:
    original: bytes = field(repr=False)
    aggregate: ReconstructedCloudSave

    def section(self, name: str) -> JsonValue:
        data = self.aggregate.data
        if name == "gameData":
            return data.game_data
        if name in data.optional_sections:
            return data.optional_sections[name]
        raise MissingSection("La sección solicitada está ausente o no está reconocida.")


def import_copy(source: AggregateSource) -> ImportedCopy:
    metadata = source.metadata()
    if type(metadata.size) is not int or not 0 < metadata.size <= MAX_INPUT_BYTES:
        raise CopyLimitError("Tamaño de copia fuera de los límites.")
    payload = source.read(metadata.size)
    verify_copy_bytes(payload, metadata)
    return ImportedCopy(payload, reconstruct_cloud_save(payload))


def summarize_copy(source: AggregateSource) -> dict[str, object]:
    return import_copy(source).aggregate.summary()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archivo", type=Path)
    parser.add_argument("--size", type=int, help="Tamaño esperado del original.")
    parser.add_argument("--sha256", help="SHA-256 esperado del original en hexadecimal.")
    parser.add_argument("--section", choices=("gameData", *OPTIONAL_SECTIONS),
                        help="Emitir el contenido JSON de esta sección.")
    args = parser.parse_args()
    if (args.size is None) != (args.sha256 is None):
        parser.error("--size y --sha256 deben indicarse juntos")
    expected = None if args.size is None else CopyMetadata(args.size, args.sha256.lower())
    try:
        copy = import_copy(LocalFileSource(args.archivo, expected))
        output = copy.section(args.section) if args.section else copy.aggregate.summary()
    except CloudSaveError as exc:
        print(json.dumps({"error": exc.code, "message": str(exc)}), file=sys.stderr)
        return 1
    print(json.dumps(output, allow_nan=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())

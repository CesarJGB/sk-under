"""Verificación de tamaño, huella y formato de una copia recibida.

La verificación ocurre antes de interpretar el JSON. Un tamaño o un SHA-256
distintos de la revisión anunciada producen un error tipado; la copia original
no se modifica y no se publica su contenido.
"""

from dataclasses import dataclass, field
from hashlib import sha256
from typing import Protocol

from ..cloud_save import (
    MAX_INPUT_BYTES,
    CloudSaveError,
    CopyLimitError,
    ReconstructedCloudSave,
)
from .decoder import DecodedCopy, DetectedFormat, decode_copy


class CopyIntegrityError(CloudSaveError):
    code = "integrity_mismatch"


class DeclaredRevision(Protocol):
    size: int
    sha256: str


@dataclass(frozen=True)
class ValidatedCopy:
    format: DetectedFormat
    aggregate: ReconstructedCloudSave
    original: bytes = field(repr=False)


def verify_copy_bytes(
    payload: bytes,
    expected: DeclaredRevision | None = None,
    *,
    limit: int = MAX_INPUT_BYTES,
) -> None:
    """Comprueba límites y, si existe, la revisión anunciada."""
    if type(limit) is not int or not 0 < limit <= MAX_INPUT_BYTES:
        raise CopyLimitError("Tamaño de copia fuera de los límites.")
    if expected is None:
        if not payload or len(payload) > limit:
            raise CopyLimitError("Tamaño de copia fuera de los límites.")
        return
    if type(expected.size) is not int or not 0 < expected.size <= limit:
        raise CopyLimitError("Tamaño de copia fuera de los límites.")
    if len(payload) != expected.size or sha256(payload).hexdigest() != expected.sha256:
        raise CopyIntegrityError("Los bytes difieren de los metadatos de la copia.")


def validate_payload(
    payload: bytes,
    *,
    expected: DeclaredRevision | None = None,
    limit: int = MAX_INPUT_BYTES,
) -> ValidatedCopy:
    """Verifica la copia y la decodifica sin llamadas externas."""
    verify_copy_bytes(payload, expected, limit=limit)
    decoded: DecodedCopy = decode_copy(payload)
    return ValidatedCopy(decoded.format, decoded.aggregate, decoded.original)

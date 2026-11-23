"""Entrada de solo lectura para una fuente de agregados ya autorizada."""

from dataclasses import dataclass, field
from hashlib import sha256
from typing import Protocol

from .cloud_save import MAX_INPUT_BYTES, CloudSaveError, reconstruct_cloud_save


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


def summarize_copy(source: AggregateSource) -> dict[str, object]:
    metadata = source.metadata()
    if not 0 < metadata.size <= MAX_INPUT_BYTES:
        raise CloudSaveError("Tamaño de copia fuera de los límites.")
    payload = source.read(metadata.size)
    if len(payload) != metadata.size or sha256(payload).hexdigest() != metadata.sha256:
        raise CloudSaveError("Los bytes difieren de los metadatos de la copia.")
    return reconstruct_cloud_save(payload).summary()

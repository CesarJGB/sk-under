"""Contratos de transporte para una copia concreta de Soul Knight.

No hay implementaciones de red. `DisabledRemoteTransport` representa la
situación actual: el proveedor no ha publicado una interfaz delegada y este
repositorio no debe llamar a endpoints privados. `SimulatedProviderTransport`
lee un archivo local y entrega un sobre con la misma forma que usaría un
conector futuro, de modo que el resto del flujo pueda probarse sin Android.
"""

import os
import stat
from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path
from typing import Protocol

from ..cloud_save import MAX_INPUT_BYTES, CloudSaveError, CopyLimitError


class TransportError(CloudSaveError):
    code = "transport_error"


class RemoteTransportDisabled(TransportError):
    code = "transport_disabled"


class TransportUnavailable(TransportError):
    code = "transport_unavailable"


@dataclass(frozen=True)
class RevisionMetadata:
    """Declaración de la revisión entregada por un transporte.

    `revision` es una etiqueta opaca del proveedor. No se interpreta como una
    versión del juego ni como una fecha. `sha256` se calcula sobre `payload`,
    los bytes exactos que el importador debe verificar.
    """

    revision: str
    size: int
    sha256: str = field(repr=False)
    media_type: str = "application/octet-stream"


@dataclass(frozen=True)
class TransportEnvelope:
    metadata: RevisionMetadata
    payload: bytes = field(repr=False)


class CloudTransport(Protocol):
    """Entrega la última revisión disponible o falla con un error tipado."""

    def fetch_latest(self, limit: int) -> TransportEnvelope:
        """Devuelve la copia completa sin superar `limit`."""
        ...


@dataclass(frozen=True)
class DisabledRemoteTransport:
    """Transporte remoto cerrado por falta de una interfaz autorizada."""

    reason: str = (
        "No existe una interfaz remota documentada y autorizada del proveedor. "
        "El transporte permanece deshabilitado."
    )

    def fetch_latest(self, limit: int) -> TransportEnvelope:
        raise RemoteTransportDisabled(self.reason)


@dataclass(frozen=True)
class SimulatedProviderTransport:
    """Proveedor local de integración. No abre sockets ni usa Android.

    `declared` permite simular una revisión anunciada por un proveedor. Si se
    omite, el sobre se calcula a partir del archivo. La verificación de tamaño
    y SHA-256 ocurre en el validador, no aquí.
    """

    path: Path = field(repr=False)
    revision: str = "simulado-1"
    media_type: str = "application/octet-stream"
    declared: RevisionMetadata | None = None

    def fetch_latest(self, limit: int) -> TransportEnvelope:
        if type(limit) is not int or not 0 < limit <= MAX_INPUT_BYTES:
            raise CopyLimitError("Tamaño de copia fuera de los límites.")
        try:
            # O_NONBLOCK también rechaza un FIFO sin esperar a un escritor.
            with open(
                self.path, "rb", opener=lambda path, flags: os.open(path, flags | os.O_NONBLOCK)
            ) as stream:
                info = os.fstat(stream.fileno())
                if not stat.S_ISREG(info.st_mode):
                    raise TransportUnavailable("Se requiere un archivo regular.")
                if info.st_size > limit:
                    raise CopyLimitError("La entrada supera el límite permitido.")
                payload = stream.read(limit + 1)
        except OSError:
            raise TransportUnavailable("No se pudo leer la copia local.") from None
        if len(payload) > limit:
            raise CopyLimitError("La entrada supera el límite permitido.")

        metadata = self.declared or RevisionMetadata(
            revision=self.revision,
            size=len(payload),
            sha256=sha256(payload).hexdigest(),
            media_type=self.media_type,
        )
        return TransportEnvelope(metadata=metadata, payload=payload)

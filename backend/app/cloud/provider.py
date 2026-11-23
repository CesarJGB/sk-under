"""Proveedores de adquisición de una copia de nube autorizada.

Este módulo separa tres cosas que no deben confundirse:

* ``DisabledCloudSaveProvider``: estado por defecto. No abre sockets y falla
  con un error tipado.
* ``LocalFixtureCloudSaveProvider``: lee una copia ya extraída para probar el
  flujo en Linux. No es una descarga remota.
* ``GatewayCloudSaveProvider``: prototipo de solo lectura para el gateway
  oficial. Requiere un token de juego que el titular debe aportar fuera de
  banda. El camino de éxito no se verificó contra el servicio real: la
  estructura exacta de la respuesta sigue siendo una hipótesis etiquetada.

Ninguna implementación escribe en la nube, automatiza el login ni desactiva la
verificación TLS. Los tokens y el contenido de la partida no se incluyen en
``repr`` ni en los resúmenes.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path
from typing import Protocol
from urllib.parse import urlsplit

from ..cloud_import import CopyMetadata, LocalFileSource
from ..cloud_save import MAX_INPUT_BYTES, CloudSaveError, CopyLimitError, reconstruct_cloud_save

type Fetch = Callable[[str, dict[str, str], float], tuple[int, bytes]]


class CloudProviderError(CloudSaveError):
    code = "cloud_provider_error"


class CloudProviderDisabled(CloudProviderError):
    code = "cloud_provider_disabled"


class CloudProviderUnauthenticated(CloudProviderError):
    code = "cloud_provider_unauthenticated"


class CloudProviderUnavailable(CloudProviderError):
    code = "cloud_provider_unavailable"


class CloudProviderProtocolError(CloudProviderError):
    code = "cloud_provider_protocol"


@dataclass(frozen=True)
class CloudSaveMetadata:
    """Revisión opaca y huella de los bytes que se van a entregar."""

    revision: str
    size: int
    sha256: str = field(repr=False)
    source: str = "remote"
    media_type: str = "application/json"

    def summary(self) -> dict[str, object]:
        return {
            "revision": self.revision,
            "size": self.size,
            "source": self.source,
            "media_type": self.media_type,
        }


@dataclass(frozen=True)
class AcquiredCloudSave:
    metadata: CloudSaveMetadata
    payload: bytes = field(repr=False)

    def __post_init__(self) -> None:
        if not self.payload:
            raise CopyLimitError("La copia adquirida está vacía.")
        if len(self.payload) != self.metadata.size:
            raise CloudProviderProtocolError("El tamaño adquirido no coincide con sus metadatos.")
        if sha256(self.payload).hexdigest() != self.metadata.sha256:
            raise CloudProviderProtocolError("La huella adquirida no coincide con sus metadatos.")

    def summary(self) -> dict[str, object]:
        return self.metadata.summary()


class CloudSaveAcquisitionProvider(Protocol):
    """Obtiene metadatos y descarga una copia autorizada, sin escribir."""

    def metadata(self) -> CloudSaveMetadata: ...

    def download(self, limit: int = MAX_INPUT_BYTES) -> AcquiredCloudSave: ...


@dataclass(frozen=True)
class DisabledCloudSaveProvider:
    """Proveedor por defecto: no hay una interfaz remota verificada."""

    reason: str = (
        "No se confirmó el contrato de descarga de CloudSaveGameData. "
        "La adquisición remota permanece deshabilitada."
    )

    def metadata(self) -> CloudSaveMetadata:
        raise CloudProviderDisabled(self.reason)

    def download(self, limit: int = MAX_INPUT_BYTES) -> AcquiredCloudSave:
        raise CloudProviderDisabled(self.reason)


@dataclass(frozen=True)
class LocalFixtureCloudSaveProvider:
    """Copia ya extraída, para pruebas y para el flujo local de Linux.

    La etiqueta ``source="fixture"`` evita presentarla como una descarga. El
    archivo se lee con las mismas defensas que el resto del puente: archivo
    regular, sin enlaces simbólicos y con límite estricto.
    """

    path: Path = field(repr=False)
    revision: str = "fixture-local"

    def _source(self) -> LocalFileSource:
        return LocalFileSource(self.path)

    def metadata(self) -> CloudSaveMetadata:
        expected = self._source().metadata()
        return CloudSaveMetadata(
            revision=self.revision,
            size=expected.size,
            sha256=expected.sha256,
            source="fixture",
        )

    def download(self, limit: int = MAX_INPUT_BYTES) -> AcquiredCloudSave:
        if type(limit) is not int or not 0 < limit <= MAX_INPUT_BYTES:
            raise CopyLimitError("Tamaño de copia fuera de los límites.")
        source = self._source()
        if source.metadata().size > limit:
            raise CopyLimitError("La entrada supera el límite permitido.")
        payload = source.read(limit)
        metadata = CloudSaveMetadata(
            revision=self.revision,
            size=len(payload),
            sha256=sha256(payload).hexdigest(),
            source="fixture",
        )
        return AcquiredCloudSave(metadata, payload)


def _urllib_fetch(url: str, headers: dict[str, str], timeout: float) -> tuple[int, bytes]:
    """GET con la verificación TLS por defecto de la plataforma."""
    request = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read(MAX_INPUT_BYTES + 1)
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read(MAX_INPUT_BYTES + 1)


def _error_code(document: object) -> int | None:
    if not isinstance(document, dict):
        return None
    for key in ("errorCode", "error", "code"):
        value = document.get(key)
        if type(value) is int:
            return value
    return None


@dataclass(frozen=True)
class GatewayCloudSaveProvider:
    """Prototipo de solo lectura contra el gateway oficial.

    ``path`` se deja configurable porque la ruta exacta de descarga
    (``/Backup/GetBlobSave`` o ``/BlobSave/Download``) no se verificó con una
    respuesta auténtica. ``fetch`` permite probar el proveedor con un servidor
    sintético sin tocar el servicio real.

    El token de juego se recibe ya emitido por el cliente oficial. Este módulo
    no implementa login, no guarda el token y no lo escribe en errores.
    """

    token: str = field(repr=False)
    base_url: str = "https://api-gateway.soulknight.chillyroom.com"
    path: str = "/Backup/GetBlobSave"
    timeout: float = 20.0
    fetch: Fetch = field(default=_urllib_fetch, repr=False, compare=False)

    def __post_init__(self) -> None:
        if not isinstance(self.token, str) or not self.token.strip():
            raise CloudProviderUnauthenticated("Falta el token de juego autorizado.")
        if not isinstance(self.base_url, str):
            raise CloudProviderProtocolError("El gateway debe ser una URL.")
        parsed = urlsplit(self.base_url)
        loopback_http = parsed.scheme == "http" and parsed.hostname in {"127.0.0.1", "localhost"}
        if not (parsed.scheme == "https" or loopback_http):
            raise CloudProviderProtocolError("El gateway debe usar HTTPS.")
        if (
            not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
        ):
            raise CloudProviderProtocolError("La URL del gateway no es válida.")
        if not isinstance(self.path, str) or not self.path.startswith("/"):
            raise CloudProviderProtocolError("La ruta del gateway no es válida.")
        if (
            isinstance(self.timeout, bool)
            or not isinstance(self.timeout, (int, float))
            or not 0 < self.timeout <= 60
        ):
            raise CloudProviderProtocolError("El tiempo de espera no es válido.")

    def _request(self, limit: int) -> bytes:
        if type(limit) is not int or not 0 < limit <= MAX_INPUT_BYTES:
            raise CopyLimitError("Tamaño de copia fuera de los límites.")
        url = self.base_url.rstrip("/") + self.path
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json",
            "User-Agent": "SK-Under/phase5-7 read-only",
        }
        try:
            status, body = self.fetch(url, headers, self.timeout)
        except (OSError, urllib.error.URLError) as exc:
            raise CloudProviderUnavailable("No se pudo contactar con el gateway.") from exc
        if len(body) > limit:
            raise CopyLimitError("La respuesta supera el límite permitido.")
        if status in (401, 403):
            raise CloudProviderUnauthenticated("El gateway rechazó el token de juego.")
        if status != 200:
            try:
                document = json.loads(body)
            except (UnicodeDecodeError, json.JSONDecodeError):
                document = None
            if _error_code(document) in (10001, 401, 403):
                raise CloudProviderUnauthenticated("El gateway rechazó el token de juego.")
            if status == 404:
                raise CloudProviderProtocolError("La ruta de descarga no existe en el gateway.")
            raise CloudProviderUnavailable(f"El gateway respondió con estado {status}.")
        return body

    def _payload_from_body(self, body: bytes) -> bytes:
        try:
            document = json.loads(body)
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise CloudProviderProtocolError("La respuesta del gateway no es JSON.") from None
        if isinstance(document, dict) and document.get("ok") is False:
            code = _error_code(document)
            if code in (10001, 401, 403):
                raise CloudProviderUnauthenticated("El gateway rechazó el token de juego.")
            raise CloudProviderUnavailable("El gateway devolvió un error.")
        if isinstance(document, dict):
            for key in ("data", "Data"):
                value = document.get(key)
                if isinstance(value, str):
                    return value.encode("utf-8")
                if isinstance(value, dict):
                    return json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8")
        if isinstance(document, dict) and "serialzedVersion" in document:
            return body
        raise CloudProviderProtocolError("La respuesta no contiene una copia reconocible.")

    def download(self, limit: int = MAX_INPUT_BYTES) -> AcquiredCloudSave:
        payload = self._payload_from_body(self._request(limit))
        if not payload or len(payload) > limit:
            raise CopyLimitError("La copia supera el límite permitido.")
        # Un 200 o un campo "data" por sí solos no identifican una copia.
        # La validación estructural tampoco demuestra que la respuesta sea
        # auténtica o que contenga progreso: el endpoint sigue sin verificar.
        try:
            reconstruct_cloud_save(payload)
        except CloudSaveError:
            raise CloudProviderProtocolError("La respuesta no contiene un agregado de copia válido.") from None
        metadata = CloudSaveMetadata(
            revision="gateway-read-only",
            size=len(payload),
            sha256=sha256(payload).hexdigest(),
            source="gateway",
        )
        return AcquiredCloudSave(metadata, payload)

    def metadata(self) -> CloudSaveMetadata:
        return self.download().metadata


@dataclass(frozen=True)
class CopyMetadataSource:
    """Fuente en memoria para entregar la copia al importador existente."""

    declared: CopyMetadata
    payload: bytes = field(repr=False)

    def metadata(self) -> CopyMetadata:
        return self.declared

    def read(self, limit: int) -> bytes:
        if type(limit) is not int or not 0 < limit <= MAX_INPUT_BYTES:
            raise CopyLimitError("Tamaño de copia fuera de los límites.")
        if len(self.payload) > limit:
            raise CopyLimitError("La copia supera el límite permitido.")
        return self.payload

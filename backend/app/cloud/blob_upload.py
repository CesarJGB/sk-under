"""Escritura BlobSave experimental, deshabilitada por defecto.

Reproduce la solicitud que el cliente 8.8.0 envió en la cuenta de laboratorio:
``POST /BlobSave/Upload`` con gzip de un sobre JSON ``{"data": "<agregado>"}``,
``Content-Type: application/json`` y ``Content-Encoding: gzip``. La sesión y los
identificadores los aporta el titular; este módulo no inicia sesión ni persiste
credenciales.

Un HTTP 200 con cuerpo ``true`` es la respuesta observada, pero **no** demuestra
persistencia por sí solo. La comprobación real es una descarga posterior con
``app.cloud.blob_roundtrip``. La escritura exige ``enabled=True`` y no está
conectada a ninguna ruta HTTP de la API.
"""

from __future__ import annotations

import http.client
import json
import ssl
import sys
import urllib.parse
from dataclasses import dataclass, field
from hashlib import sha256
from typing import Callable

from ..cloud_save import MAX_INPUT_BYTES, CloudSaveError, CopyLimitError
from .blob_wire import UPLOAD_URL, BlobWireError, build_blob_headers, decode_response, is_credential
from .provider import CloudProviderError, CloudProviderProtocolError, CloudProviderUnauthenticated, CloudProviderUnavailable
from .upload_dry_run import prepare_upload_candidate

MAX_UPLOAD_RESPONSE = 64 * 1024
type Send = Callable[[str, dict[str, str], bytes, float], tuple[int, str, bytes]]


class CloudWriteDisabled(CloudProviderError):
    code = "cloud_write_disabled"


class CloudUploadRejected(CloudProviderError):
    code = "cloud_upload_rejected"

    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


def _send(url: str, headers: dict[str, str], body: bytes, timeout: float) -> tuple[int, str, bytes]:
    """Envía un POST sin seguir redirecciones y sin desactivar TLS."""
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme == "https":
        connection: http.client.HTTPConnection = http.client.HTTPSConnection(
            parsed.hostname, parsed.port or 443, timeout=timeout, context=ssl.create_default_context()
        )
    elif parsed.scheme == "http" and parsed.hostname in {"127.0.0.1", "localhost", "::1"}:
        connection = http.client.HTTPConnection(parsed.hostname, parsed.port or 80, timeout=timeout)
    else:
        raise BlobWireError("La URL de subida debe usar HTTPS o loopback de prueba.")
    target = parsed.path or "/"
    if parsed.query:
        target += "?" + parsed.query
    try:
        connection.request("POST", target, body=body, headers=headers)
        response = connection.getresponse()
        raw = response.read(MAX_UPLOAD_RESPONSE + 1)
        return response.status, response.getheader("Content-Encoding", ""), raw
    finally:
        connection.close()


def _validate_url(url: str) -> None:
    parsed = urllib.parse.urlsplit(url)
    loopback_http = parsed.scheme == "http" and parsed.hostname in {"127.0.0.1", "localhost", "::1"}
    if not (parsed.scheme == "https" or loopback_http):
        raise CloudProviderProtocolError("La URL de subida debe usar HTTPS o loopback de prueba.")
    if (
        not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.fragment
    ):
        raise CloudProviderProtocolError("La URL de subida no es válida.")


@dataclass(frozen=True)
class UploadResult:
    """Resultado auténtico de una solicitud de escritura, sin secretos."""

    status: int
    accepted: bool
    aggregate_size: int
    aggregate_sha256: str = field(repr=False)
    body_size: int
    body_sha256: str = field(repr=False)
    response_size: int
    response_sha256: str = field(repr=False)
    request_token_sent: bool = False

    def summary(self) -> dict[str, object]:
        return {
            "status": self.status,
            "accepted": self.accepted,
            "aggregate_size": self.aggregate_size,
            "aggregate_sha256": self.aggregate_sha256,
            "body_size": self.body_size,
            "body_sha256": self.body_sha256,
            "response_size": self.response_size,
            "response_sha256": self.response_sha256,
            "request_token_sent": self.request_token_sent,
        }


@dataclass(frozen=True)
class BlobSaveUploader:
    """Transporte de escritura opt-in para la cuenta de laboratorio.

    ``enabled`` debe ser verdadero de forma explícita. ``send`` se inyecta en
    pruebas; su valor por defecto usa TLS normal y no sigue redirecciones.
    """

    session_token: str = field(repr=False)
    unique_id: str = field(repr=False)
    distro_id: str = field(repr=False)
    enabled: bool = False
    request_token: int | None = None
    url: str = UPLOAD_URL
    timeout: float = 30.0
    platform: str = "android"
    app_version: str = "8.8.0"
    game_version: str = "8.8.0"
    send: Send = field(default=_send, repr=False, compare=False)

    def __post_init__(self) -> None:
        if not is_credential(self.session_token):
            raise CloudProviderUnauthenticated("Falta una sesión autorizada válida.")
        if not is_credential(self.unique_id) or not is_credential(self.distro_id):
            raise CloudProviderProtocolError("Faltan los identificadores de la instalación.")
        if isinstance(self.timeout, bool) or not isinstance(self.timeout, (int, float)) or not 0 < self.timeout <= 60:
            raise CloudProviderProtocolError("Tiempo de espera inválido.")
        if self.request_token is not None and (
            isinstance(self.request_token, bool) or not isinstance(self.request_token, int) or self.request_token <= 0
        ):
            raise CloudProviderProtocolError("x-request-token debe ser un entero positivo.")
        _validate_url(self.url)

    def upload(self, aggregate: bytes) -> UploadResult:
        if not self.enabled:
            raise CloudWriteDisabled(
                "La escritura experimental está deshabilitada; actívala solo en la cuenta de laboratorio."
            )
        if not aggregate or len(aggregate) > MAX_INPUT_BYTES:
            raise CopyLimitError("La copia está vacía o supera el límite.")
        candidate = prepare_upload_candidate(aggregate)
        headers = build_blob_headers(
            self.session_token,
            self.unique_id,
            self.distro_id,
            content_type="application/json",
            content_encoding="gzip",
            content_length=len(candidate.body),
            platform=self.platform,
            app_version=self.app_version,
            game_version=self.game_version,
        )
        if self.request_token is not None:
            headers["x-request-token"] = str(self.request_token)
        try:
            status, encoding, wire = self.send(self.url, headers, candidate.body, self.timeout)
        except (OSError, http.client.HTTPException, ssl.SSLError):
            raise CloudProviderUnavailable("No se pudo contactar con el servicio de nube.") from None
        if len(wire) > MAX_UPLOAD_RESPONSE:
            raise CloudProviderProtocolError("La respuesta de la subida supera el límite.")
        if status in (401, 403):
            raise CloudProviderUnauthenticated("El servicio rechazó la sesión de escritura.")
        if status != 200:
            raise CloudUploadRejected(f"El servicio respondió con estado {status}.", status)
        try:
            document = decode_response(wire, encoding, MAX_UPLOAD_RESPONSE)
        except BlobWireError:
            raise CloudProviderProtocolError("La respuesta de la subida no es un gzip válido.") from None
        try:
            accepted = json.loads(document)
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise CloudProviderProtocolError("La respuesta de la subida no es JSON válido.") from None
        if accepted is False:
            raise CloudUploadRejected("El servicio respondió false a la escritura.", status)
        if accepted is not True:
            raise CloudProviderProtocolError("La respuesta de la subida no es el booleano observado.")
        return UploadResult(
            status=status,
            accepted=True,
            aggregate_size=len(aggregate),
            aggregate_sha256=sha256(aggregate).hexdigest(),
            body_size=len(candidate.body),
            body_sha256=sha256(candidate.body).hexdigest(),
            response_size=len(wire),
            response_sha256=sha256(wire).hexdigest(),
            request_token_sent=self.request_token is not None,
        )


def main(argv: list[str] | None = None) -> int:
    """CLI de laboratorio; exige una variable de entorno y una confirmación."""
    import argparse
    import os
    from pathlib import Path

    parser = argparse.ArgumentParser(description="Subida BlobSave experimental (cuenta de laboratorio).")
    parser.add_argument("aggregate", type=Path, help="agregado JSON ya validado")
    parser.add_argument("--confirm-experimental-write", action="store_true", help="confirma la escritura remota")
    parser.add_argument("--url", default=UPLOAD_URL, help="URL de subida; por defecto la observada")
    args = parser.parse_args(argv)
    if os.environ.get("SK_CLOUD_WRITE_EXPERIMENTAL") != "1" or not args.confirm_experimental_write:
        parser.exit(2, "Escritura deshabilitada: define SK_CLOUD_WRITE_EXPERIMENTAL=1 y confirma el flag.\n")
    try:
        aggregate = args.aggregate.read_bytes()
        uploader = BlobSaveUploader(
            os.environ.get("SK_CLOUD_SESSION_TOKEN", ""),
            os.environ.get("SK_CLOUD_UNIQUE_ID", ""),
            os.environ.get("SK_CLOUD_DISTRO_ID", ""),
            enabled=True,
            url=args.url,
        )
        result = uploader.upload(aggregate)
    except (CloudSaveError, OSError) as exc:
        parser.exit(1, f"Error: {type(exc).__name__}\n")
    print(json.dumps(result.summary(), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

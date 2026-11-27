"""Lectura experimental BlobSave de Soul Knight 8.8.0, sin escritura remota.

La sesión, distribución e identificador del dispositivo los aporta el titular;
no se obtiene la sesión ni se modifica el dispositivo desde este módulo. La
verificación TLS, el CRC gzip y la validación estructural no sustituyen una
huella independiente publicada por el servidor.
"""
from __future__ import annotations

import argparse
import http.client
import json
import os
import urllib.error
import urllib.request
import zlib
from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path
from typing import Callable

from ..cloud_save import MAX_INPUT_BYTES, MAX_JSON_BYTES, CloudSaveError, CopyLimitError, reconstruct_cloud_save
from ..parsers.json_document import parse_json
from .blob_wire import DOWNLOAD_URL, build_blob_headers, is_credential
from .provider import (AcquiredCloudSave, CloudProviderDeviceBindingThrottled,
                       CloudProviderDeviceRejected, CloudProviderProtocolError,
                       CloudProviderUnauthenticated, CloudProviderUnavailable, CloudSaveMetadata)

URL = DOWNLOAD_URL
Fetch = Callable[[str, dict[str, str], float], tuple[int, str, bytes]]


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _fetch(url: str, headers: dict[str, str], timeout: float) -> tuple[int, str, bytes]:
    request = urllib.request.Request(url, data=b'', headers=headers, method='POST')
    opener = urllib.request.build_opener(_NoRedirect())
    try:
        response = opener.open(request, timeout=timeout)
    except urllib.error.HTTPError as exc:
        response = exc
    with response:
        try:
            body = response.read(MAX_JSON_BYTES + 1)
        except http.client.IncompleteRead:
            raise CloudProviderProtocolError('Respuesta HTTP incompleta.') from None
        length = response.headers.get('Content-Length')
        if length is not None:
            try:
                expected = int(length)
            except ValueError:
                raise CloudProviderProtocolError('Longitud HTTP inválida.') from None
            if expected < 0 or (len(body) <= MAX_JSON_BYTES and expected != len(body)):
                raise CloudProviderProtocolError('Respuesta HTTP incompleta.')
        return response.status, response.headers.get('Content-Encoding', ''), body


def _decode_response(body: bytes, encoding: str) -> bytes:
    if len(body) > MAX_JSON_BYTES:
        raise CopyLimitError('La respuesta supera el límite permitido.')
    if encoding.strip().lower() in ('', 'identity'):
        return body
    if encoding.strip().lower() != 'gzip':
        raise CloudProviderProtocolError('Codificación HTTP desconocida.')
    decoder = zlib.decompressobj(16 + zlib.MAX_WBITS)
    try:
        result = decoder.decompress(body, MAX_JSON_BYTES + 1)
    except zlib.error:
        raise CloudProviderProtocolError('Respuesta gzip corrupta.') from None
    if len(result) > MAX_JSON_BYTES:
        raise CopyLimitError('La respuesta descomprimida supera el límite.')
    if not decoder.eof or decoder.unused_data:
        raise CloudProviderProtocolError('Respuesta gzip incompleta o con bytes adicionales.')
    return result


def _raise_remote_error(status: int, wire: bytes, encoding: str) -> None:
    """Traduce el error del servicio sin conservar su cuerpo ni sus mensajes.

    BlobSave devuelve JSON con ``error`` y ``errordetails``. El código
    ``100509`` indica que la cuenta ya vinculó un dispositivo nuevo hace poco;
    el campo ``bindDeviceWaitSeconds`` o ``timeWait`` fija la espera. No se
    reintenta y no se expone el texto remoto, que puede contener datos.
    """

    try:
        document = _decode_response(wire, encoding)
    except CloudSaveError:
        document = b''
    error_code: int | None = None
    details: dict[str, object] = {}
    if document:
        try:
            parsed = parse_json(document)
        except (ValueError, RecursionError):
            parsed = None
        if isinstance(parsed, dict):
            candidate = parsed.get('error', parsed.get('errorCode'))
            if type(candidate) is int:
                error_code = candidate
            raw_details = parsed.get('errordetails', parsed.get('errorDetails'))
            if isinstance(raw_details, dict):
                details = raw_details
    if error_code == 100509:
        wait: int | None = None
        for key in ('bindDeviceWaitSeconds', 'timeWait', 'waitSeconds'):
            value = details.get(key)
            if type(value) is int:
                wait = value
                break
            if isinstance(value, str) and value.isascii() and value.isdigit():
                wait = int(value)
                break
        raise CloudProviderDeviceBindingThrottled(wait or 86400)
    if error_code == 100505:
        raise CloudProviderDeviceRejected(
            'El servicio rechazó el identificador de instalación generado.'
        )
    raise CloudProviderUnavailable(
        f'El servicio respondió con estado {status}.', provider_code=error_code
    )


@dataclass(frozen=True)
class ModernCloudSaveProvider:
    """Proveedor optativo para el contrato observado en la cuenta de laboratorio."""

    session_token: str = field(repr=False)
    unique_id: str = field(repr=False)
    distro_id: str = field(repr=False)
    timeout: float = 30.0
    platform: str = "android"
    app_version: str = "8.8.0"
    game_version: str = "8.8.0"
    fetch: Fetch = field(default=_fetch, repr=False, compare=False)

    def __post_init__(self) -> None:
        if not is_credential(self.session_token):
            raise CloudProviderUnauthenticated('Falta una sesión autorizada válida.')
        if not is_credential(self.unique_id) or not is_credential(self.distro_id):
            raise CloudProviderProtocolError('Faltan los identificadores de la instalación.')
        if isinstance(self.timeout, bool) or not isinstance(self.timeout, (int, float)) or not 0 < self.timeout <= 60:
            raise CloudProviderProtocolError('Tiempo de espera inválido.')

    def download(self, limit: int = MAX_INPUT_BYTES) -> AcquiredCloudSave:
        if type(limit) is not int or not 0 < limit <= MAX_INPUT_BYTES:
            raise CopyLimitError('Tamaño de copia fuera de los límites.')
        headers = build_blob_headers(
            self.session_token,
            self.unique_id,
            self.distro_id,
            platform=self.platform,
            app_version=self.app_version,
            game_version=self.game_version,
        )
        try:
            status, encoding, wire = self.fetch(URL, headers, self.timeout)
        except (OSError, urllib.error.URLError, http.client.HTTPException):
            # No propagar detalles del transporte que podrían contener datos privados.
            raise CloudProviderUnavailable('No se pudo contactar con el servicio de nube.') from None
        if status in (401, 403):
            raise CloudProviderUnauthenticated('El servicio rechazó la sesión.')
        if status != 200:
            _raise_remote_error(status, wire, encoding)
        document = _decode_response(wire, encoding)
        try:
            envelope = parse_json(document)
        except (ValueError, RecursionError):
            raise CloudProviderProtocolError('La respuesta no contiene JSON válido.') from None
        if not isinstance(envelope, dict) or not isinstance(envelope.get('data'), str):
            raise CloudProviderProtocolError('La respuesta no contiene el campo data observado.')
        try:
            payload = envelope['data'].encode('utf-8')
        except UnicodeEncodeError:
            raise CloudProviderProtocolError('La copia no contiene UTF-8 válido.') from None
        if not payload or len(payload) > limit:
            raise CopyLimitError('La copia está vacía o supera el límite.')
        try:
            reconstruct_cloud_save(payload)
        except CloudSaveError:
            raise CloudProviderProtocolError('La respuesta no contiene un agregado válido.') from None
        metadata = CloudSaveMetadata('blob-save-experimental', len(payload), sha256(payload).hexdigest(),
                                     source='modern-cloud')
        return AcquiredCloudSave(metadata, payload)

    def metadata(self) -> CloudSaveMetadata:
        return self.download().metadata


def main() -> int:
    parser = argparse.ArgumentParser(description='Descarga experimental de solo lectura; requiere sesión autorizada.')
    parser.add_argument('output', type=Path, help='archivo privado nuevo para el agregado')
    args = parser.parse_args()
    try:
        provider = ModernCloudSaveProvider(os.environ.get('SK_CLOUD_SESSION_TOKEN', ''),
                                           os.environ.get('SK_CLOUD_UNIQUE_ID', ''),
                                           os.environ.get('SK_CLOUD_DISTRO_ID', ''))
        copy = provider.download()
        from ..local_save import write_private_file
        write_private_file(args.output, copy.payload)
        print(json.dumps({'source': copy.metadata.source, 'bytes': copy.metadata.size,
                          'sha256': copy.metadata.sha256, 'save': reconstruct_cloud_save(copy.payload).summary()}))
    except (CloudSaveError, OSError) as exc:
        parser.exit(1, f'Error: {type(exc).__name__}\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

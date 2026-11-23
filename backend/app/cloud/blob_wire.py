"""Primitivas de transporte compartidas por la lectura y la escritura BlobSave.

Las cabeceras reproducen las que usó la sesión de laboratorio: el token de
sesión y los identificadores de la instalación ya emitidos por el cliente
oficial. Este módulo no inicia sesión, no guarda credenciales y no desactiva la
verificación TLS. La decodificación de la respuesta es estricta para no aceptar
gzip truncado ni bytes adicionales.
"""

from __future__ import annotations

import zlib

from ..cloud_save import MAX_JSON_BYTES, CloudSaveError, CopyLimitError

BASE_URL = "https://save.soulknight.chillyroom.com"
DOWNLOAD_URL = BASE_URL + "/BlobSave/Download"
UPLOAD_URL = BASE_URL + "/BlobSave/Upload"


class BlobWireError(CloudSaveError):
    code = "blob_wire"


def is_credential(value: object) -> bool:
    """Un valor de sesión o identificador visible, sin espacios ni controles."""
    return isinstance(value, str) and bool(value.strip()) and all(33 <= ord(c) <= 126 for c in value)


def build_blob_headers(
    session_token: str,
    unique_id: str,
    distro_id: str,
    *,
    content_type: str = "application/json; charset=utf-8",
    content_encoding: str | None = None,
    content_length: int | None = None,
) -> dict[str, str]:
    """Cabeceras observadas en el cliente 8.8.0 para esta cuenta de laboratorio.

    No se afirma que todas sean obligatorias. El llamador sigue siendo
    responsable de verificar las credenciales antes de construir la petición.
    """
    headers = {
        "Authorization": "Bearer " + session_token,
        "x-unique-id": unique_id,
        "x-distro-id": distro_id,
        "x-game-id": "1",
        "x-game": "Soulknight",
        "x-app-version": "8.8.0",
        "x-game-version": "8.8.0",
        "x-platform": "android",
        "x-game-lang": "en",
        "x-locale": "en_US",
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
        "Content-Type": content_type,
    }
    if content_encoding is not None:
        headers["Content-Encoding"] = content_encoding
    if content_length is not None:
        headers["Content-Length"] = str(content_length)
    return headers


def decode_response(body: bytes, encoding: str, limit: int = MAX_JSON_BYTES) -> bytes:
    """Descomprime una respuesta HTTP y rechaza truncamientos o bytes extra."""
    if len(body) > limit:
        raise CopyLimitError("La respuesta supera el límite permitido.")
    if encoding.strip().lower() in ("", "identity"):
        return body
    if encoding.strip().lower() != "gzip":
        raise BlobWireError("Codificación HTTP desconocida.")
    decoder = zlib.decompressobj(16 + zlib.MAX_WBITS)
    try:
        result = decoder.decompress(body, limit + 1)
    except zlib.error:
        raise BlobWireError("Respuesta gzip corrupta.") from None
    if len(result) > limit:
        raise CopyLimitError("La respuesta descomprimida supera el límite.")
    if not decoder.eof or decoder.unused_data:
        raise BlobWireError("Respuesta gzip incompleta o con bytes adicionales.")
    return result

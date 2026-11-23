"""Preparación local de una hipótesis de subida; no abre conexiones.

La forma exacta del JSON y la semántica de x-request-token no se observaron
sobre el cable. No usar este candidato como prueba de aceptación del servicio.
"""
from __future__ import annotations

import gzip
import json
from dataclasses import dataclass, field
from hashlib import sha256

from ..cloud_save import MAX_INPUT_BYTES, CopyLimitError, reconstruct_cloud_save
from ..parsers.json_document import parse_json


@dataclass(frozen=True)
class UploadCandidate:
    body: bytes = field(repr=False)
    aggregate_sha256: str = field(repr=False)
    body_sha256: str = field(repr=False)
    content_type: str = 'application/json'
    content_encoding: str = 'gzip'


def prepare_upload_candidate(aggregate: bytes) -> UploadCandidate:
    """Genera gzip(JSON con data textual) y verifica el roundtrip local.

    El candidato se basa en el DTO y en la serialización observados estáticamente;
    no establece que sea idéntico a la solicitud del cliente ni aceptado.
    """
    if not aggregate or len(aggregate) > MAX_INPUT_BYTES:
        raise CopyLimitError('La copia está vacía o supera el límite.')
    reconstruct_cloud_save(aggregate)
    document = json.dumps({'data': aggregate.decode('utf-8')}, ensure_ascii=False,
                          separators=(',', ':'), allow_nan=False)
    # Json.NET escapa estos separadores incluso con StringEscapeHandling.Default.
    for char in ('\u0085', '\u2028', '\u2029'):
        document = document.replace(char, f'\\u{ord(char):04x}')
    document = document.encode('utf-8')
    body = gzip.compress(document, mtime=0)
    decoded = parse_json(gzip.decompress(body))
    if not isinstance(decoded, dict) or decoded.get('data', '').encode('utf-8') != aggregate:
        raise ValueError('El candidato no conserva el agregado.')
    return UploadCandidate(body, sha256(aggregate).hexdigest(), sha256(body).hexdigest())

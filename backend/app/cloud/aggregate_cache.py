"""Caché acotada de agregados canónicos ya validados.

Los editores de la Fase 8 validaban y volvían a analizar el agregado completo
en cada paso. En una edición unificada el mismo original se usa varias veces y
cada candidato intermedio se lee de nuevo para verificarlo. Esta caché conserva
el árbol inmutable de los bytes ya comprobados (clave: hash + tamaño), de modo
que las lecturas posteriores no repitan el sobre, el análisis JSON ni la
comprobación de serialización canónica.

El árbol devuelto es compartido: los mutadores existentes siempre trabajan
sobre ``deepcopy(root)``. No se cachean fallos.
"""

from __future__ import annotations

import json
from collections import OrderedDict
from hashlib import sha256
from threading import Lock
from typing import Mapping

from ..cloud_save import (
    MAX_INPUT_BYTES,
    AggregateFormatError,
    CopyLimitError,
    reconstruct_cloud_save,
    unpack_cloud_save,
)
from ..parsers.json_document import parse_json

JsonObject = dict[str, object]

_MAX_ENTRIES = 16
_MAX_BYTES = 32 * 1024 * 1024
_cache: OrderedDict[tuple[str, int], tuple[JsonObject, int]] = OrderedDict()
_cache_bytes = 0
_lock = Lock()


def serialize_canonical(document: Mapping[str, object]) -> bytes:
    """Serializa con la forma canónica observada en las copias reales."""
    try:
        return json.dumps(
            document,
            ensure_ascii=False,
            sort_keys=True,
            allow_nan=False,
            separators=(", ", ": "),
        ).encode("utf-8")
    except (TypeError, ValueError):
        raise AggregateFormatError("El agregado no se puede serializar como JSON.") from None


def validated_document(
    source: bytes,
    *,
    unsupported_error: type[Exception],
    unsupported_message: str,
    empty_error: type[Exception] = CopyLimitError,
    size_error: type[Exception] = CopyLimitError,
    format_error: type[Exception] = AggregateFormatError,
) -> tuple[JsonObject, int]:
    """Devuelve ``(root, serialzedVersion)`` validando una sola vez por hash.

    ``unsupported_error`` permite conservar el error específico de cada editor
    cuando el agregado no usa el sobre JSON canónico.
    """

    if not source:
        raise empty_error("La copia está vacía.")
    if len(source) > MAX_INPUT_BYTES:
        raise size_error("La copia supera el límite permitido.")
    key = (sha256(source).hexdigest(), len(source))
    with _lock:
        cached = _cache.get(key)
        if cached is not None:
            _cache.move_to_end(key)
            return cached[0], cached[1]

    reconstruct_cloud_save(source)
    encoding, document = unpack_cloud_save(source)
    if encoding != "json":
        raise unsupported_error(unsupported_message)
    try:
        root = parse_json(document)
    except (ValueError, RecursionError):
        raise format_error("El documento no contiene JSON UTF-8 válido.") from None
    if not isinstance(root, dict):
        raise format_error("Se esperaba un objeto JSON en la raíz.")
    if serialize_canonical(root) != source:
        raise unsupported_error(unsupported_message)
    version = root.get("serialzedVersion")
    if isinstance(version, bool) or not isinstance(version, int):
        raise format_error("Se requiere serialzedVersion como entero.")

    with _lock:
        global _cache_bytes
        previous = _cache.pop(key, None)
        if previous is not None:
            _cache_bytes -= len(source)
        _cache[key] = (root, version)
        _cache_bytes += len(source)
        while len(_cache) > _MAX_ENTRIES or _cache_bytes > _MAX_BYTES:
            old_key, _ = _cache.popitem(last=False)
            _cache_bytes -= old_key[1]
    return root, version


def clear_aggregate_cache() -> None:
    """Vacía la caché; usado por pruebas y por recargas controladas."""

    global _cache_bytes
    with _lock:
        _cache.clear()
        _cache_bytes = 0
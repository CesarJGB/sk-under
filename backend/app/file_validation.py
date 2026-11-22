import base64

from .errors import EditorError


def base64_limit(file_limit: int) -> int:
    return 4 * ((file_limit + 2) // 3)


def require_size(data: bytes, limit: int) -> None:
    if len(data) > limit:
        raise EditorError(413, "file_too_large", "El archivo supera el límite permitido.")


def decode_file(encoded: str, limit: int) -> bytes:
    if len(encoded) > base64_limit(limit):
        raise EditorError(413, "file_too_large", "El archivo supera el límite permitido.")
    try:
        data = base64.b64decode(encoded, validate=True)
    except ValueError:
        raise EditorError(422, "invalid_base64", "El contenido no es Base64 válido.") from None
    if not data:
        raise EditorError(422, "empty_file", "El archivo está vacío.")
    require_size(data, limit)
    return data

"""Detección del formato exterior y reconstrucción local del agregado.

Solo se decodifica lo que ya está demostrado: un objeto JSON UTF-8 o un único
miembro gzip que contiene ese objeto. Los marcadores RPC se clasifican y, por
defecto, se rechazan con un error tipado. ``rpc_body="gzip_candidate"`` habilita
un intento experimental de leer el cuerpo como gzip; no se usa en producción y
no se declara que sea el códec real.
"""

from dataclasses import dataclass, field
from typing import Literal

from ..cloud_envelope import RpcFrame, inspect_rpc_frame
from ..cloud_save import (
    MAX_INPUT_BYTES,
    CopyLimitError,
    ReconstructedCloudSave,
    UnsupportedEncoding,
    reconstruct_cloud_save,
)

type DetectedFormat = Literal["json", "gzip"]


class RpcEnvelopeError(UnsupportedEncoding):
    """El sobre RPC se reconoce, pero no se puede entregar como agregado."""

    code = "rpc_envelope"

    def __init__(self, message: str, frame: RpcFrame | None = None) -> None:
        super().__init__(message)
        self.frame = frame


class RpcNullMarker(RpcEnvelopeError):
    code = "rpc_null_marker"


class RpcBodyUnknown(RpcEnvelopeError):
    code = "rpc_codec_unknown"


class RpcBodyNotGzip(RpcBodyUnknown):
    """El cuerpo comprimido no empieza con la firma gzip observable."""

    code = "rpc_body_not_gzip"


type RpcBodyPolicy = Literal["reject", "gzip_candidate"]


@dataclass(frozen=True)
class DecodedCopy:
    format: DetectedFormat
    aggregate: ReconstructedCloudSave
    original: bytes = field(repr=False)


def detect_format(payload: bytes) -> DetectedFormat:
    if payload.startswith(b"\x1f\x8b"):
        return "gzip"
    if payload.lstrip(b" \t\r\n").startswith(b"{"):
        return "json"
    raise UnsupportedEncoding("Se esperaba un objeto JSON UTF-8 o gzip.")


def classify_rpc(payload: bytes) -> RpcFrame:
    """Clasifica el discriminador RPC sin interpretar el cuerpo comprimido."""
    return inspect_rpc_frame(payload)


def decode_rpc_gzip(payload: bytes, frame: RpcFrame | None = None) -> DecodedCopy:
    """Intenta interpretar el cuerpo RPC como un miembro gzip.

    Es una capacidad experimental: la firma gzip del cuerpo no se ha
    confirmado con una respuesta real. No se usa por defecto en ``decode_copy``.
    """
    frame = frame or inspect_rpc_frame(payload)
    if frame.kind != "compressed":
        raise RpcBodyUnknown("El sobre no selecciona la rama comprimida.", frame)
    body = bytes(frame.body or b"")
    if not body.startswith(b"\x1f\x8b"):
        raise RpcBodyNotGzip(
            "El cuerpo RPC no presenta la firma gzip 1f 8b; no se adivina el códec.",
            frame,
        )
    return DecodedCopy("gzip", reconstruct_cloud_save(body), payload)


def decode_copy(payload: bytes, *, rpc_body: RpcBodyPolicy = "reject") -> DecodedCopy:
    if len(payload) > MAX_INPUT_BYTES:
        raise CopyLimitError("La entrada supera el límite permitido.")
    if not payload:
        raise CopyLimitError("La copia está vacía.")

    frame = inspect_rpc_frame(payload)
    if frame.kind == "null_marker":
        raise RpcNullMarker(
            "El sobre RPC contiene la marca nula; no es un agregado reutilizable.",
            frame,
        )
    if frame.kind == "compressed":
        if rpc_body == "gzip_candidate":
            return decode_rpc_gzip(payload, frame)
        raise RpcBodyUnknown(
            "El sobre RPC está comprimido y su códec interior no está demostrado.",
            frame,
        )

    detected = detect_format(payload)
    return DecodedCopy(detected, reconstruct_cloud_save(payload), payload)


@dataclass(frozen=True)
class GzipDiagnostics:
    """Informe acotado sobre un miembro gzip, sin habilitar producción."""

    header: bool
    member_bytes: int
    isize: int | None = None
    decompressed_bytes: int | None = None
    trailing_bytes: int = 0
    crc_ok: bool | None = None
    error: str | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            "header": self.header,
            "member_bytes": self.member_bytes,
            "isize": self.isize,
            "decompressed_bytes": self.decompressed_bytes,
            "trailing_bytes": self.trailing_bytes,
            "crc_ok": self.crc_ok,
            "error": self.error,
        }


def diagnose_gzip(payload: bytes) -> GzipDiagnostics:
    """Valida cabecera, CRC, tamaño y truncamiento de un miembro gzip.

    La salida está limitada a ``MAX_JSON_BYTES``; no se interpreta el contenido.
    """
    import zlib

    from ..cloud_save import MAX_JSON_BYTES

    if not payload.startswith(b"\x1f\x8b"):
        return GzipDiagnostics(False, len(payload), error="missing_header")
    if len(payload) < 18:
        return GzipDiagnostics(True, len(payload), error="truncated")
    isize = int.from_bytes(payload[-4:], "little")
    decoder = zlib.decompressobj(wbits=16 + zlib.MAX_WBITS)
    try:
        document = decoder.decompress(payload, MAX_JSON_BYTES + 1)
    except zlib.error:
        return GzipDiagnostics(True, len(payload), isize, error="invalid_stream")
    if len(document) > MAX_JSON_BYTES:
        return GzipDiagnostics(True, len(payload), isize, len(document), error="size_limit")
    if not decoder.eof:
        return GzipDiagnostics(True, len(payload), isize, len(document), error="truncated")
    trailing = len(decoder.unused_data)
    if trailing:
        return GzipDiagnostics(True, len(payload), isize, len(document), trailing, error="trailing_bytes")
    return GzipDiagnostics(True, len(payload), isize, len(document), 0, crc_ok=True)


def diagnose_payload(payload: bytes) -> dict[str, object]:
    """Clasifica una copia y resume el resultado sin exponer su contenido."""
    from hashlib import sha256

    from ..cloud_save import MAX_INPUT_BYTES, CloudSaveError

    report: dict[str, object] = {
        "size": len(payload),
        "sha256": sha256(payload).hexdigest(),
        "rpc": None,
        "format": None,
        "gzip": None,
        "decoded": False,
        "error": None,
    }
    if len(payload) > MAX_INPUT_BYTES:
        report["error"] = "size_limit"
        return report
    try:
        frame = inspect_rpc_frame(payload)
        report["rpc"] = frame.kind
        body = bytes(frame.body or b"")
        if body.startswith(b"\x1f\x8b"):
            report["format"] = "gzip"
            report["gzip"] = diagnose_gzip(body).as_dict()
        elif body.lstrip(b" \t\r\n").startswith(b"{"):
            report["format"] = "json"
        elif body:
            report["format"] = "unknown"
        if frame.kind in ("compressed", "passthrough"):
            decode_copy(payload, rpc_body="gzip_candidate" if frame.kind == "compressed" else "reject")
            report["decoded"] = True
    except CloudSaveError as exc:
        report["error"] = exc.code
    return report

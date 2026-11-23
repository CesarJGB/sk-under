"""Detección del formato exterior y reconstrucción local del agregado.

Solo se decodifica lo que ya está demostrado: un objeto JSON UTF-8 o un único
miembro gzip que contiene ese objeto. Los marcadores RPC se clasifican y se
rechazan con un error tipado; el códec interior del bloque comprimido no está
resuelto y no se adivina aquí.
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


def decode_copy(payload: bytes) -> DecodedCopy:
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
        raise RpcBodyUnknown(
            "El sobre RPC está comprimido y su códec interior no está demostrado.",
            frame,
        )

    detected = detect_format(payload)
    return DecodedCopy(detected, reconstruct_cloud_save(payload), payload)

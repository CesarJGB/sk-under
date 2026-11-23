"""Límites administrados del APK 8.8.0, para datos ya suministrados."""

from dataclasses import dataclass, field
from typing import Literal

from .cloud_save import (
    MAX_INPUT_BYTES,
    AggregateFormatError,
    CopyLimitError,
    ReconstructedCloudSave,
    reconstruct_cloud_save,
)


@dataclass(frozen=True)
class RpcFrame:
    kind: Literal["null_input", "null_marker", "compressed", "passthrough"]
    original: bytes | None = field(repr=False)

    @property
    def body(self) -> memoryview | None:
        if self.original is None or self.kind == "null_marker":
            return None
        start = 4 if self.kind == "compressed" else 0
        return memoryview(self.original)[start:]


def inspect_rpc_frame(payload: bytes | None) -> RpcFrame:
    if payload is None:
        return RpcFrame("null_input", None)
    if len(payload) > MAX_INPUT_BYTES:
        raise CopyLimitError("La entrada supera el límite permitido.")
    if payload.startswith(b"\xff\xff\xff\xff"):
        return RpcFrame("null_marker", payload)
    if payload.startswith(b"\x00\x00\x00\x80"):
        return RpcFrame("compressed", payload)
    return RpcFrame("passthrough", payload)


def parse_blobsave_data(text: str | None) -> ReconstructedCloudSave:
    """Consume el string Data ya materializado. La huella corresponde a su UTF-8."""
    if not isinstance(text, str):
        raise AggregateFormatError("Se esperaba texto en Data.")
    if len(text) > MAX_INPUT_BYTES:
        raise CopyLimitError("La entrada supera el límite permitido.")
    try:
        payload = text.encode("utf-8")
    except UnicodeEncodeError:
        raise AggregateFormatError("El texto de Data no se puede codificar en UTF-8.") from None
    return reconstruct_cloud_save(payload)

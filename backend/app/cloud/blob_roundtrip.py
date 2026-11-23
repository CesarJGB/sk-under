"""Ciclo experimental subida + descarga de verificación.

Una respuesta ``true`` solo se considera aceptación de la solicitud. El éxito
requiere que una descarga posterior, hecha por el mismo canal autenticado,
devuelva exactamente el SHA-256 enviado. Este módulo no está expuesto por la
API HTTP.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass, field
from hmac import compare_digest
from pathlib import Path

from ..cloud_save import MAX_INPUT_BYTES, CloudSaveError, CopyLimitError
from .blob_upload import BlobSaveUploader, UploadResult
from .modern import ModernCloudSaveProvider
from .provider import CloudSaveAcquisitionProvider


@dataclass(frozen=True)
class RoundtripResult:
    upload: UploadResult
    remote_size: int
    remote_sha256: str = field(repr=False)
    remote_source: str = "remote"
    matches: bool = False

    def summary(self) -> dict[str, object]:
        return {
            "upload": self.upload.summary(),
            "verification": {
                "remote_size": self.remote_size,
                "remote_sha256": self.remote_sha256,
                "remote_source": self.remote_source,
                "matches_uploaded": self.matches,
            },
        }


def upload_and_verify(
    aggregate: bytes,
    uploader: BlobSaveUploader,
    provider: CloudSaveAcquisitionProvider,
    limit: int = MAX_INPUT_BYTES,
) -> RoundtripResult:
    """Sube y vuelve a descargar; ``matches`` es la única confirmación de persistencia."""
    if not aggregate or len(aggregate) > limit:
        raise CopyLimitError("La copia está vacía o supera el límite.")
    upload = uploader.upload(aggregate)
    remote = provider.download(limit)
    matches = (
        remote.metadata.size == len(aggregate)
        and compare_digest(remote.metadata.sha256, upload.aggregate_sha256)
    )
    return RoundtripResult(
        upload=upload,
        remote_size=remote.metadata.size,
        remote_sha256=remote.metadata.sha256,
        remote_source=remote.metadata.source,
        matches=matches,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Subida BlobSave experimental y verificación por descarga (cuenta de laboratorio)."
    )
    parser.add_argument("aggregate", type=Path, help="agregado JSON ya validado")
    parser.add_argument("--confirm-experimental-write", action="store_true")
    args = parser.parse_args(argv)
    if os.environ.get("SK_CLOUD_WRITE_EXPERIMENTAL") != "1" or not args.confirm_experimental_write:
        parser.exit(2, "Escritura deshabilitada: define SK_CLOUD_WRITE_EXPERIMENTAL=1 y confirma el flag.\n")
    token = os.environ.get("SK_CLOUD_SESSION_TOKEN", "")
    unique_id = os.environ.get("SK_CLOUD_UNIQUE_ID", "")
    distro_id = os.environ.get("SK_CLOUD_DISTRO_ID", "")
    try:
        aggregate = args.aggregate.read_bytes()
        uploader = BlobSaveUploader(token, unique_id, distro_id, enabled=True)
        provider = ModernCloudSaveProvider(token, unique_id, distro_id)
        result = upload_and_verify(aggregate, uploader, provider)
    except (CloudSaveError, OSError) as exc:
        parser.exit(1, f"Error: {type(exc).__name__}\n")
    print(json.dumps(result.summary(), indent=2))
    return 0 if result.matches else 1


if __name__ == "__main__":
    sys.exit(main())

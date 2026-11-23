"""Puente local entre una copia suministrada por el titular y Linux.

No hay transporte remoto ni llamadas al cliente del juego. El puente recibe un
archivo local, lo identifica, verifica su integridad, permite una edición
explícita de laboratorio y entrega una copia conservando el original. Las
interfaces separan adquisición, decodificación, validación, edición y
exportación para poder añadir proveedores autorizados en el futuro.
"""

from __future__ import annotations

import argparse
import json
import os
import stat
import sys
from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path
from typing import Protocol

from .cloud.provider import (
    AcquiredCloudSave,
    CloudSaveAcquisitionProvider,
    CopyMetadataSource,
)
from .cloud_import import CopyMetadata, ImportedCopy, import_copy
from .cloud_save import MAX_INPUT_BYTES
from .local_save import (
    MAX_LOCAL_FILE_BYTES,
    LocalFormatError,
    LocalSaveError,
    LocalSaveLab,
    LocalSection,
    decode_local_section,
    inspect_local_directory,
    kind_from_filename,
    write_private_file,
)
from .settings import Settings


@dataclass(frozen=True)
class AcquiredSave:
    name: str
    data: bytes = field(repr=False)
    source: str = field(repr=False)

    @property
    def sha256(self) -> str:
        return sha256(self.data).hexdigest()


@dataclass(frozen=True)
class DecodedSave:
    acquired: AcquiredSave
    section: LocalSection | None
    status: str
    reason: str | None = None

    @property
    def summary(self) -> dict[str, object]:
        result: dict[str, object] = {
            "name": self.acquired.name,
            "status": self.status,
            "bytes": len(self.acquired.data),
            "sha256": self.acquired.sha256,
        }
        if self.section is not None:
            result.update(self.section.summary())
        if self.reason:
            result["reason"] = self.reason
        return result


@dataclass(frozen=True)
class ValidatedSave:
    decoded: DecodedSave
    valid: bool
    checks: tuple[str, ...]

    def summary(self) -> dict[str, object]:
        return {
            **self.decoded.summary,
            "valid": self.valid,
            "checks": list(self.checks),
        }


@dataclass(frozen=True)
class ExportedSave:
    target: str
    bytes: int
    sha256: str
    original_preserved: bool

    def summary(self) -> dict[str, object]:
        return {
            "target": self.target,
            "bytes": self.bytes,
            "sha256": self.sha256,
            "original_preserved": self.original_preserved,
        }


class SaveAcquisitionProvider(Protocol):
    def acquire(self) -> AcquiredSave: ...


class SaveDecoder(Protocol):
    def decode(self, acquired: AcquiredSave) -> DecodedSave: ...


class SaveValidator(Protocol):
    def validate(self, decoded: DecodedSave) -> ValidatedSave: ...


class SaveEditor(Protocol):
    def edit(self, decoded: DecodedSave, changes: dict[str, object]) -> tuple[DecodedSave, bytes]: ...


class SaveExporter(Protocol):
    def export(self, decoded: DecodedSave, target: Path, *, overwrite: bool = False) -> ExportedSave: ...


def read_regular_file(path: Path, *, limit: int = MAX_LOCAL_FILE_BYTES) -> bytes:
    """Lee un archivo regular sin seguir enlaces y con un límite estricto."""
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError:
        raise LocalFormatError("No se pudo abrir el archivo local.") from None
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode):
            raise LocalFormatError("Se requiere un archivo regular.")
        if not 0 < info.st_size <= limit:
            raise LocalFormatError("El archivo está vacío o supera el límite.")
        data = bytearray()
        while len(data) <= limit:
            chunk = os.read(descriptor, min(65536, limit + 1 - len(data)))
            if not chunk:
                break
            data.extend(chunk)
    finally:
        os.close(descriptor)
    if len(data) > limit:
        raise LocalFormatError("El archivo supera el límite.")
    return bytes(data)


@dataclass(frozen=True)
class LocalFileProvider:
    path: Path = field(repr=False)

    def acquire(self) -> AcquiredSave:
        data = read_regular_file(self.path)
        return AcquiredSave(self.path.name, data, str(self.path.resolve()))


@dataclass(frozen=True)
class LocalSectionDecoder:
    general_key: bytes = field(repr=False)
    statistics_key: bytes = field(repr=False)
    iv: bytes = field(repr=False)

    def decode(self, acquired: AcquiredSave) -> DecodedSave:
        expected = kind_from_filename(acquired.name)
        try:
            section = decode_local_section(
                acquired.data,
                general_key=self.general_key,
                statistics_key=self.statistics_key,
                iv=self.iv,
                name=acquired.name,
                expected_kind=expected,
            )
        except LocalSaveError as exc:
            return DecodedSave(acquired, None, "unknown", exc.code)
        if section is not None:
            return DecodedSave(acquired, section, "decoded")
        if acquired.data.lstrip().startswith(b"{") and expected in ("sandbox_config", "sandbox_maps"):
            return DecodedSave(acquired, None, "plain_json", "json sin cifrar")
        if expected == "game":
            return DecodedSave(acquired, None, "opaque", "formato de game.data no identificado")
        return DecodedSave(acquired, None, "unknown", "no corresponde a una sección local")


@dataclass(frozen=True)
class LocalSectionValidator:
    def validate(self, decoded: DecodedSave) -> ValidatedSave:
        checks = ["sha256", "tamaño"]
        valid = len(decoded.acquired.data) > 0 and sha256(decoded.acquired.data).hexdigest() == decoded.acquired.sha256
        if decoded.section is not None:
            checks.append("esquema")
            checks.append("versión")
            valid = valid and decoded.section.sha256 == decoded.acquired.sha256
        return ValidatedSave(decoded, valid, tuple(checks))


@dataclass(frozen=True)
class LocalSectionEditor:
    general_key: bytes = field(repr=False)
    statistics_key: bytes = field(repr=False)
    iv: bytes = field(repr=False)

    def edit(self, decoded: DecodedSave, changes: dict[str, object]) -> tuple[DecodedSave, bytes]:
        if decoded.section is None:
            raise LocalFormatError("Solo se edita una sección local reconocida.")
        lab = LocalSaveLab.open(
            decoded.acquired.data,
            general_key=self.general_key,
            statistics_key=self.statistics_key,
            iv=self.iv,
            name=decoded.acquired.name,
        )
        for path, value in changes.items():
            lab.set(path, value)  # type: ignore[arg-type]
        report = lab.report()
        edited = AcquiredSave(decoded.acquired.name, report.output, decoded.acquired.source)
        reopened = decode_local_section(
            report.output,
            general_key=self.general_key,
            statistics_key=self.statistics_key,
            iv=self.iv,
            name=decoded.acquired.name,
            expected_kind=decoded.section.kind,
        )
        if reopened is None:
            raise LocalFormatError("La copia editada no se pudo volver a identificar.")
        return DecodedSave(edited, reopened, "decoded"), report.output


@dataclass(frozen=True)
class LocalFileExporter:
    def export(self, decoded: DecodedSave, target: Path, *, overwrite: bool = False) -> ExportedSave:
        written = write_private_file(target, decoded.acquired.data, overwrite=overwrite)
        return ExportedSave(
            target=str(written),
            bytes=len(decoded.acquired.data),
            sha256=sha256(decoded.acquired.data).hexdigest(),
            original_preserved=True,
        )


@dataclass(frozen=True)
class LocalBridge:
    decoder: SaveDecoder
    validator: SaveValidator
    editor: SaveEditor
    exporter: SaveExporter

    def inspect(self, provider: SaveAcquisitionProvider) -> ValidatedSave:
        return self.validator.validate(self.decoder.decode(provider.acquire()))

    def export(self, provider: SaveAcquisitionProvider, target: Path, *, overwrite: bool = False) -> ExportedSave:
        decoded = self.decoder.decode(provider.acquire())
        return self.exporter.export(decoded, target, overwrite=overwrite)

    def edit(
        self,
        provider: SaveAcquisitionProvider,
        changes: dict[str, object],
        target: Path,
        *,
        overwrite: bool = False,
    ) -> ExportedSave:
        decoded = self.decoder.decode(provider.acquire())
        edited, _ = self.editor.edit(decoded, changes)
        return self.exporter.export(edited, target, overwrite=overwrite)


@dataclass(frozen=True)
class CloudAcquisition:
    """Resultado de una adquisición ya validada por el importador existente."""

    acquired: AcquiredCloudSave
    copy: ImportedCopy

    def summary(self) -> dict[str, object]:
        return {
            **self.acquired.summary(),
            **self.copy.aggregate.summary(),
        }


@dataclass(frozen=True)
class CloudBridge:
    """Une un proveedor de nube con el importador y el exportador locales.

    No inicia sesión, no escribe en la nube y no acepta credenciales en claro.
    Un proveedor deshabilitado propaga su error tipado; un fixture local se
    etiqueta como tal y no se presenta como una descarga.
    """

    def acquire(self, provider: CloudSaveAcquisitionProvider) -> CloudAcquisition:
        acquired = provider.download(MAX_INPUT_BYTES)
        declared = CopyMetadata(acquired.metadata.size, acquired.metadata.sha256)
        source = CopyMetadataSource(declared, acquired.payload)
        return CloudAcquisition(acquired, import_copy(source))

    def inspect(self, provider: CloudSaveAcquisitionProvider) -> dict[str, object]:
        return self.acquire(provider).summary()

    def export(
        self,
        provider: CloudSaveAcquisitionProvider,
        target: Path,
        *,
        overwrite: bool = False,
    ) -> ExportedSave:
        acquired = provider.download(MAX_INPUT_BYTES)
        written = write_private_file(target, acquired.payload, overwrite=overwrite)
        return ExportedSave(
            target=str(written),
            bytes=len(acquired.payload),
            sha256=sha256(acquired.payload).hexdigest(),
            original_preserved=True,
        )


def build_bridge(settings: Settings) -> LocalBridge:
    cipher = settings.save_cipher
    if cipher is None:
        raise LocalSaveError("Faltan SK_SAVE_GENERAL_KEY_HEX, SK_SAVE_STATISTICS_KEY_HEX y SK_SAVE_IV_HEX.")
    general, statistics, iv = cipher
    return LocalBridge(
        decoder=LocalSectionDecoder(general, statistics, iv),
        validator=LocalSectionValidator(),
        editor=LocalSectionEditor(general, statistics, iv),
        exporter=LocalFileExporter(),
    )


def _parse_value(text: str) -> object:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, help="Archivo privado con las claves del códec local.")
    sub = parser.add_subparsers(dest="command", required=True)

    inspect = sub.add_parser("inspect", help="Resumir un archivo o un directorio local.")
    source = inspect.add_mutually_exclusive_group(required=True)
    source.add_argument("--file", type=Path)
    source.add_argument("--directory", type=Path)

    export = sub.add_parser("export", help="Copiar un archivo local sin modificarlo.")
    export.add_argument("file", type=Path)
    export.add_argument("--output", type=Path, required=True)
    export.add_argument("--overwrite", action="store_true")

    edit = sub.add_parser("edit", help="Editar una sección local en una copia nueva.")
    edit.add_argument("file", type=Path)
    edit.add_argument("--output", type=Path, required=True)
    edit.add_argument("--set", action="append", default=[], metavar="RUTA=VALOR")
    edit.add_argument("--overwrite", action="store_true")

    args = parser.parse_args(argv)
    try:
        settings = Settings(_env_file=args.env_file)
        bridge = build_bridge(settings)
        if args.command == "inspect":
            if args.directory is not None:
                general, statistics, iv = settings.save_cipher or (b"", b"", b"")
                output = inspect_local_directory(
                    args.directory, general_key=general, statistics_key=statistics, iv=iv
                ).as_dict()
            else:
                output = bridge.inspect(LocalFileProvider(args.file)).summary()
        elif args.command == "export":
            output = bridge.export(LocalFileProvider(args.file), args.output, overwrite=args.overwrite).summary()
        else:
            changes: dict[str, object] = {}
            for item in args.set:
                path, separator, value = item.partition("=")
                if not separator or not path:
                    parser.error("--set requiere RUTA=VALOR")
                changes[path] = _parse_value(value)
            output = bridge.edit(
                LocalFileProvider(args.file), changes, args.output, overwrite=args.overwrite
            ).summary()
    except (LocalSaveError, FileExistsError, OSError) as exc:
        print(json.dumps({"error": getattr(exc, "code", "bridge_error"), "message": str(exc)}), file=sys.stderr)
        return 1
    print(json.dumps(output, ensure_ascii=False, allow_nan=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())

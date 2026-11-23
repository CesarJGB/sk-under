"""Respaldos privados de las operaciones del editor de gemas.

Cada preparación crea un directorio nuevo bajo ``SK_CLOUD_BACKUP_DIR`` con el
original y el candidato exactos, un registro sin secretos y un diario de
eventos. Los archivos se crean con modo ``0600`` y el directorio con ``0700``.
Nunca se guardan tokens, correo, identificadores de cuenta ni el contenido en
los registros de eventos.
"""

from __future__ import annotations

import json
import os
import re
import stat
from dataclasses import dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any
from uuid import uuid4

from ..cloud_save import MAX_INPUT_BYTES, CloudSaveError, reconstruct_cloud_save
from ..parsers.json_document import parse_json
from .gems_editor import GemsEdit, prepare_gems_edit, read_gems

_ID = re.compile(r"^[0-9a-f]{32}$")
_RECORD_LIMIT = 64 * 1024


class BackupStoreError(CloudSaveError):
    code = "backup_store"


class InvalidBackupId(BackupStoreError):
    code = "invalid_backup_id"


class BackupNotFound(BackupStoreError):
    code = "backup_not_found"


class BackupIntegrityError(BackupStoreError):
    code = "backup_integrity"


class BackupAlreadyConfirmed(BackupStoreError):
    code = "backup_already_confirmed"


@dataclass(frozen=True)
class BackupRecord:
    id: str
    created_at: str
    changed: bool
    original_size: int
    original_sha256: str = field(repr=False)
    original_gems: int
    candidate_size: int
    candidate_sha256: str = field(repr=False)
    candidate_gems: int
    remote_source: str
    remote_size: int
    remote_sha256: str = field(repr=False)

    def summary(self) -> dict[str, object]:
        return {
            "id": self.id,
            "created_at": self.created_at,
            "changed": self.changed,
            "original_size": self.original_size,
            "original_sha256": self.original_sha256,
            "original_gems": self.original_gems,
            "candidate_size": self.candidate_size,
            "candidate_sha256": self.candidate_sha256,
            "candidate_gems": self.candidate_gems,
            "remote_source": self.remote_source,
            "remote_size": self.remote_size,
            "remote_sha256": self.remote_sha256,
        }


@dataclass(frozen=True)
class BackupBundle:
    record: BackupRecord
    original: bytes = field(repr=False)
    candidate: bytes = field(repr=False)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _require_int(value: object, name: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise BackupIntegrityError(f"El registro de respaldo contiene {name} inválido.")
    return value


def _require_hash(value: object) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise BackupIntegrityError("El registro de respaldo contiene una huella inválida.")
    return value


def _require_text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value or len(value) > 200:
        raise BackupIntegrityError(f"El registro de respaldo contiene {name} inválido.")
    return value


class LabBackupStore:
    """Almacén de respaldos creado explícitamente sobre un directorio privado."""

    def __init__(self, root: Path, *, limit: int = MAX_INPUT_BYTES) -> None:
        if isinstance(limit, bool) or not isinstance(limit, int) or not 0 < limit <= MAX_INPUT_BYTES:
            raise BackupStoreError("Límite de respaldo inválido.")
        self.root = Path(root).expanduser().absolute()
        self.limit = limit

    def _ensure_root(self) -> None:
        try:
            self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
            info = self.root.stat()
            if not stat.S_ISDIR(info.st_mode):
                raise BackupStoreError("La ruta de respaldos no es un directorio.")
            os.chmod(self.root, 0o700)
        except OSError:
            raise BackupStoreError("No se pudo preparar el directorio privado de respaldos.") from None

    def _directory(self, backup_id: str) -> Path:
        if not isinstance(backup_id, str) or not _ID.fullmatch(backup_id):
            raise InvalidBackupId("El identificador de respaldo no es válido.")
        return self.root / backup_id

    def claim_confirmation_attempt(self, backup_id: str) -> None:
        path = self._directory(backup_id) / "upload-attempt"
        try:
            self._write_private(path, b"\n")
        except BackupStoreError:
            if path.is_file():
                raise BackupAlreadyConfirmed(
                    "Ya se intentó subir este candidato. Verifica la partida antes de preparar otra edición."
                ) from None
            raise

    def _write_private(self, path: Path, data: bytes, *, exclusive: bool = True) -> None:
        flags = os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW
        flags |= os.O_EXCL if exclusive else os.O_TRUNC
        try:
            descriptor = os.open(path, flags, 0o600)
        except OSError:
            raise BackupStoreError("No se pudo crear un archivo privado de respaldo.") from None
        try:
            view = memoryview(data)
            while view:
                written = os.write(descriptor, view)
                view = view[written:]
            os.fsync(descriptor)
        except OSError:
            raise BackupStoreError("No se pudo escribir un archivo privado de respaldo.") from None
        finally:
            os.close(descriptor)

    def _read_private(self, path: Path, limit: int) -> bytes:
        try:
            descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        except OSError:
            raise BackupNotFound("No se encontró el respaldo solicitado.") from None
        try:
            info = os.fstat(descriptor)
            if not stat.S_ISREG(info.st_mode) or info.st_size > limit:
                raise BackupIntegrityError("El archivo de respaldo no es válido.")
            chunks: list[bytes] = []
            remaining = info.st_size
            while remaining:
                chunk = os.read(descriptor, min(remaining, 64 * 1024))
                if not chunk:
                    raise BackupIntegrityError("El archivo de respaldo está truncado.")
                chunks.append(chunk)
                remaining -= len(chunk)
            data = b"".join(chunks)
        except OSError:
            raise BackupNotFound("No se pudo leer el respaldo solicitado.") from None
        finally:
            os.close(descriptor)
        return data

    def save(
        self,
        edit: GemsEdit,
        *,
        remote_source: str,
        remote_size: int,
        remote_sha256: str,
    ) -> BackupBundle:
        """Crea un respaldo y devuelve los bytes que quedaron en disco."""
        if remote_sha256 != edit.original_sha256 or remote_size != len(edit.original):
            raise BackupIntegrityError("La copia remota no coincide con el original preparado.")
        source = _require_text(remote_source, "remote_source")
        self._ensure_root()
        backup_id = uuid4().hex
        directory = self._directory(backup_id)
        try:
            os.mkdir(directory, 0o700)
        except OSError:
            raise BackupStoreError("No se pudo crear el directorio del respaldo.") from None
        record = BackupRecord(
            id=backup_id,
            created_at=_now(),
            changed=edit.changed,
            original_size=len(edit.original),
            original_sha256=edit.original_sha256,
            original_gems=edit.original_gems,
            candidate_size=len(edit.candidate),
            candidate_sha256=edit.candidate_sha256,
            candidate_gems=edit.new_gems,
            remote_source=source,
            remote_size=remote_size,
            remote_sha256=remote_sha256,
        )
        try:
            self._write_private(directory / "original.json", edit.original)
            self._write_private(directory / "candidate.json", edit.candidate)
            encoded = json.dumps(record.summary(), ensure_ascii=False, sort_keys=True).encode("utf-8")
            self._write_private(directory / "record.json", encoded)
        except BackupStoreError:
            # El directorio es nuevo y su nombre lo generó este proceso.
            for name in ("record.json", "candidate.json", "original.json"):
                try:
                    (directory / name).unlink(missing_ok=True)
                except OSError:
                    pass
            try:
                directory.rmdir()
            except OSError:
                pass
            raise
        return BackupBundle(record, edit.original, edit.candidate)

    def _read_record(self, backup_id: str) -> BackupRecord:
        raw = self._read_private(self._directory(backup_id) / "record.json", _RECORD_LIMIT)
        try:
            data = parse_json(raw)
        except (ValueError, RecursionError):
            raise BackupIntegrityError("El registro de respaldo no es JSON válido.") from None
        if not isinstance(data, dict):
            raise BackupIntegrityError("El registro de respaldo no es un objeto.")
        record = BackupRecord(
            id=_require_text(data.get("id"), "id"),
            created_at=_require_text(data.get("created_at"), "created_at"),
            changed=data.get("changed") is True,
            original_size=_require_int(data.get("original_size"), "original_size"),
            original_sha256=_require_hash(data.get("original_sha256")),
            original_gems=_require_int(data.get("original_gems"), "original_gems"),
            candidate_size=_require_int(data.get("candidate_size"), "candidate_size"),
            candidate_sha256=_require_hash(data.get("candidate_sha256")),
            candidate_gems=_require_int(data.get("candidate_gems"), "candidate_gems"),
            remote_source=_require_text(data.get("remote_source"), "remote_source"),
            remote_size=_require_int(data.get("remote_size"), "remote_size"),
            remote_sha256=_require_hash(data.get("remote_sha256")),
        )
        if record.id != backup_id:
            raise BackupIntegrityError("El identificador del registro no coincide.")
        if not isinstance(data.get("changed"), bool):
            raise BackupIntegrityError("El registro de respaldo contiene changed inválido.")
        return record

    def load(self, backup_id: str) -> BackupBundle:
        """Carga y verifica el respaldo completo antes de cualquier reenvío."""
        record = self._read_record(backup_id)
        directory = self._directory(backup_id)
        original = self._read_private(directory / "original.json", self.limit)
        candidate = self._read_private(directory / "candidate.json", self.limit)
        if len(original) != record.original_size or sha256(original).hexdigest() != record.original_sha256:
            raise BackupIntegrityError("El original del respaldo no coincide con su registro.")
        if len(candidate) != record.candidate_size or sha256(candidate).hexdigest() != record.candidate_sha256:
            raise BackupIntegrityError("El candidato del respaldo no coincide con su registro.")
        reconstruct_cloud_save(original)
        if read_gems(original).gems != record.original_gems:
            raise BackupIntegrityError("El original del respaldo no conserva el valor registrado.")
        edit = prepare_gems_edit(original, record.candidate_gems)
        if (
            edit.changed != record.changed
            or edit.new_gems != record.candidate_gems
            or edit.candidate_sha256 != record.candidate_sha256
            or edit.candidate != candidate
        ):
            raise BackupIntegrityError("El candidato del respaldo no es reproducible desde el original.")
        return BackupBundle(record, original, candidate)

    def list(self, limit: int = 25) -> list[BackupRecord]:
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
            raise BackupStoreError("Límite de listado inválido.")
        if not self.root.exists():
            return []
        if not self.root.is_dir():
            raise BackupStoreError("La ruta de respaldos no es un directorio.")
        records: list[BackupRecord] = []
        try:
            entries = list(self.root.iterdir())
        except OSError:
            raise BackupStoreError("No se pudo leer el directorio de respaldos.") from None
        for entry in entries:
            if not _ID.fullmatch(entry.name) or entry.is_symlink() or not entry.is_dir():
                continue
            try:
                records.append(self._read_record(entry.name))
            except (BackupStoreError, OSError):
                continue
        records.sort(key=lambda record: (record.created_at, record.id), reverse=True)
        return records[:limit]

    def count(self) -> int:
        return len(self.list(limit=100))

    def append_event(self, backup_id: str, event: dict[str, Any]) -> None:
        """Añade una línea al diario privado; no acepta contenido de la partida."""
        directory = self._directory(backup_id)
        if not directory.is_dir():
            raise BackupNotFound("No se encontró el respaldo solicitado.")
        payload = {"at": _now(), **event}
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8") + b"\n"
        path = directory / "events.jsonl"
        flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW
        try:
            descriptor = os.open(path, flags, 0o600)
        except OSError:
            raise BackupStoreError("No se pudo abrir el diario del respaldo.") from None
        try:
            view = memoryview(encoded)
            while view:
                written = os.write(descriptor, view)
                view = view[written:]
        except OSError:
            raise BackupStoreError("No se pudo registrar el evento del respaldo.") from None
        finally:
            os.close(descriptor)

    def confirmation(self, backup_id: str) -> dict[str, Any] | None:
        path = self._directory(backup_id) / "confirmation.json"
        if not path.exists():
            return None
        raw = self._read_private(path, _RECORD_LIMIT)
        try:
            data = parse_json(raw)
        except (ValueError, RecursionError):
            raise BackupIntegrityError("La confirmación del respaldo no es JSON válido.") from None
        if not isinstance(data, dict):
            raise BackupIntegrityError("La confirmación del respaldo no es un objeto.")
        return data

    def save_confirmation(self, backup_id: str, result: dict[str, Any]) -> None:
        path = self._directory(backup_id) / "confirmation.json"
        encoded = json.dumps(result, ensure_ascii=False, sort_keys=True).encode("utf-8")
        try:
            self._write_private(path, encoded)
        except BackupStoreError:
            if path.exists():
                raise BackupAlreadyConfirmed("Este respaldo ya tiene una confirmación registrada.") from None
            raise

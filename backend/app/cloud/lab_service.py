"""Servicio de laboratorio para editar y verificar ``gameData.gems``.

Separa la lectura autenticada, la preparación local con respaldo, la escritura
remota opt-in y la verificación por descarga. La escritura solo existe si el
servicio se construye con ``write_enabled=True`` y un uploader; la autorización
administrativa se exige además en la capa HTTP.
"""

from __future__ import annotations

import re
import threading
from dataclasses import dataclass, field
from hmac import compare_digest
from typing import Literal, Protocol

from ..cloud_save import MAX_INPUT_BYTES, CloudSaveError, CopyLimitError
from .backup_store import BackupRecord, BackupStoreError, LabBackupStore
from .blob_upload import UploadResult
from .gems_editor import (
    GEMS_FIELD_ID,
    MAX_GEMS,
    MIN_GEMS,
    GemsEdit,
    prepare_gems_edit,
    read_gems,
)
from .provider import AcquiredCloudSave, CloudSaveMetadata


class LabServiceError(CloudSaveError):
    code = "cloud_lab"


class LabWriteDisabled(LabServiceError):
    code = "cloud_write_disabled"


class LabNoChanges(LabServiceError):
    code = "cloud_no_changes"


class LabHashMismatch(LabServiceError):
    code = "cloud_hash_mismatch"


class LabRemoteChanged(LabServiceError):
    code = "cloud_remote_changed"


class LabAlreadyConfirmed(LabServiceError):
    code = "cloud_already_confirmed"


_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class DownloadProvider(Protocol):
    def download(self, limit: int = MAX_INPUT_BYTES) -> AcquiredCloudSave: ...


class AggregateUploader(Protocol):
    def upload(self, aggregate: bytes) -> UploadResult: ...


@dataclass(frozen=True)
class LabStatus:
    mode: Literal["live", "read_only", "disabled"]
    read_ready: bool
    write_enabled: bool
    write_ready: bool
    admin_configured: bool
    backup_count: int
    min_gems: int
    max_gems: int
    message: str

    def summary(self) -> dict[str, object]:
        return {
            "mode": self.mode,
            "read_ready": self.read_ready,
            "write_enabled": self.write_enabled,
            "write_ready": self.write_ready,
            "admin_configured": self.admin_configured,
            "admin_required": True,
            "backup_count": self.backup_count,
            "min_gems": self.min_gems,
            "max_gems": self.max_gems,
            "message": self.message,
        }


@dataclass(frozen=True)
class LoadedSave:
    metadata: CloudSaveMetadata
    gems: int
    size: int
    sha256: str = field(repr=False)
    serialzed_version: int

    def summary(self) -> dict[str, object]:
        return {
            "remote": {
                "source": self.metadata.source,
                "size": self.metadata.size,
                "sha256": self.metadata.sha256,
            },
            "gems": self.gems,
            "size": self.size,
            "sha256": self.sha256,
            "serialzed_version": self.serialzed_version,
        }


@dataclass(frozen=True)
class PreparedEdit:
    backup: BackupRecord
    edit: GemsEdit
    remote_source: str

    @property
    def original_gems(self) -> int:
        return self.edit.original_gems

    @property
    def new_gems(self) -> int:
        return self.edit.new_gems

    @property
    def changed(self) -> bool:
        return self.edit.changed

    @property
    def candidate_sha256(self) -> str:
        return self.edit.candidate_sha256

    def summary(self) -> dict[str, object]:
        return {
            "remote": {
                "source": self.remote_source,
                "size": self.edit.binary.original_size,
                "sha256": self.edit.original_sha256,
            },
            "backup": self.backup.summary(),
            "original_gems": self.edit.original_gems,
            "new_gems": self.edit.new_gems,
            "changed": self.edit.changed,
            "candidate_size": len(self.edit.candidate),
            "candidate_sha256": self.edit.candidate_sha256,
            "byte_diff": self.edit.binary.as_dict(),
            "validation": {
                "valid": True,
                "structure_valid": True,
                "only_gems_changed": True,
                "message": (
                    "Solo cambia gameData.gems."
                    if self.edit.changed
                    else "El valor solicitado ya está en la partida; no hay cambios que subir."
                ),
            },
        }


@dataclass(frozen=True)
class WriteResult:
    action: Literal["confirm", "restore"]
    backup_id: str
    uploaded: bool
    accepted: bool
    persisted: bool
    already_original: bool
    expected_sha256: str = field(repr=False)
    remote_sha256: str | None = field(repr=False)
    remote_size: int | None
    remote_gems: int | None
    status: int | None
    message: str

    def summary(self) -> dict[str, object]:
        return {
            "action": self.action,
            "backup_id": self.backup_id,
            "uploaded": self.uploaded,
            "accepted": self.accepted,
            "persisted": self.persisted,
            "already_original": self.already_original,
            "expected_sha256": self.expected_sha256,
            "remote_sha256": self.remote_sha256,
            "remote_size": self.remote_size,
            "remote_gems": self.remote_gems,
            "status": self.status,
            "message": self.message,
        }


@dataclass(frozen=True)
class VerifyResult:
    backup_id: str
    matches_candidate: bool
    matches_original: bool
    remote_sha256: str = field(repr=False)
    remote_size: int
    remote_gems: int | None
    expected_candidate_sha256: str = field(repr=False)
    expected_original_sha256: str = field(repr=False)
    message: str

    def summary(self) -> dict[str, object]:
        return {
            "backup_id": self.backup_id,
            "matches_candidate": self.matches_candidate,
            "matches_original": self.matches_original,
            "remote_sha256": self.remote_sha256,
            "remote_size": self.remote_size,
            "remote_gems": self.remote_gems,
            "expected_candidate_sha256": self.expected_candidate_sha256,
            "expected_original_sha256": self.expected_original_sha256,
            "message": self.message,
        }


class CloudLabService:
    """Orquestador explícito; no crea credenciales ni activa la escritura."""

    def __init__(
        self,
        provider: DownloadProvider,
        store: LabBackupStore,
        *,
        uploader: AggregateUploader | None = None,
        write_enabled: bool = False,
        admin_configured: bool = False,
        max_input_bytes: int = MAX_INPUT_BYTES,
    ) -> None:
        if isinstance(max_input_bytes, bool) or not isinstance(max_input_bytes, int) or not 0 < max_input_bytes <= MAX_INPUT_BYTES:
            raise LabServiceError("Límite de lectura inválido.")
        self.provider = provider
        self.store = store
        self.uploader = uploader
        self.write_enabled = write_enabled
        self.admin_configured = admin_configured
        self.max_input_bytes = max_input_bytes
        self._write_lock = threading.Lock()

    def status(self) -> LabStatus:
        read_ready = True
        write_ready = self.write_enabled and self.uploader is not None and self.admin_configured
        if write_ready:
            mode: Literal["live", "read_only", "disabled"] = "live"
        else:
            mode = "read_only"
        backups: int
        try:
            backups = self.store.count()
        except BackupStoreError:
            backups = 0
        message = (
            "Laboratorio real con escritura administrativa habilitada."
            if mode == "live"
            else "Laboratorio en solo lectura: la escritura está deshabilitada en el servidor."
        )
        return LabStatus(
            mode=mode,
            read_ready=read_ready,
            write_enabled=self.write_enabled,
            write_ready=write_ready,
            admin_configured=self.admin_configured,
            backup_count=backups,
            min_gems=MIN_GEMS,
            max_gems=MAX_GEMS,
            message=message,
        )

    def load(self) -> LoadedSave:
        save = self.provider.download(self.max_input_bytes)
        snapshot = read_gems(save.payload)
        if snapshot.sha256 != save.metadata.sha256 or snapshot.size != save.metadata.size:
            raise LabServiceError("La copia descargada no coincide con sus metadatos.")
        return LoadedSave(
            metadata=save.metadata,
            gems=snapshot.gems,
            size=snapshot.size,
            sha256=snapshot.sha256,
            serialzed_version=snapshot.serialzed_version,
        )

    def _event(self, backup_id: str, event: dict[str, object]) -> None:
        """El diario no debe convertir una escritura remota ya hecha en un error."""
        try:
            self.store.append_event(backup_id, event)
        except BackupStoreError:
            pass

    def prepare(self, new_gems: object, *, expected_source: str | None = None) -> PreparedEdit:
        save = self.provider.download(self.max_input_bytes)
        if expected_source is not None and not compare_digest(expected_source, save.metadata.sha256):
            raise LabRemoteChanged("La partida remota cambió desde la descarga. Vuelve a descargarla.")
        edit = prepare_gems_edit(save.payload, new_gems)
        if edit.original_sha256 != save.metadata.sha256:
            raise LabServiceError("El original preparado no coincide con la descarga.")
        bundle = self.store.save(
            edit,
            remote_source=save.metadata.source,
            remote_size=save.metadata.size,
            remote_sha256=save.metadata.sha256,
        )
        self.store.append_event(
            bundle.record.id,
            {
                "action": "prepare",
                "changed": edit.changed,
                "original_gems": edit.original_gems,
                "candidate_gems": edit.new_gems,
                "candidate_sha256": edit.candidate_sha256,
                "remote_source": save.metadata.source,
            },
        )
        return PreparedEdit(bundle.record, edit, save.metadata.source)

    def confirm(self, backup_id: str, expected_sha256: str, *, single_attempt: bool = False) -> WriteResult:
        if not self.write_enabled or self.uploader is None:
            raise LabWriteDisabled("La escritura remota está deshabilitada en el servidor.")
        if not isinstance(expected_sha256, str) or not _SHA256.fullmatch(expected_sha256):
            raise LabHashMismatch("La huella esperada no es válida.")
        with self._write_lock:
            bundle = self.store.load(backup_id)
            if not bundle.record.changed:
                raise LabNoChanges("La operación no cambia las gemas; no se enviará nada a la nube.")
            if not compare_digest(expected_sha256, bundle.record.candidate_sha256):
                raise LabHashMismatch("La huella esperada no coincide con el candidato respaldado.")
            if self.store.confirmation(backup_id) is not None:
                raise LabAlreadyConfirmed("Este respaldo ya fue confirmado; usa la verificación.")
            current = self.provider.download(self.max_input_bytes)
            if current.metadata.sha256 != bundle.record.original_sha256:
                raise LabRemoteChanged(
                    "La partida remota cambió desde la preparación. Vuelve a cargarla antes de escribir."
                )
            if single_attempt:
                self.store.claim_confirmation_attempt(backup_id)
            upload = self.uploader.upload(bundle.candidate)
            remote = self.provider.download(self.max_input_bytes)
            persisted = (
                remote.metadata.size == bundle.record.candidate_size
                and compare_digest(remote.metadata.sha256, bundle.record.candidate_sha256)
            )
            try:
                remote_gems = read_gems(remote.payload).gems
            except CloudSaveError:
                remote_gems = None
            result = WriteResult(
                action="confirm",
                backup_id=backup_id,
                uploaded=True,
                accepted=upload.accepted,
                persisted=persisted,
                already_original=False,
                expected_sha256=bundle.record.candidate_sha256,
                remote_sha256=remote.metadata.sha256,
                remote_size=remote.metadata.size,
                remote_gems=remote_gems,
                status=upload.status,
                message=(
                    "La descarga posterior coincide con el agregado subido."
                    if persisted
                    else "La subida fue aceptada, pero la descarga posterior no coincide. No se declara persistencia."
                ),
            )
            if persisted:
                self.store.save_confirmation(backup_id, result.summary())
            self._event(
                backup_id,
                {
                    "action": "confirm",
                    "uploaded": True,
                    "accepted": upload.accepted,
                    "persisted": persisted,
                    "remote_sha256": remote.metadata.sha256,
                },
            )
            return result

    def restore(self, backup_id: str) -> WriteResult:
        if not self.write_enabled or self.uploader is None:
            raise LabWriteDisabled("La escritura remota está deshabilitada en el servidor.")
        with self._write_lock:
            bundle = self.store.load(backup_id)
            if not bundle.record.changed:
                raise LabNoChanges("El respaldo no contiene una modificación que restaurar.")
            current = self.provider.download(self.max_input_bytes)
            if current.metadata.sha256 == bundle.record.original_sha256:
                return WriteResult(
                    action="restore",
                    backup_id=backup_id,
                    uploaded=False,
                    accepted=False,
                    persisted=True,
                    already_original=True,
                    expected_sha256=bundle.record.original_sha256,
                    remote_sha256=current.metadata.sha256,
                    remote_size=current.metadata.size,
                    remote_gems=bundle.record.original_gems,
                    status=None,
                    message="La nube ya contiene el original; no se envió nada.",
                )
            if current.metadata.sha256 != bundle.record.candidate_sha256:
                raise LabRemoteChanged(
                    "La nube no coincide con el candidato confirmado; la restauración se detuvo."
                )
            upload = self.uploader.upload(bundle.original)
            remote = self.provider.download(self.max_input_bytes)
            persisted = (
                remote.metadata.size == bundle.record.original_size
                and compare_digest(remote.metadata.sha256, bundle.record.original_sha256)
            )
            try:
                remote_gems = read_gems(remote.payload).gems
            except CloudSaveError:
                remote_gems = None
            result = WriteResult(
                action="restore",
                backup_id=backup_id,
                uploaded=True,
                accepted=upload.accepted,
                persisted=persisted,
                already_original=False,
                expected_sha256=bundle.record.original_sha256,
                remote_sha256=remote.metadata.sha256,
                remote_size=remote.metadata.size,
                remote_gems=remote_gems,
                status=upload.status,
                message=(
                    "La descarga posterior coincide con el original respaldado."
                    if persisted
                    else "La restauración fue aceptada, pero la descarga posterior no coincide con el original."
                ),
            )
            self._event(
                backup_id,
                {
                    "action": "restore",
                    "persisted": persisted,
                    "remote_sha256": remote.metadata.sha256,
                },
            )
            return result

    def verify(self, backup_id: str) -> VerifyResult:
        bundle = self.store.load(backup_id)
        remote = self.provider.download(self.max_input_bytes)
        matches_candidate = (
            remote.metadata.size == bundle.record.candidate_size
            and compare_digest(remote.metadata.sha256, bundle.record.candidate_sha256)
        )
        matches_original = (
            remote.metadata.size == bundle.record.original_size
            and compare_digest(remote.metadata.sha256, bundle.record.original_sha256)
        )
        try:
            remote_gems = read_gems(remote.payload).gems
        except CloudSaveError:
            remote_gems = None
        self._event(
            backup_id,
            {
                "action": "verify",
                "matches_candidate": matches_candidate,
                "matches_original": matches_original,
                "remote_sha256": remote.metadata.sha256,
            },
        )
        if matches_candidate:
            message = "La nube conserva exactamente el candidato respaldado."
        elif matches_original:
            message = "La nube contiene el original; el candidato no está aplicado."
        else:
            message = "La nube no coincide ni con el original ni con el candidato de este respaldo."
        return VerifyResult(
            backup_id=backup_id,
            matches_candidate=matches_candidate,
            matches_original=matches_original,
            remote_sha256=remote.metadata.sha256,
            remote_size=remote.metadata.size,
            remote_gems=remote_gems,
            expected_candidate_sha256=bundle.record.candidate_sha256,
            expected_original_sha256=bundle.record.original_sha256,
            message=message,
        )

    def backups(self, limit: int = 25) -> list[BackupRecord]:
        return self.store.list(limit=limit)


def build_cloud_lab(settings: object) -> CloudLabService | None:
    """Construye el servicio solo si la configuración privada está completa.

    El import se hace aquí para que la aplicación pueda importarse sin cargar
    módulos de red y para que los tests inyecten su propio servicio.
    """
    from .blob_upload import BlobSaveUploader
    from .modern import ModernCloudSaveProvider

    session_token = getattr(settings, "cloud_session_token", None)
    unique_id = getattr(settings, "cloud_unique_id", None)
    distro_id = getattr(settings, "cloud_distro_id", None)
    if not (session_token and unique_id and distro_id):
        return None
    token = session_token.get_secret_value()
    device = unique_id.get_secret_value()
    distro = distro_id.get_secret_value()
    write_enabled = bool(getattr(settings, "cloud_write_enabled", False))
    admin = getattr(settings, "cloud_admin_token", None)
    admin_configured = admin is not None
    provider = ModernCloudSaveProvider(token, device, distro)
    store = LabBackupStore(getattr(settings, "cloud_backup_dir"))
    uploader = None
    if write_enabled and admin_configured:
        uploader = BlobSaveUploader(token, device, distro, enabled=True)
    return CloudLabService(
        provider,
        store,
        uploader=uploader,
        write_enabled=write_enabled,
        admin_configured=admin_configured,
    )

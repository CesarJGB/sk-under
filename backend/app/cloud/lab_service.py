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
from hashlib import sha256
from hmac import compare_digest
from typing import Literal, Protocol

from ..cloud_save import MAX_INPUT_BYTES, CloudSaveError, CopyLimitError
from ..save_report import read_save_report
from .backup_store import BackupRecord, BackupStoreError, LabBackupStore
from .blob_upload import UploadResult
from .advanced_editor import (
    ADVANCED_RECORD_FIELD,
    BATTLE_PASS_PATH,
    MATERIALS_PATH,
    REBORN_PATH,
    SEASON_COIN_PATH,
    SEEDS_PATH,
    AdvancedEdit,
    prepare_advanced_edit,
    PETS_PATH,
    read_advanced_source,
    require_advanced_write_compatibility,
)
from .character_editor import (
    CHARACTER_PATH,
    CHARACTER_RECORD_FIELD,
    CharacterEdit,
    prepare_character_unlock_edit,
    read_characters,
    require_character_write_compatibility,
)
from .fish_chip_editor import (
    FISH_CHIP_PATH,
    FISH_CHIP_RECORD_FIELD,
    FISH_EDIT_PATHS,
    MATERIAL_FISH_PATH,
    MAX_FISH_CHIP,
    MIN_FISH_CHIP,
    FishChipEdit,
    FishChipFieldMissing,
    prepare_fish_chip_edit,
    read_fish_chip,
    require_fish_chip_write_compatibility,
)
from .fish_progress_editor import (
    PROGRESS_PATH,
    PROGRESS_RECORD_FIELD,
    FishProgressEdit,
    prepare_fish_progress_edit,
    read_fish_progress,
    require_fish_progress_write_compatibility,
)
from .gems_editor import (
    GEMS_FIELD_ID,
    MAX_GEMS,
    MIN_GEMS,
    GemsEdit,
    prepare_gems_edit,
    read_gems,
    require_gems_write_compatibility,
)
from .provider import AcquiredCloudSave, CloudSaveMetadata
from .skill_editor import (
    SKILL_PATH,
    SKILL_RECORD_FIELD,
    SkillEdit,
    prepare_skill_unlock_edit,
    read_skills,
    require_skill_write_compatibility,
)
from .skin_editor import (
    SKIN_PATH,
    SKIN_RECORD_FIELD,
    SkinEdit,
    prepare_skin_unlock_edit,
    read_skins,
    require_skin_write_compatibility,
)
from .unified_editor import (
    UNIFIED_RECORD_FIELD,
    UnifiedEdit,
    prepare_unified_edit,
    require_unified_write_compatibility,
)


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
    min_fish_chip: int = MIN_FISH_CHIP
    max_fish_chip: int = MAX_FISH_CHIP

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
            "min_fish_chip": self.min_fish_chip,
            "max_fish_chip": self.max_fish_chip,
            "fish_chip_write_policy": "confirmed_by_owner",
            "character_write_policy": "confirmed_by_owner",
            "skill_write_policy": "confirmed_by_owner",
            "skin_write_policy": "confirmed_by_owner",
            "message": self.message,
        }


@dataclass(frozen=True)
class LoadedSave:
    metadata: CloudSaveMetadata
    gems: int
    size: int
    sha256: str = field(repr=False)
    serialzed_version: int
    report: dict[str, object]
    fish_chip: int | None = None
    material_fish: int | None = None
    cumulative_fish_count: int | None = None
    advanced: dict[str, object] = field(default_factory=dict)

    def summary(self) -> dict[str, object]:
        return {
            "remote": {
                "source": self.metadata.source,
                "size": self.metadata.size,
                "sha256": self.metadata.sha256,
            },
            "gems": self.gems,
            "fish_chip": self.fish_chip,
            "fish_chip_path": FISH_CHIP_PATH,
            "material_fish": self.material_fish,
            "material_fish_path": MATERIAL_FISH_PATH,
            "cumulative_fish_count": self.cumulative_fish_count,
            "cumulative_fish_count_path": PROGRESS_PATH,
            "fish_chip_write_policy": "confirmed_by_owner",
            "character_write_policy": "confirmed_by_owner",
            "skill_write_policy": "confirmed_by_owner",
            "skin_write_policy": "confirmed_by_owner",
            "size": self.size,
            "sha256": self.sha256,
            "serialzed_version": self.serialzed_version,
            "report": self.report,
            "advanced": self.advanced,
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
            "field": "gameData.gems",
            "remote": {
                "source": self.remote_source,
                "size": self.edit.binary.original_size,
                "sha256": self.edit.original_sha256,
            },
            "backup": self.backup.summary(),
            "original_gems": self.edit.original_gems,
            "new_gems": self.edit.new_gems,
            "original_value": self.edit.original_gems,
            "new_value": self.edit.new_gems,
            "changed": self.edit.changed,
            "candidate_size": len(self.edit.candidate),
            "candidate_sha256": self.edit.candidate_sha256,
            "byte_diff": self.edit.binary.as_dict(),
            "changed_fields": list(self.edit.changed_fields),
            "validation": {
                "valid": True,
                "structure_valid": True,
                "only_gems_changed": "gameData.varGems" not in self.edit.changed_fields,
                "message": (
                    "Campos modificados: " + ", ".join(self.edit.changed_fields) + "."
                    if self.edit.changed
                    else "El valor solicitado ya está en la partida; no hay cambios que subir."
                ),
            },
        }


@dataclass(frozen=True)
class PreparedFishChipEdit:
    """Resultado experimental de preparar un cambio de ``gameData.fishChip``."""

    backup: BackupRecord
    edit: FishChipEdit
    remote_source: str

    @property
    def original_fish_chip(self) -> int:
        return self.edit.original_fish_chip

    @property
    def new_fish_chip(self) -> int:
        return self.edit.new_fish_chip

    @property
    def original_material_fish(self) -> int | None:
        return self.edit.original_material_fish

    @property
    def new_material_fish(self) -> int:
        return self.edit.new_material_fish

    @property
    def changed(self) -> bool:
        return self.edit.changed

    @property
    def candidate_sha256(self) -> str:
        return self.edit.candidate_sha256

    def summary(self) -> dict[str, object]:
        return {
            "field": FISH_CHIP_PATH,
            "material_fish_path": MATERIAL_FISH_PATH,
            "remote": {
                "source": self.remote_source,
                "size": self.edit.binary.original_size,
                "sha256": self.edit.original_sha256,
            },
            "backup": self.backup.summary(),
            "original_fish_chip": self.edit.original_fish_chip,
            "new_fish_chip": self.edit.new_fish_chip,
            "original_material_fish": self.edit.original_material_fish,
            "new_material_fish": self.edit.new_material_fish,
            "original_value": self.edit.original_fish_chip,
            "new_value": self.edit.new_fish_chip,
            "changed": self.edit.changed,
            "candidate_size": len(self.edit.candidate),
            "candidate_sha256": self.edit.candidate_sha256,
            "byte_diff": self.edit.binary.as_dict(),
            "changed_fields": list(self.edit.changed_fields),
            "experimental": True,
            "validation": {
                "valid": True,
                "structure_valid": True,
                "only_fish_fields_changed": self.edit.changed
                and set(self.edit.changed_fields) <= set(FISH_EDIT_PATHS),
                "experimental": True,
                "evidence_level": "E2",
                "message": (
                    "Campos modificados: " + ", ".join(self.edit.changed_fields) + "."
                    if self.edit.changed
                    else "El valor solicitado ya está en la partida; no hay cambios que subir."
                ),
            },
        }


@dataclass(frozen=True)
class PreparedFishProgressEdit:
    """Resultado experimental de preparar el progreso acumulado de fichas."""

    backup: BackupRecord
    edit: FishProgressEdit
    remote_source: str

    @property
    def changed(self) -> bool:
        return self.edit.changed

    @property
    def candidate_sha256(self) -> str:
        return self.edit.candidate_sha256

    def summary(self) -> dict[str, object]:
        return {
            "field": PROGRESS_PATH,
            "remote": {
                "source": self.remote_source,
                "size": self.edit.binary.original_size,
                "sha256": self.edit.original_sha256,
            },
            "backup": self.backup.summary(),
            "original_cumulative_fish_count": self.edit.original_cumulative_fish_count,
            "new_cumulative_fish_count": self.edit.new_cumulative_fish_count,
            "original_value": self.edit.original_cumulative_fish_count,
            "new_value": self.edit.new_cumulative_fish_count,
            "changed": self.edit.changed,
            "candidate_size": len(self.edit.candidate),
            "candidate_sha256": self.edit.candidate_sha256,
            "byte_diff": self.edit.binary.as_dict(),
            "changed_fields": list(self.edit.changed_fields),
            "experimental": True,
            "validation": {
                "valid": True,
                "structure_valid": True,
                "only_fish_progress_changed": self.edit.changed
                and set(self.edit.changed_fields) <= {PROGRESS_PATH},
                "experimental": True,
                "evidence_level": "E2",
                "message": (
                    "Campo modificado: " + ", ".join(self.edit.changed_fields) + "."
                    if self.edit.changed
                    else "El valor solicitado ya está en la partida; no hay cambios que subir."
                ),
            },
        }


@dataclass(frozen=True)
class PreparedAdvancedEdit:
    """Resultado experimental del editor avanzado por lotes."""

    backup: BackupRecord
    edit: AdvancedEdit
    remote_source: str

    @property
    def changed(self) -> bool:
        return self.edit.changed

    @property
    def candidate_sha256(self) -> str:
        return self.edit.candidate_sha256

    def summary(self) -> dict[str, object]:
        prefixes = (MATERIALS_PATH + ".", SEEDS_PATH + ".", BATTLE_PASS_PATH + ".", PETS_PATH + ".")
        only_advanced = self.edit.changed and all(
            path == SEASON_COIN_PATH
            or path == REBORN_PATH
            or path.startswith(prefixes)
            for path in self.edit.changed_fields
        )
        plan = self.edit.plan
        experimental = bool(plan.get("battle_pass"))
        evidence_level = "E2" if experimental else "E3"
        message = (
            "Campos modificados: " + ", ".join(self.edit.changed_fields) + ". "
            "No se modifican gemas, fichas de pesca, recompensas reclamadas ni recibos. "
            + (
                "Esta operación incluye el pase de batalla, que conserva evidencia experimental E2."
                if experimental
                else "Materiales, semillas, moneda de temporada, renacimiento, mascotas, skins y "
                "alimento están confirmados por el propietario en Android físico."
            )
        ) if self.edit.changed else "Los valores solicitados ya están en la partida; no hay cambios que subir."
        return {
            "field": ADVANCED_RECORD_FIELD,
            "remote": {
                "source": self.remote_source,
                "size": self.edit.original_size,
                "sha256": self.edit.original_sha256,
            },
            "backup": self.backup.summary(),
            "changes": [change.summary() for change in self.edit.changes],
            "plan": self.edit.plan,
            "original_value": 0,
            "new_value": len(self.edit.changes),
            "changed": self.edit.changed,
            "candidate_size": self.edit.candidate_size,
            "candidate_sha256": self.edit.candidate_sha256,
            "byte_diff": self.edit.binary.as_dict(),
            "changed_fields": list(self.edit.changed_fields),
            "experimental": experimental,
            "validation": {
                "valid": True,
                "structure_valid": True,
                "only_advanced_changed": only_advanced,
                "experimental": experimental,
                "evidence_level": evidence_level,
                "message": message,
            },
        }


@dataclass(frozen=True)
class PreparedUnifiedEdit:
    """Resultado de una edición compuesta: un candidato y un solo respaldo."""

    backup: BackupRecord
    edit: UnifiedEdit
    remote_source: str

    @property
    def changed(self) -> bool:
        return self.edit.changed

    @property
    def candidate_sha256(self) -> str:
        return self.edit.candidate_sha256

    def summary(self) -> dict[str, object]:
        return {
            "field": UNIFIED_RECORD_FIELD,
            "remote": {
                "source": self.remote_source,
                "size": self.edit.original_size,
                "sha256": self.edit.original_sha256,
            },
            "backup": self.backup.summary(),
            "plan": self.edit.plan,
            "categories": [category.summary() for category in self.edit.categories],
            "steps": list(self.edit.steps),
            "change_count": self.edit.change_count,
            "original_value": 0,
            "new_value": self.edit.change_count,
            "changed": self.edit.changed,
            "candidate_size": self.edit.candidate_size,
            "candidate_sha256": self.edit.candidate_sha256,
            "byte_diff": self.edit.binary.as_dict(),
            "changed_fields": list(self.edit.changed_fields),
            "validation": {
                "valid": True,
                "structure_valid": True,
                "atomic": True,
                "message": (
                    "Campos modificados: " + ", ".join(self.edit.changed_fields) + ". "
                    "La operación se compone sobre un único candidato y se sube una sola vez."
                    if self.edit.changed
                    else "Los valores solicitados ya están en la partida; no hay cambios que subir."
                ),
            },
        }


@dataclass(frozen=True)
class PreparedCharacterEdit:
    """Resultado experimental de preparar un desbloqueo de personajes."""

    backup: BackupRecord
    edit: CharacterEdit
    remote_source: str

    @property
    def changed(self) -> bool:
        return self.edit.changed

    @property
    def candidate_sha256(self) -> str:
        return self.edit.candidate_sha256

    def summary(self) -> dict[str, object]:
        return {
            "field": CHARACTER_PATH,
            "remote": {
                "source": self.remote_source,
                "size": self.edit.binary.original_size,
                "sha256": self.edit.original_sha256,
            },
            "backup": self.backup.summary(),
            "original_unlocked_count": len(self.edit.original_unlocked),
            "new_unlocked_count": len(self.edit.new_unlocked),
            "total_characters": self.edit.total,
            "selected_codes": list(self.edit.selected_codes),
            "newly_unlocked_codes": list(self.edit.newly_unlocked),
            "original_value": len(self.edit.original_unlocked),
            "new_value": len(self.edit.new_unlocked),
            "changed": self.edit.changed,
            "candidate_size": len(self.edit.candidate),
            "candidate_sha256": self.edit.candidate_sha256,
            "byte_diff": self.edit.binary.as_dict(),
            "changed_fields": list(self.edit.changed_fields),
            "experimental": False,
            "validation": {
                "valid": True,
                "structure_valid": True,
                "only_characters_changed": self.edit.changed
                and all(path.startswith(CHARACTER_PATH + ".") for path in self.edit.changed_fields),
                "experimental": False,
                "evidence_level": "confirmed_by_owner",
                "message": (
                    "Campos modificados: " + ", ".join(self.edit.changed_fields) + ". "
                    "Niveles, habilidades y skins no se modifican. El desbloqueo fue "
                    "confirmado por el propietario en Android físico."
                    if self.edit.changed
                    else "Los personajes seleccionados ya están disponibles; no hay cambios que subir."
                ),
            },
        }


@dataclass(frozen=True)
class PreparedSkillEdit:
    """Resultado de preparar un desbloqueo de habilidades confirmado por el propietario."""

    backup: BackupRecord
    edit: SkillEdit
    remote_source: str

    @property
    def changed(self) -> bool:
        return self.edit.changed

    @property
    def candidate_sha256(self) -> str:
        return self.edit.candidate_sha256

    def summary(self) -> dict[str, object]:
        return {
            "field": SKILL_PATH,
            "remote": {
                "source": self.remote_source,
                "size": self.edit.binary.original_size,
                "sha256": self.edit.original_sha256,
            },
            "backup": self.backup.summary(),
            "original_unlocked_count": len(self.edit.original_unlocked),
            "new_unlocked_count": len(self.edit.new_unlocked),
            "total_skills": self.edit.total,
            "selected_skills": [ref.as_dict() for ref in self.edit.selected_skills],
            "newly_unlocked_skills": [ref.as_dict() for ref in self.edit.newly_unlocked],
            "affected_codes": list(self.edit.affected_codes),
            "original_value": len(self.edit.original_unlocked),
            "new_value": len(self.edit.new_unlocked),
            "changed": self.edit.changed,
            "candidate_size": len(self.edit.candidate),
            "candidate_sha256": self.edit.candidate_sha256,
            "byte_diff": self.edit.binary.as_dict(),
            "changed_fields": list(self.edit.changed_fields),
            "experimental": False,
            "validation": {
                "valid": True,
                "structure_valid": True,
                "only_skills_changed": self.edit.changed
                and all(path.startswith(SKILL_PATH + ".") for path in self.edit.changed_fields),
                "experimental": False,
                "evidence_level": "E3",
                "message": (
                    "Campos modificados: " + ", ".join(self.edit.changed_fields) + ". "
                    "gameData.heroSkill y los demás campos no se modifican. El propietario "
                    "confirmó el desbloqueo en el cliente oficial y Android físico."
                    if self.edit.changed
                    else "Las habilidades seleccionadas ya están disponibles; no hay cambios que subir."
                ),
            },
        }


@dataclass(frozen=True)
class PreparedSkinEdit:
    """Resultado de preparar un desbloqueo de skins confirmado por el propietario."""

    backup: BackupRecord
    edit: SkinEdit
    remote_source: str

    @property
    def changed(self) -> bool:
        return self.edit.changed

    @property
    def candidate_sha256(self) -> str:
        return self.edit.candidate_sha256

    def summary(self) -> dict[str, object]:
        return {
            "field": SKIN_PATH,
            "remote": {
                "source": self.remote_source,
                "size": self.edit.binary.original_size,
                "sha256": self.edit.original_sha256,
            },
            "backup": self.backup.summary(),
            "original_unlocked_count": len(self.edit.original_unlocked),
            "new_unlocked_count": len(self.edit.new_unlocked),
            "total_skins": self.edit.total,
            "selected_skins": [ref.as_dict() for ref in self.edit.selected_skins],
            "newly_unlocked_skins": [ref.as_dict() for ref in self.edit.newly_unlocked],
            "affected_codes": list(self.edit.affected_codes),
            "locked_character_codes": list(self.edit.locked_character_codes),
            "original_value": len(self.edit.original_unlocked),
            "new_value": len(self.edit.new_unlocked),
            "changed": self.edit.changed,
            "candidate_size": len(self.edit.candidate),
            "candidate_sha256": self.edit.candidate_sha256,
            "byte_diff": self.edit.binary.as_dict(),
            "changed_fields": list(self.edit.changed_fields),
            "experimental": False,
            "validation": {
                "valid": True,
                "structure_valid": True,
                "only_skins_changed": self.edit.changed
                and all(path.startswith(SKIN_PATH + ".") for path in self.edit.changed_fields),
                "experimental": False,
                "evidence_level": "E3",
                "message": (
                    "Campos modificados: " + ", ".join(self.edit.changed_fields) + ". "
                    "gameData.currentSkinDatas, gameData.heroUnlock y los demás campos no se "
                    "modifican. El propietario confirmó el desbloqueo en el cliente oficial y "
                    "Android físico; solo se activan posiciones existentes con Value=1."
                    if self.edit.changed
                    else "Las skins seleccionadas ya están desbloqueadas; no hay cambios que subir."
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
    field: str = "gems"
    remote_value: int | None = None
    remote_material_fish: int | None = None
    remote_characters: int | None = None
    remote_skills: int | None = None
    remote_skins: int | None = None
    historical: bool = False
    preventive_backup_id: str | None = None

    def summary(self) -> dict[str, object]:
        return {
            "action": self.action,
            "backup_id": self.backup_id,
            "field": self.field,
            "uploaded": self.uploaded,
            "accepted": self.accepted,
            "persisted": self.persisted,
            "already_original": self.already_original,
            "historical": self.historical,
            "preventive_backup_id": self.preventive_backup_id,
            "expected_sha256": self.expected_sha256,
            "remote_sha256": self.remote_sha256,
            "remote_size": self.remote_size,
            "remote_gems": self.remote_gems,
            "remote_value": self.remote_value,
            "remote_material_fish": self.remote_material_fish,
            "remote_characters": self.remote_characters,
            "remote_skills": self.remote_skills,
            "remote_skins": self.remote_skins,
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
    field: str = "gems"
    remote_value: int | None = None
    remote_material_fish: int | None = None
    remote_characters: int | None = None
    remote_skills: int | None = None
    remote_skins: int | None = None

    def summary(self) -> dict[str, object]:
        return {
            "backup_id": self.backup_id,
            "field": self.field,
            "matches_candidate": self.matches_candidate,
            "matches_original": self.matches_original,
            "remote_sha256": self.remote_sha256,
            "remote_size": self.remote_size,
            "remote_gems": self.remote_gems,
            "remote_value": self.remote_value,
            "remote_material_fish": self.remote_material_fish,
            "remote_characters": self.remote_characters,
            "remote_skills": self.remote_skills,
            "remote_skins": self.remote_skins,
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
            min_fish_chip=MIN_FISH_CHIP,
            max_fish_chip=MAX_FISH_CHIP,
            message=message,
        )

    def load(self) -> LoadedSave:
        save = self.provider.download(self.max_input_bytes)
        snapshot = read_gems(save.payload)
        if snapshot.sha256 != save.metadata.sha256 or snapshot.size != save.metadata.size:
            raise LabServiceError("La copia descargada no coincide con sus metadatos.")
        try:
            fish_snapshot = read_fish_chip(save.payload)
            fish_chip = fish_snapshot.fish_chip
            material_fish = fish_snapshot.material_fish
        except (FishChipFieldMissing, CloudSaveError):
            fish_chip = None
            material_fish = None
        try:
            cumulative_fish_count = read_fish_progress(save.payload).cumulative_fish_count
        except CloudSaveError:
            cumulative_fish_count = None
        try:
            advanced = read_advanced_source(save.payload)
        except CloudSaveError as exc:
            advanced = {"available": False, "error": str(exc)}
        return LoadedSave(
            metadata=save.metadata,
            gems=snapshot.gems,
            fish_chip=fish_chip,
            material_fish=material_fish,
            cumulative_fish_count=cumulative_fish_count,
            advanced=advanced,
            size=snapshot.size,
            sha256=snapshot.sha256,
            serialzed_version=snapshot.serialzed_version,
            report=read_save_report(save.payload),
        )

    def _event(self, backup_id: str, event: dict[str, object]) -> None:
        """El diario no debe convertir una escritura remota ya hecha en un error."""
        try:
            self.store.append_event(backup_id, event)
        except BackupStoreError:
            pass

    def _snapshot_summary(self, payload: bytes) -> dict[str, object]:
        """Resumen saneado de la partida para el historial, sin rutas ni hashes."""
        summary: dict[str, object] = {"save_size": len(payload)}
        try:
            gems = read_gems(payload)
            summary["gems"] = gems.gems
            summary["serialzed_version"] = gems.serialzed_version
        except CloudSaveError:
            pass
        try:
            fish = read_fish_chip(payload)
            summary["fish_chip"] = fish.fish_chip
            summary["material_fish"] = fish.material_fish
        except CloudSaveError:
            pass
        try:
            summary["cumulative_fish_count"] = read_fish_progress(payload).cumulative_fish_count
        except CloudSaveError:
            pass
        try:
            summary["characters"] = len(read_characters(payload).unlocked)
        except CloudSaveError:
            pass
        try:
            summary["skills"] = len(read_skills(payload).unlocked)
        except CloudSaveError:
            pass
        try:
            summary["skins"] = len(read_skins(payload).unlocked)
        except CloudSaveError:
            pass
        try:
            summary["game_version"] = read_save_report(payload).get("game_version")
        except CloudSaveError:
            pass
        return summary

    def create_manual_backup(self) -> BackupRecord:
        """Crea una copia verificada sin escribir nada en ChillyRoom."""
        save = self.provider.download(self.max_input_bytes)
        if save.metadata.size != len(save.payload) or not compare_digest(
            save.metadata.sha256, sha256(save.payload).hexdigest()
        ):
            raise LabServiceError("La copia descargada no coincide con sus metadatos.")
        summary = self._snapshot_summary(save.payload)
        bundle = self.store.save_snapshot(
            save.payload,
            kind="manual",
            remote_source=save.metadata.source,
            remote_size=save.metadata.size,
            remote_sha256=save.metadata.sha256,
            snapshot=summary,
        )
        self._event(
            bundle.record.id,
            {
                "action": "snapshot",
                "kind": "manual",
                "size": bundle.record.original_size,
                "changed": False,
            },
        )
        return bundle.record

    def restore_history(
        self, backup_id: str, *, expected_sha256: str | None = None
    ) -> WriteResult:
        """Restaura cualquier copia verificable creando antes un punto preventivo.

        A diferencia de ``restore``, no exige que la nube contenga el candidato:
        recupera los bytes originales del respaldo y conserva el estado actual
        como un respaldo independiente que permite deshacer la operación.
        """
        if not self.write_enabled or self.uploader is None:
            raise LabWriteDisabled("La escritura remota está deshabilitada en el servidor.")
        if expected_sha256 is not None and (
            not isinstance(expected_sha256, str) or not _SHA256.fullmatch(expected_sha256)
        ):
            raise LabHashMismatch("La huella esperada no es válida.")
        with self._write_lock:
            bundle = self.store.load(backup_id)
            label = (
                "la copia completa de la partida"
                if bundle.record.is_snapshot
                else self._field_label(bundle.record.field)
            )
            if not bundle.record.is_snapshot and not bundle.record.changed:
                raise LabNoChanges("El respaldo no contiene una modificación que restaurar.")
            current = self.provider.download(self.max_input_bytes)
            if expected_sha256 is not None and not compare_digest(expected_sha256, current.metadata.sha256):
                raise LabRemoteChanged(
                    "La partida remota cambió desde que abriste el historial. Actualiza la partida y vuelve a intentarlo."
                )
            target_sha256 = bundle.record.original_sha256
            if current.metadata.sha256 == target_sha256:
                remote_gems, remote_value, remote_material, remote_characters, remote_skills, remote_skins = self._remote_values(
                    current.payload, bundle.record.field
                )
                return WriteResult(
                    action="restore",
                    backup_id=backup_id,
                    uploaded=False,
                    accepted=False,
                    persisted=True,
                    already_original=True,
                    expected_sha256=target_sha256,
                    remote_sha256=current.metadata.sha256,
                    remote_size=current.metadata.size,
                    remote_gems=remote_gems,
                    status=None,
                    field=self._field_path(bundle.record.field),
                    remote_value=remote_value,
                    remote_material_fish=remote_material,
                    remote_characters=remote_characters,
                    remote_skills=remote_skills,
                    remote_skins=remote_skins,
                    historical=True,
                    message="La nube ya contiene exactamente este respaldo; no se envió nada.",
                )
            preventive = self.store.save_snapshot(
                current.payload,
                kind="preventive",
                remote_source=current.metadata.source,
                remote_size=current.metadata.size,
                remote_sha256=current.metadata.sha256,
                snapshot=self._snapshot_summary(current.payload),
            )
            self._event(
                preventive.record.id,
                {"action": "preventive", "for_backup": backup_id, "size": preventive.record.original_size},
            )
            # La descarga previa al respaldo preventivo debe seguir siendo la
            # misma justo antes de escribir; si no, no se toca la nube.
            check = self.provider.download(self.max_input_bytes)
            if not compare_digest(check.metadata.sha256, current.metadata.sha256):
                raise LabRemoteChanged(
                    "La partida remota cambió mientras se preparaba la restauración. "
                    "Se conservó un respaldo preventivo y no se escribió nada."
                )
            upload = self.uploader.upload(bundle.original)
            remote = self.provider.download(self.max_input_bytes)
            persisted = (
                remote.metadata.size == bundle.record.original_size
                and compare_digest(remote.metadata.sha256, target_sha256)
            )
            remote_gems, remote_value, remote_material, remote_characters, remote_skills, remote_skins = self._remote_values(
                remote.payload, bundle.record.field
            )
            result = WriteResult(
                action="restore",
                backup_id=backup_id,
                uploaded=True,
                accepted=upload.accepted,
                persisted=persisted,
                already_original=False,
                expected_sha256=target_sha256,
                remote_sha256=remote.metadata.sha256,
                remote_size=remote.metadata.size,
                remote_gems=remote_gems,
                status=upload.status,
                field=self._field_path(bundle.record.field),
                remote_value=remote_value,
                remote_material_fish=remote_material,
                remote_characters=remote_characters,
                remote_skills=remote_skills,
                remote_skins=remote_skins,
                historical=True,
                preventive_backup_id=preventive.record.id,
                message=(
                    f"La descarga posterior coincide con {label}. "
                    "El estado anterior quedó guardado como respaldo preventivo."
                    if persisted
                    else "La restauración fue aceptada, pero la descarga posterior no coincide. "
                    "El estado anterior sigue guardado como respaldo preventivo."
                ),
            )
            self._event(
                backup_id,
                {
                    "action": "restore",
                    "mode": "historical",
                    "persisted": persisted,
                    "remote_sha256": remote.metadata.sha256,
                    "preventive_backup_id": preventive.record.id,
                },
            )
            return result

    @staticmethod
    def _field_path(field: str) -> str:
        if field == "snapshot":
            return "snapshot"
        if field == FISH_CHIP_RECORD_FIELD:
            return FISH_CHIP_PATH
        if field == PROGRESS_RECORD_FIELD:
            return PROGRESS_PATH
        if field == CHARACTER_RECORD_FIELD:
            return CHARACTER_PATH
        if field == SKILL_RECORD_FIELD:
            return SKILL_PATH
        if field == SKIN_RECORD_FIELD:
            return SKIN_PATH
        if field == ADVANCED_RECORD_FIELD:
            return (
                "itemData.materials, itemData.seeds, seasonData.coin, gameData.rebornCard, "
                "battlePassSaveData.seasonData, gameData.petUnlock, statisticData.event2Count"
            )
        if field == UNIFIED_RECORD_FIELD:
            return "gameData, itemData y seasonData (edición unificada)"
        return "gameData.gems"

    @staticmethod
    def _field_label(field: str) -> str:
        if field == "snapshot":
            return "la copia completa de la partida"
        if field == FISH_CHIP_RECORD_FIELD:
            return "las fichas de pesca"
        if field == PROGRESS_RECORD_FIELD:
            return "el progreso acumulado de fichas de pesca"
        if field == CHARACTER_RECORD_FIELD:
            return "los personajes"
        if field == SKILL_RECORD_FIELD:
            return "las habilidades"
        if field == SKIN_RECORD_FIELD:
            return "las skins"
        if field == ADVANCED_RECORD_FIELD:
            return (
                "los materiales, las semillas, las monedas de temporada, la tarjeta de "
                "renacimiento, el pase de batalla y las mascotas"
            )
        if field == UNIFIED_RECORD_FIELD:
            return "los cambios seleccionados"
        return "las gemas"

    @staticmethod
    def _persisted_message(field: str, label: str) -> str:
        if field == FISH_CHIP_RECORD_FIELD:
            return (
                f"La descarga posterior coincide con el agregado subido de {label}. "
                "La efectividad dentro del juego fue confirmada por el propietario."
            )
        if field == PROGRESS_RECORD_FIELD:
            return (
                f"La descarga posterior coincide con el agregado subido de {label}. "
                "La barra de recompensas aún no se ha comprobado en Android."
            )
        if field == ADVANCED_RECORD_FIELD:
            return (
                f"La descarga posterior coincide con el agregado subido de {label}. "
                "Los materiales, semillas, moneda de temporada, renacimiento y progreso de pesca "
                "fueron confirmados por el propietario en Android físico. El pase de batalla y "
                "las mascotas siguen como experimentales E2."
            )
        if field == UNIFIED_RECORD_FIELD:
            return (
                f"La descarga posterior coincide con el agregado subido de {label}. "
                "Se subió un único candidato compuesto y se conserva el respaldo restaurable."
            )
        if field == CHARACTER_RECORD_FIELD:
            return (
                f"La descarga posterior coincide con el agregado subido de {label}. "
                "El propietario confirmó el desbloqueo masivo, la subida, la recuperación "
                "desde la nube y el resultado dentro del juego en un Android físico."
            )
        if field == SKILL_RECORD_FIELD:
            return (
                f"La descarga posterior coincide con el agregado subido de {label}. "
                "El propietario confirmó el desbloqueo, la recuperación desde la nube y la "
                "disponibilidad dentro del juego en un Android físico."
            )
        if field == SKIN_RECORD_FIELD:
            return (
                f"La descarga posterior coincide con el agregado subido de {label}. "
                "Falta la comprobación manual del desbloqueo de skins dentro del juego."
            )
        return (
            f"La descarga posterior coincide con el agregado subido de {label}. "
            "Las transacciones y la persistencia dentro del juego siguen sin verificarse."
        )

    @staticmethod
    def _remote_values(
        payload: bytes, field: str
    ) -> tuple[int | None, int | None, int | None, int | None, int | None, int | None]:
        """Devuelve gemas, valor del campo, material_fish, personajes, habilidades y skins."""
        try:
            gems = read_gems(payload).gems
        except CloudSaveError:
            gems = None
        material: int | None = None
        characters: int | None = None
        skills: int | None = None
        skins: int | None = None
        if field == FISH_CHIP_RECORD_FIELD:
            try:
                snapshot = read_fish_chip(payload)
                value: int | None = snapshot.fish_chip
                material = snapshot.material_fish
            except CloudSaveError:
                value = None
        elif field == PROGRESS_RECORD_FIELD:
            try:
                value = read_fish_progress(payload).cumulative_fish_count
            except CloudSaveError:
                value = None
        elif field == CHARACTER_RECORD_FIELD:
            try:
                characters = len(read_characters(payload).unlocked)
            except CloudSaveError:
                characters = None
            value = characters
        elif field == SKILL_RECORD_FIELD:
            try:
                skills = len(read_skills(payload).unlocked)
            except CloudSaveError:
                skills = None
            value = skills
        elif field == SKIN_RECORD_FIELD:
            try:
                skins = len(read_skins(payload).unlocked)
            except CloudSaveError:
                skins = None
            value = skins
        elif field == UNIFIED_RECORD_FIELD:
            value = None
            try:
                material = read_fish_chip(payload).material_fish
            except CloudSaveError:
                material = None
            try:
                characters = len(read_characters(payload).unlocked)
            except CloudSaveError:
                characters = None
            try:
                skills = len(read_skills(payload).unlocked)
            except CloudSaveError:
                skills = None
            try:
                skins = len(read_skins(payload).unlocked)
            except CloudSaveError:
                skins = None
        elif field == ADVANCED_RECORD_FIELD:
            value = None
        else:
            value = gems
        return gems, value, material, characters, skills, skins

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
                "changed_fields": list(edit.changed_fields),
                "remote_source": save.metadata.source,
            },
        )
        return PreparedEdit(bundle.record, edit, save.metadata.source)

    def prepare_fish_chip(
        self, new_fish_chip: object, *, expected_source: str | None = None
    ) -> PreparedFishChipEdit:
        """Prepara una edición experimental de las dos rutas de pesca.

        Aplica el mismo entero a ``gameData.fishChip`` y a
        ``itemData.materials.material_fish``. El respaldo usa el mismo almacén
        cifrado que las gemas y registra el tipo de campo para que la
        confirmación y la restauración verifiquen la transición correcta.
        """
        save = self.provider.download(self.max_input_bytes)
        if expected_source is not None and not compare_digest(expected_source, save.metadata.sha256):
            raise LabRemoteChanged("La partida remota cambió desde la descarga. Vuelve a descargarla.")
        edit = prepare_fish_chip_edit(save.payload, new_fish_chip)
        if edit.original_sha256 != save.metadata.sha256:
            raise LabServiceError("El original preparado no coincide con la descarga.")
        bundle = self.store.save(
            edit,
            remote_source=save.metadata.source,
            remote_size=save.metadata.size,
            remote_sha256=save.metadata.sha256,
            field=FISH_CHIP_RECORD_FIELD,
            original_value=edit.original_fish_chip,
            new_value=edit.new_fish_chip,
        )
        self.store.append_event(
            bundle.record.id,
            {
                "action": "prepare",
                "field": FISH_CHIP_PATH,
                "experimental": True,
                "changed": edit.changed,
                "original_value": edit.original_fish_chip,
                "candidate_value": edit.new_fish_chip,
                "original_material_fish": edit.original_material_fish,
                "candidate_material_fish": edit.new_material_fish,
                "candidate_sha256": edit.candidate_sha256,
                "changed_fields": list(edit.changed_fields),
                "remote_source": save.metadata.source,
            },
        )
        return PreparedFishChipEdit(bundle.record, edit, save.metadata.source)

    def prepare_fish_progress(
        self, new_cumulative_fish_count: object, *, expected_source: str | None = None
    ) -> PreparedFishProgressEdit:
        """Prepara un cambio aislado de ``itemData.cumulativeFishCount``.

        No modifica el saldo de fichas, el material espejo, los historiales ni
        las recompensas reclamadas. El respaldo usa el mismo almacén cifrado y
        la confirmación vuelve a reproducir el candidato antes de subirlo.
        """
        save = self.provider.download(self.max_input_bytes)
        if expected_source is not None and not compare_digest(expected_source, save.metadata.sha256):
            raise LabRemoteChanged("La partida remota cambió desde la descarga. Vuelve a descargarla.")
        edit = prepare_fish_progress_edit(save.payload, new_cumulative_fish_count)
        if edit.original_sha256 != save.metadata.sha256:
            raise LabServiceError("El original preparado no coincide con la descarga.")
        bundle = self.store.save(
            edit,
            remote_source=save.metadata.source,
            remote_size=save.metadata.size,
            remote_sha256=save.metadata.sha256,
            field=PROGRESS_RECORD_FIELD,
            original_value=edit.original_cumulative_fish_count,
            new_value=edit.new_cumulative_fish_count,
        )
        self.store.append_event(
            bundle.record.id,
            {
                "action": "prepare",
                "field": PROGRESS_PATH,
                "experimental": True,
                "changed": edit.changed,
                "original_value": edit.original_cumulative_fish_count,
                "candidate_value": edit.new_cumulative_fish_count,
                "candidate_sha256": edit.candidate_sha256,
                "changed_fields": list(edit.changed_fields),
                "remote_source": save.metadata.source,
            },
        )
        return PreparedFishProgressEdit(bundle.record, edit, save.metadata.source)

    def prepare_unified(
        self, plan: object, *, expected_source: str | None = None
    ) -> PreparedUnifiedEdit:
        """Compone todos los escritores sobre una sola descarga y un solo respaldo."""
        if not isinstance(plan, dict):
            raise LabServiceError("El plan unificado debe ser un objeto JSON.")
        save = self.provider.download(self.max_input_bytes)
        if expected_source is not None and not compare_digest(expected_source, save.metadata.sha256):
            raise LabRemoteChanged("La partida remota cambió desde la descarga. Vuelve a descargarla.")
        edit = prepare_unified_edit(save.payload, plan)
        if edit.original_sha256 != save.metadata.sha256:
            raise LabServiceError("El original preparado no coincide con la descarga.")
        bundle = self.store.save(
            edit,
            remote_source=save.metadata.source,
            remote_size=save.metadata.size,
            remote_sha256=save.metadata.sha256,
            field=UNIFIED_RECORD_FIELD,
            original_value=0,
            new_value=edit.change_count,
            unified_plan=edit.plan,
        )
        self.store.append_event(
            bundle.record.id,
            {
                "action": "prepare",
                "field": UNIFIED_RECORD_FIELD,
                "changed": edit.changed,
                "change_count": edit.change_count,
                "steps": list(edit.steps),
                "candidate_sha256": edit.candidate_sha256,
                "changed_fields": list(edit.changed_fields),
                "remote_source": save.metadata.source,
            },
        )
        return PreparedUnifiedEdit(bundle.record, edit, save.metadata.source)

    def prepare_characters(
        self, codes: object, *, expected_source: str | None = None
    ) -> PreparedCharacterEdit:
        """Prepara el desbloqueo de los personajes seleccionados.

        Solo activa las entradas correspondientes de ``gameData.heroUnlock``.
        No crea ni modifica niveles, habilidades o skins, y conserva los
        personajes que ya estaban disponibles.
        """
        save = self.provider.download(self.max_input_bytes)
        if expected_source is not None and not compare_digest(expected_source, save.metadata.sha256):
            raise LabRemoteChanged("La partida remota cambió desde la descarga. Vuelve a descargarla.")
        edit = prepare_character_unlock_edit(save.payload, codes)
        if edit.original_sha256 != save.metadata.sha256:
            raise LabServiceError("El original preparado no coincide con la descarga.")
        bundle = self.store.save(
            edit,
            remote_source=save.metadata.source,
            remote_size=save.metadata.size,
            remote_sha256=save.metadata.sha256,
            field=CHARACTER_RECORD_FIELD,
            original_value=len(edit.original_unlocked),
            new_value=len(edit.new_unlocked),
            character_codes=edit.newly_unlocked,
        )
        self.store.append_event(
            bundle.record.id,
            {
                "action": "prepare",
                "field": CHARACTER_PATH,
                "experimental": True,
                "changed": edit.changed,
                "original_unlocked": len(edit.original_unlocked),
                "new_unlocked": len(edit.new_unlocked),
                "newly_unlocked_codes": list(edit.newly_unlocked),
                "candidate_sha256": edit.candidate_sha256,
                "changed_fields": list(edit.changed_fields),
                "remote_source": save.metadata.source,
            },
        )
        return PreparedCharacterEdit(bundle.record, edit, save.metadata.source)

    def prepare_skills(
        self, selections: object, *, expected_source: str | None = None
    ) -> PreparedSkillEdit:
        """Prepara el desbloqueo de las habilidades seleccionadas.

        Solo activa las posiciones existentes de ``gameData.heroSkillUnlock``.
        No crea listas ni entradas ausentes y conserva ``gameData.heroSkill``
        junto con cualquier otro campo de la partida.
        """
        save = self.provider.download(self.max_input_bytes)
        if expected_source is not None and not compare_digest(expected_source, save.metadata.sha256):
            raise LabRemoteChanged("La partida remota cambió desde la descarga. Vuelve a descargarla.")
        edit = prepare_skill_unlock_edit(save.payload, selections)
        if edit.original_sha256 != save.metadata.sha256:
            raise LabServiceError("El original preparado no coincide con la descarga.")
        bundle = self.store.save(
            edit,
            remote_source=save.metadata.source,
            remote_size=save.metadata.size,
            remote_sha256=save.metadata.sha256,
            field=SKILL_RECORD_FIELD,
            original_value=len(edit.original_unlocked),
            new_value=len(edit.new_unlocked),
            skill_selections=[ref.as_dict() for ref in edit.newly_unlocked],
        )
        self.store.append_event(
            bundle.record.id,
            {
                "action": "prepare",
                "field": SKILL_PATH,
                "experimental": True,
                "changed": edit.changed,
                "original_unlocked": len(edit.original_unlocked),
                "new_unlocked": len(edit.new_unlocked),
                "newly_unlocked_skills": [ref.as_dict() for ref in edit.newly_unlocked],
                "affected_codes": list(edit.affected_codes),
                "candidate_sha256": edit.candidate_sha256,
                "changed_fields": list(edit.changed_fields),
                "remote_source": save.metadata.source,
            },
        )
        return PreparedSkillEdit(bundle.record, edit, save.metadata.source)

    def prepare_skins(
        self, selections: object, *, expected_source: str | None = None
    ) -> PreparedSkinEdit:
        """Prepara el desbloqueo de las skins seleccionadas.

        Solo cambia a ``1`` las posiciones existentes de ``gameData.skinLock``.
        No crea listas ni entradas ausentes y conserva ``gameData.currentSkinDatas``,
        ``gameData.heroUnlock`` y cualquier otro campo de la partida.
        """
        save = self.provider.download(self.max_input_bytes)
        if expected_source is not None and not compare_digest(expected_source, save.metadata.sha256):
            raise LabRemoteChanged("La partida remota cambió desde la descarga. Vuelve a descargarla.")
        edit = prepare_skin_unlock_edit(save.payload, selections)
        if edit.original_sha256 != save.metadata.sha256:
            raise LabServiceError("El original preparado no coincide con la descarga.")
        bundle = self.store.save(
            edit,
            remote_source=save.metadata.source,
            remote_size=save.metadata.size,
            remote_sha256=save.metadata.sha256,
            field=SKIN_RECORD_FIELD,
            original_value=len(edit.original_unlocked),
            new_value=len(edit.new_unlocked),
            skin_selections=[ref.as_dict() for ref in edit.newly_unlocked],
        )
        self.store.append_event(
            bundle.record.id,
            {
                "action": "prepare",
                "field": SKIN_PATH,
                "experimental": False,
                "changed": edit.changed,
                "original_unlocked": len(edit.original_unlocked),
                "new_unlocked": len(edit.new_unlocked),
                "newly_unlocked_skins": [ref.as_dict() for ref in edit.newly_unlocked],
                "affected_codes": list(edit.affected_codes),
                "locked_character_codes": list(edit.locked_character_codes),
                "candidate_sha256": edit.candidate_sha256,
                "changed_fields": list(edit.changed_fields),
                "remote_source": save.metadata.source,
            },
        )
        return PreparedSkinEdit(bundle.record, edit, save.metadata.source)

    def prepare_advanced(
        self, plan: object, *, expected_source: str | None = None
    ) -> PreparedAdvancedEdit:
        """Prepara un lote atómico de campos avanzados autorizados."""
        if not isinstance(plan, dict):
            raise LabServiceError("El plan avanzado debe ser un objeto JSON.")
        save = self.provider.download(self.max_input_bytes)
        if expected_source is not None and not compare_digest(expected_source, save.metadata.sha256):
            raise LabRemoteChanged("La partida remota cambió desde la descarga. Vuelve a descargarla.")
        edit = prepare_advanced_edit(save.payload, plan)
        if edit.original_sha256 != save.metadata.sha256:
            raise LabServiceError("El original preparado no coincide con la descarga.")
        bundle = self.store.save(
            edit,
            remote_source=save.metadata.source,
            remote_size=save.metadata.size,
            remote_sha256=save.metadata.sha256,
            field=ADVANCED_RECORD_FIELD,
            original_value=0,
            new_value=len(edit.changes),
            advanced_plan=edit.plan,
        )
        self.store.append_event(
            bundle.record.id,
            {
                "action": "prepare",
                "field": ADVANCED_RECORD_FIELD,
                "experimental": True,
                "changed": edit.changed,
                "changed_fields": list(edit.changed_fields),
                "candidate_sha256": edit.candidate_sha256,
                "remote_source": save.metadata.source,
            },
        )
        return PreparedAdvancedEdit(bundle.record, edit, save.metadata.source)

    def confirm(self, backup_id: str, expected_sha256: str, *, single_attempt: bool = False) -> WriteResult:
        if not self.write_enabled or self.uploader is None:
            raise LabWriteDisabled("La escritura remota está deshabilitada en el servidor.")
        if not isinstance(expected_sha256, str) or not _SHA256.fullmatch(expected_sha256):
            raise LabHashMismatch("La huella esperada no es válida.")
        with self._write_lock:
            bundle = self.store.load(backup_id)
            label = self._field_label(bundle.record.field)
            if not bundle.record.changed:
                raise LabNoChanges(f"La operación no cambia {label}; no se enviará nada a la nube.")
            if not compare_digest(expected_sha256, bundle.record.candidate_sha256):
                raise LabHashMismatch("La huella esperada no coincide con el candidato respaldado.")
            if self.store.confirmation(backup_id) is not None:
                raise LabAlreadyConfirmed("Este respaldo ya fue confirmado; usa la verificación.")
            if bundle.record.field == FISH_CHIP_RECORD_FIELD:
                require_fish_chip_write_compatibility(
                    bundle.original, bundle.record.candidate_gems, bundle.candidate
                )
            elif bundle.record.field == PROGRESS_RECORD_FIELD:
                require_fish_progress_write_compatibility(
                    bundle.original, bundle.record.candidate_gems, bundle.candidate
                )
            elif bundle.record.field == CHARACTER_RECORD_FIELD:
                require_character_write_compatibility(
                    bundle.original, bundle.record.character_codes, bundle.candidate
                )
            elif bundle.record.field == SKILL_RECORD_FIELD:
                require_skill_write_compatibility(
                    bundle.original,
                    [
                        {"code": code, "index": index}
                        for code, index in bundle.record.skill_selections
                    ],
                    bundle.candidate,
                )
            elif bundle.record.field == SKIN_RECORD_FIELD:
                require_skin_write_compatibility(
                    bundle.original,
                    [
                        {"code": code, "index": index}
                        for code, index in bundle.record.skin_selections
                    ],
                    bundle.candidate,
                )
            elif bundle.record.field == ADVANCED_RECORD_FIELD:
                require_advanced_write_compatibility(
                    bundle.original, bundle.record.advanced_plan, bundle.candidate
                )
            elif bundle.record.field == UNIFIED_RECORD_FIELD:
                require_unified_write_compatibility(
                    bundle.original, bundle.record.unified_plan, bundle.candidate
                )
            else:
                require_gems_write_compatibility(bundle.original, bundle.record.candidate_gems, bundle.candidate)
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
            remote_gems, remote_value, remote_material, remote_characters, remote_skills, remote_skins = self._remote_values(
                remote.payload, bundle.record.field
            )
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
                field=self._field_path(bundle.record.field),
                remote_value=remote_value,
                remote_material_fish=remote_material,
                remote_characters=remote_characters,
                remote_skills=remote_skills,
                remote_skins=remote_skins,
                message=(
                    self._persisted_message(bundle.record.field, label)
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
            label = self._field_label(bundle.record.field)
            if not bundle.record.changed:
                raise LabNoChanges("El respaldo no contiene una modificación que restaurar.")
            current = self.provider.download(self.max_input_bytes)
            if current.metadata.sha256 == bundle.record.original_sha256:
                remote_gems, remote_value, remote_material, remote_characters, remote_skills, remote_skins = self._remote_values(
                    current.payload, bundle.record.field
                )
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
                    remote_gems=remote_gems,
                    status=None,
                    field=self._field_path(bundle.record.field),
                    remote_value=remote_value,
                    remote_material_fish=remote_material,
                    remote_characters=remote_characters,
                    remote_skills=remote_skills,
                    remote_skins=remote_skins,
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
            remote_gems, remote_value, remote_material, remote_characters, remote_skills, remote_skins = self._remote_values(
                remote.payload, bundle.record.field
            )
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
                field=self._field_path(bundle.record.field),
                remote_value=remote_value,
                remote_material_fish=remote_material,
                remote_characters=remote_characters,
                remote_skills=remote_skills,
                remote_skins=remote_skins,
                message=(
                    f"La descarga posterior coincide con el original respaldado de {label}."
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
        remote_gems, remote_value, remote_material, remote_characters, remote_skills, remote_skins = self._remote_values(
            remote.payload, bundle.record.field
        )
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
            remote_skills=remote_skills,
            remote_skins=remote_skins,
            expected_candidate_sha256=bundle.record.candidate_sha256,
            expected_original_sha256=bundle.record.original_sha256,
            message=message,
            field=self._field_path(bundle.record.field),
            remote_value=remote_value,
            remote_material_fish=remote_material,
            remote_characters=remote_characters,
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

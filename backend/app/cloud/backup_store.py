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
from dataclasses import dataclass, field as dataclass_field
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any
from uuid import uuid4

from Crypto.Cipher import AES

from ..cloud_save import MAX_INPUT_BYTES, CloudSaveError, reconstruct_cloud_save
from ..parsers.json_document import parse_json
from .advanced_editor import (
    ADVANCED_RECORD_FIELD,
    AdvancedEdit,
    normalize_advanced_plan,
    prepare_advanced_edit,
)
from .character_editor import (
    CHARACTER_RECORD_FIELD,
    MAX_CHARACTERS,
    CharacterFieldMissing,
    prepare_character_unlock_edit,
    read_characters,
)
from .fish_chip_editor import (
    FISH_CHIP_RECORD_FIELD,
    FishChipEdit,
    FishChipFieldMissing,
    legacy_fish_chip_candidate_matches,
    prepare_fish_chip_edit,
    read_fish_chip,
)
from .fish_progress_editor import (
    PROGRESS_RECORD_FIELD,
    FishProgressEdit,
    FishProgressFieldMissing,
    prepare_fish_progress_edit,
    read_fish_progress,
)
from .gems_editor import GemsEdit, GemsEditError, prepare_gems_edit, read_gems, replay_legacy_gems_edit
from .skill_editor import (
    MAX_SKILLS,
    SKILL_RECORD_FIELD,
    SkillEdit,
    SkillFieldMissing,
    prepare_skill_unlock_edit,
    read_skills,
)
from .skin_editor import (
    MAX_SKINS,
    SKIN_RECORD_FIELD,
    SkinEdit,
    SkinFieldMissing,
    prepare_skin_unlock_edit,
    read_skins,
)
from .unified_editor import (
    UNIFIED_RECORD_FIELD,
    UnifiedEdit,
    normalize_unified_plan,
    prepare_unified_edit,
)

_ID = re.compile(r"^[0-9a-f]{32}$")
_FIELDS = frozenset(
    {
        "gems",
        FISH_CHIP_RECORD_FIELD,
        PROGRESS_RECORD_FIELD,
        CHARACTER_RECORD_FIELD,
        SKILL_RECORD_FIELD,
        SKIN_RECORD_FIELD,
        ADVANCED_RECORD_FIELD,
        UNIFIED_RECORD_FIELD,
    }
)
_RECORD_LIMIT = 64 * 1024
_JOURNAL_LIMIT = 1024 * 1024
_SEAL_MAGIC = b"SKB1"
_SEAL_TAG = 16


class BackupStoreError(CloudSaveError):
    code = "backup_store"


class InvalidBackupId(BackupStoreError):
    code = "invalid_backup_id"


class BackupNotFound(BackupStoreError):
    code = "backup_not_found"


class BackupIntegrityError(BackupStoreError):
    code = "backup_integrity"


class BackupStorageUnavailable(BackupStoreError):
    code = "native_backup_unavailable"


class BackupUnreadable(BackupIntegrityError):
    """Los datos no se pueden autenticar con el formato y la clave actuales."""


class BackupIncompatible(BackupIntegrityError):
    """Metadatos de un formato o plan que el lector actual no reconoce."""


class BackupAlreadyConfirmed(BackupStoreError):
    code = "backup_already_confirmed"


@dataclass(frozen=True)
class BackupRecord:
    id: str
    created_at: str
    changed: bool
    original_size: int
    original_sha256: str = dataclass_field(repr=False)
    original_gems: int
    candidate_size: int
    candidate_sha256: str = dataclass_field(repr=False)
    candidate_gems: int
    remote_source: str
    remote_size: int
    remote_sha256: str = dataclass_field(repr=False)
    field: str = "gems"
    character_codes: tuple[str, ...] = ()
    skill_selections: tuple[tuple[str, int], ...] = ()
    skin_selections: tuple[tuple[str, int], ...] = ()
    advanced_plan: dict[str, object] = dataclass_field(default_factory=dict)
    unified_plan: dict[str, object] = dataclass_field(default_factory=dict)

    @property
    def original_value(self) -> int:
        """Valor original del campo respaldado, sea gemas o fichas de pesca."""
        return self.original_gems

    @property
    def candidate_value(self) -> int:
        """Valor candidato del campo respaldado, sea gemas o fichas de pesca."""
        return self.candidate_gems

    def summary(self) -> dict[str, object]:
        return {
            "id": self.id,
            "created_at": self.created_at,
            "field": self.field,
            "changed": self.changed,
            "original_size": self.original_size,
            "original_sha256": self.original_sha256,
            "original_gems": self.original_gems,
            "original_value": self.original_gems,
            "candidate_size": self.candidate_size,
            "candidate_sha256": self.candidate_sha256,
            "candidate_gems": self.candidate_gems,
            "candidate_value": self.candidate_gems,
            "remote_source": self.remote_source,
            "remote_size": self.remote_size,
            "remote_sha256": self.remote_sha256,
            "character_codes": list(self.character_codes),
            "skill_selections": [
                {"code": code, "index": index} for code, index in self.skill_selections
            ],
            "skin_selections": [
                {"code": code, "index": index} for code, index in self.skin_selections
            ],
            "advanced_plan": self.advanced_plan,
            "unified_plan": self.unified_plan,
        }


@dataclass(frozen=True)
class BackupBundle:
    record: BackupRecord
    original: bytes = dataclass_field(repr=False)
    candidate: bytes = dataclass_field(repr=False)
    categories: tuple[str, ...] = ()


def backup_problem(error: CloudSaveError | OSError) -> str:
    if isinstance(error, BackupUnreadable):
        return "authentication"
    if isinstance(error, BackupIncompatible):
        return "incompatible"
    if isinstance(error, (BackupNotFound, OSError)) or type(error) is BackupStoreError:
        return "file_unavailable"
    return "integrity"


@dataclass(frozen=True)
class BackupIndexEntry:
    id: str
    record: BackupRecord | None
    problem: str | None = None


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


def _require_advanced_plan(value: object, *, historical: bool = False) -> dict[str, object]:
    if not isinstance(value, dict):
        raise BackupIncompatible("El registro de respaldo no contiene un plan avanzado válido.")
    if historical and set(value) == {"materials", "seeds", "season_coin", "reborn_card", "battle_pass"}:
        # Fase 7.1: ambos campos se añadieron como operaciones opcionales en 7.2.
        value = value | {"pets": [], "pet_food": {}}
    try:
        plan = normalize_advanced_plan(value)
    except CloudSaveError as exc:
        raise BackupIncompatible("El plan avanzado del respaldo no es válido.") from exc
    if plan != value:
        raise BackupIncompatible("El plan avanzado del respaldo no está normalizado.")
    return plan


def _require_unified_plan(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise BackupIncompatible("El registro de respaldo no contiene un plan unificado válido.")
    try:
        plan = normalize_unified_plan(value)
    except CloudSaveError as exc:
        raise BackupIncompatible("El plan unificado del respaldo no es válido.") from exc
    if plan != value:
        raise BackupIncompatible("El plan unificado del respaldo no está normalizado.")
    return plan


def _require_skill_selections(value: object) -> tuple[tuple[str, int], ...]:
    if value is None:
        return ()
    if not isinstance(value, list) or len(value) > MAX_SKILLS:
        raise BackupIntegrityError(
            "El registro de respaldo contiene una selección de habilidades inválida."
        )
    selections: list[tuple[str, int]] = []
    for item in value:
        if not isinstance(item, dict):
            raise BackupIntegrityError(
                "El registro de respaldo contiene una selección de habilidades inválida."
            )
        code = item.get("code")
        index = item.get("index")
        if (
            not isinstance(code, str)
            or not code
            or len(code) > 80
            or type(index) is not int
            or index < 0
            or (code, index) in selections
        ):
            raise BackupIntegrityError(
                "El registro de respaldo contiene una selección de habilidades inválida."
            )
        selections.append((code, index))
    return tuple(selections)


def _require_skin_selections(value: object) -> tuple[tuple[str, int], ...]:
    if value is None:
        return ()
    if not isinstance(value, list) or len(value) > MAX_SKINS:
        raise BackupIntegrityError(
            "El registro de respaldo contiene una selección de skins inválida."
        )
    selections: list[tuple[str, int]] = []
    for item in value:
        if not isinstance(item, dict):
            raise BackupIntegrityError(
                "El registro de respaldo contiene una selección de skins inválida."
            )
        code = item.get("code")
        index = item.get("index")
        if (
            not isinstance(code, str)
            or not code
            or len(code) > 80
            or type(index) is not int
            or index < 0
            or (code, index) in selections
        ):
            raise BackupIntegrityError(
                "El registro de respaldo contiene una selección de skins inválida."
            )
        selections.append((code, index))
    return tuple(selections)


def _require_codes(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list) or len(value) > MAX_CHARACTERS:
        raise BackupIntegrityError("El registro de respaldo contiene una selección de personajes inválida.")
    codes: list[str] = []
    for code in value:
        if not isinstance(code, str) or not code or len(code) > 80 or code in codes:
            raise BackupIntegrityError(
                "El registro de respaldo contiene una selección de personajes inválida."
            )
        codes.append(code)
    return tuple(codes)


class LabBackupStore:
    """Almacén de respaldos creado explícitamente sobre un directorio privado."""

    def __init__(
        self,
        root: Path,
        *,
        limit: int = MAX_INPUT_BYTES,
        cipher_key: bytes | None = None,
        required_mount: Path | None = None,
    ) -> None:
        if isinstance(limit, bool) or not isinstance(limit, int) or not 0 < limit <= MAX_INPUT_BYTES:
            raise BackupStoreError("Límite de respaldo inválido.")
        if cipher_key is not None and (not isinstance(cipher_key, bytes) or len(cipher_key) != 32):
            raise BackupStoreError("La clave de cifrado de respaldos no tiene 32 bytes.")
        self.root = Path(root).expanduser().absolute()
        self.limit = limit
        self.cipher_key = cipher_key
        self.required_mount = required_mount

    def _require_mount(self) -> None:
        if self.required_mount is None:
            return
        try:
            root = self.required_mount.resolve(strict=True)
            covering = []
            for line in Path("/proc/self/mountinfo").read_text().splitlines():
                mount, filesystem = line.split(" - ", 1)
                encoded = mount.split()[4]
                path = Path(re.sub(r"\\([0-7]{3})", lambda match: chr(int(match[1], 8)), encoded))
                if root.is_relative_to(path):
                    covering.append((path, filesystem.split()[0]))
            nearest, storage_type = max(covering, key=lambda item: len(item[0].parts))
            if nearest != Path("/") and storage_type not in {"overlay", "tmpfs", "ramfs", "rootfs"}:
                return
        except (OSError, ValueError, IndexError, RuntimeError):
            pass
        raise BackupStorageUnavailable("El volumen persistente de respaldos no está disponible.")

    def _context(self, path: Path) -> bytes:
        return b"sk-under/backup\x00" + path.parent.name.encode("ascii") + b"\x00" + path.name.encode("ascii")

    def _seal(self, path: Path, data: bytes) -> bytes:
        if self.cipher_key is None:
            return data
        cipher = AES.new(self.cipher_key, AES.MODE_SIV)
        cipher.update(self._context(path))
        encrypted, tag = cipher.encrypt_and_digest(data)
        return _SEAL_MAGIC + tag + encrypted

    def _open(self, path: Path, data: bytes) -> bytes:
        if self.cipher_key is None:
            return data
        if not data.startswith(_SEAL_MAGIC) or len(data) < len(_SEAL_MAGIC) + _SEAL_TAG:
            raise BackupUnreadable(
                "El respaldo no está cifrado con la clave actual. Migra los respaldos antes de continuar."
            )
        cipher = AES.new(self.cipher_key, AES.MODE_SIV)
        cipher.update(self._context(path))
        try:
            return cipher.decrypt_and_verify(data[len(_SEAL_MAGIC) + _SEAL_TAG:], data[len(_SEAL_MAGIC):len(_SEAL_MAGIC) + _SEAL_TAG])
        except (ValueError, KeyError):
            raise BackupUnreadable("El respaldo no se pudo descifrar o fue alterado.") from None

    def _ensure_root(self) -> None:
        try:
            self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
            info = self.root.lstat()
            if not stat.S_ISDIR(info.st_mode):
                raise BackupStoreError("La ruta de respaldos no es un directorio.")
            os.chmod(self.root, 0o700)
        except OSError:
            raise BackupStoreError("No se pudo preparar el directorio privado de respaldos.") from None

    def _directory(self, backup_id: str) -> Path:
        if not isinstance(backup_id, str) or not _ID.fullmatch(backup_id):
            raise InvalidBackupId("El identificador de respaldo no es válido.")
        return self.root / backup_id

    def _existing_directory(self, backup_id: str) -> Path:
        directory = self._directory(backup_id)
        try:
            if not stat.S_ISDIR(self.root.lstat().st_mode) or not stat.S_ISDIR(directory.lstat().st_mode):
                raise BackupIntegrityError("El directorio del respaldo no es válido.")
        except FileNotFoundError:
            raise BackupNotFound("No se encontró el respaldo solicitado.") from None
        except OSError:
            raise BackupStoreError("No se pudo acceder al directorio privado de respaldo.") from None
        return directory

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
        payload = self._seal(path, data)
        flags = os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW
        flags |= os.O_EXCL if exclusive else os.O_TRUNC
        try:
            descriptor = os.open(path, flags, 0o600)
        except OSError:
            raise BackupStoreError("No se pudo crear un archivo privado de respaldo.") from None
        try:
            view = memoryview(payload)
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
            descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        except FileNotFoundError:
            raise BackupNotFound("No se encontró el respaldo solicitado.") from None
        except OSError:
            raise BackupStoreError("No se pudo abrir el archivo privado de respaldo.") from None
        try:
            info = os.fstat(descriptor)
            wire_limit = limit + len(_SEAL_MAGIC) + _SEAL_TAG if self.cipher_key is not None else limit
            if not stat.S_ISREG(info.st_mode) or info.st_size > wire_limit:
                raise BackupIntegrityError("El archivo de respaldo no es válido.")
            chunks: list[bytes] = []
            remaining = info.st_size
            while remaining:
                chunk = os.read(descriptor, min(remaining, 64 * 1024))
                if not chunk:
                    raise BackupIntegrityError("El archivo de respaldo está truncado.")
                chunks.append(chunk)
                remaining -= len(chunk)
            data = self._open(path, b"".join(chunks))
        except OSError:
            raise BackupStoreError("No se pudo leer el archivo privado de respaldo.") from None
        finally:
            os.close(descriptor)
        if len(data) > limit:
            raise BackupIntegrityError("El archivo de respaldo supera el límite.")
        return data

    @staticmethod
    def _sync_directory(path: Path) -> None:
        descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    def save(
        self,
        edit: GemsEdit | FishChipEdit | FishProgressEdit | SkillEdit | SkinEdit | AdvancedEdit | UnifiedEdit,
        *,
        remote_source: str,
        remote_size: int,
        remote_sha256: str,
        field: str = "gems",
        original_value: int | None = None,
        new_value: int | None = None,
        character_codes: tuple[str, ...] | None = None,
        skill_selections: list[dict[str, object]] | tuple[dict[str, object], ...] | None = None,
        skin_selections: list[dict[str, object]] | tuple[dict[str, object], ...] | None = None,
        advanced_plan: dict[str, object] | None = None,
        unified_plan: dict[str, object] | None = None,
    ) -> BackupBundle:
        """Crea un respaldo y devuelve los bytes que quedaron en disco.

        ``field`` identifica el único grupo editado (``gems`` o ``fish_chip``).
        Los registros y las respuestas existentes conservan ``original_gems`` y
        ``candidate_gems`` como el valor del campo respaldado para mantener la
        compatibilidad de la Fase 6.13.
        """
        self._require_mount()
        if field not in _FIELDS:
            raise BackupIntegrityError("El tipo de campo del respaldo no es válido.")
        codes = _require_codes(list(character_codes) if character_codes is not None else None)
        skills = _require_skill_selections(
            list(skill_selections) if skill_selections is not None else None
        )
        skins = _require_skin_selections(
            list(skin_selections) if skin_selections is not None else None
        )
        plan: dict[str, object] = {}
        unified: dict[str, object] = {}
        if field == CHARACTER_RECORD_FIELD:
            if edit.changed and not codes:
                raise BackupIntegrityError("El respaldo de personajes requiere la selección preparada.")
            skills = ()
            skins = ()
        elif field == SKILL_RECORD_FIELD:
            if edit.changed and not skills:
                raise BackupIntegrityError("El respaldo de habilidades requiere la selección preparada.")
            codes = ()
            skins = ()
        elif field == SKIN_RECORD_FIELD:
            if edit.changed and not skins:
                raise BackupIntegrityError("El respaldo de skins requiere la selección preparada.")
            codes = ()
            skills = ()
        elif field == ADVANCED_RECORD_FIELD:
            if advanced_plan is None:
                raise BackupIntegrityError("El respaldo avanzado requiere su plan preparado.")
            plan = _require_advanced_plan(advanced_plan)
            if getattr(edit, "plan", None) != plan:
                raise BackupIntegrityError("El plan avanzado no coincide con la edición preparada.")
            codes = ()
            skills = ()
            skins = ()
        elif field == UNIFIED_RECORD_FIELD:
            if unified_plan is None:
                raise BackupIntegrityError("El respaldo unificado requiere su plan preparado.")
            unified = _require_unified_plan(unified_plan)
            if getattr(edit, "plan", None) != unified:
                raise BackupIntegrityError("El plan unificado no coincide con la edición preparada.")
            codes = ()
            skills = ()
            skins = ()
            plan = {}
        else:
            codes = ()
            skills = ()
            skins = ()
            plan = {}
        if remote_sha256 != edit.original_sha256 or remote_size != len(edit.original):
            raise BackupIntegrityError("La copia remota no coincide con el original preparado.")
        if original_value is None:
            original_value = getattr(
                edit,
                "original_gems",
                getattr(edit, "original_fish_chip", getattr(edit, "original_cumulative_fish_count", None)),
            )
        if new_value is None:
            new_value = getattr(
                edit,
                "new_gems",
                getattr(edit, "new_fish_chip", getattr(edit, "new_cumulative_fish_count", None)),
            )
        original_value = _require_int(original_value, "original_value")
        new_value = _require_int(new_value, "candidate_value")
        source = _require_text(remote_source, "remote_source")
        self._ensure_root()
        backup_id = uuid4().hex
        staging = self.root / f".pending-{backup_id}"
        try:
            staging.mkdir(mode=0o700)
        except OSError:
            raise BackupStoreError("No se pudo preparar el directorio del respaldo.") from None
        # El nombre final también se usa como contexto de autenticación AES-SIV.
        directory = staging / backup_id
        try:
            os.mkdir(directory, 0o700)
        except OSError:
            try:
                staging.rmdir()
            except OSError:
                pass
            raise BackupStoreError("No se pudo crear el directorio del respaldo.") from None
        record = BackupRecord(
            id=backup_id,
            created_at=_now(),
            changed=edit.changed,
            original_size=len(edit.original),
            original_sha256=edit.original_sha256,
            original_gems=original_value,
            candidate_size=len(edit.candidate),
            candidate_sha256=edit.candidate_sha256,
            candidate_gems=new_value,
            remote_source=source,
            remote_size=remote_size,
            remote_sha256=remote_sha256,
            field=field,
            character_codes=codes,
            skill_selections=skills,
            skin_selections=skins,
            advanced_plan=plan,
            unified_plan=unified,
        )
        try:
            self._write_private(directory / "original.json", edit.original)
            self._write_private(directory / "candidate.json", edit.candidate)
            encoded = json.dumps(record.summary(), ensure_ascii=False, sort_keys=True).encode("utf-8")
            if len(encoded) > _RECORD_LIMIT:
                raise BackupIntegrityError("El registro de respaldo supera el límite.")
            self._write_private(directory / "record.json", encoded)
            self._sync_directory(directory)
            directory = directory.rename(self._directory(backup_id))
            self._sync_directory(self.root)
            self._sync_directory(self.root.parent)
        except (BackupStoreError, OSError) as exc:
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
            if isinstance(exc, OSError):
                raise BackupStoreError("No se pudo conservar el respaldo de forma persistente.") from None
            raise
        finally:
            try:
                staging.rmdir()
            except OSError:
                pass
        return BackupBundle(record, edit.original, edit.candidate)

    def migrate_legacy(self) -> int:
        """Cifra respaldos de la Fase 6.8 que todavía están en claro.

        Es una operación administrativa explícita: recorre los directorios de
        respaldo, cifra los archivos conocidos y los reemplaza de forma atómica.
        No modifica los bytes originales de la partida ni sus huellas. Devuelve
        el número de archivos migrados.
        """

        if self.cipher_key is None:
            raise BackupStoreError("Configura una clave de respaldos para migrar.")
        if not self.root.exists():
            return 0
        migrated = 0
        for entry in self.root.iterdir():
            if not _ID.fullmatch(entry.name) or entry.is_symlink() or not entry.is_dir():
                continue
            for name in ("original.json", "candidate.json", "record.json", "confirmation.json", "events.jsonl"):
                path = entry / name
                if not path.is_file() or path.is_symlink():
                    continue
                raw = self._read_plain(path, self.limit + _RECORD_LIMIT)
                if raw.startswith(_SEAL_MAGIC):
                    continue
                if name == "events.jsonl":
                    lines = [line for line in raw.splitlines() if line]
                    payload = b"".join(self._seal(path, line) + b"\n" for line in lines)
                else:
                    payload = self._seal(path, raw)
                temp = path.with_name(path.name + ".migrating")
                flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
                try:
                    descriptor = os.open(temp, flags, 0o600)
                    try:
                        view = memoryview(payload)
                        while view:
                            written = os.write(descriptor, view)
                            view = view[written:]
                        os.fsync(descriptor)
                    finally:
                        os.close(descriptor)
                    os.replace(temp, path)
                except OSError:
                    try:
                        temp.unlink(missing_ok=True)
                    except OSError:
                        pass
                    raise BackupStoreError("No se pudo migrar un respaldo.") from None
                migrated += 1
        return migrated

    @staticmethod
    def _read_plain(path: Path, limit: int) -> bytes:
        try:
            descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        except FileNotFoundError:
            raise BackupNotFound("No se encontró el respaldo solicitado.") from None
        except OSError:
            raise BackupStoreError("No se pudo abrir el archivo privado de respaldo.") from None
        try:
            info = os.fstat(descriptor)
            if not stat.S_ISREG(info.st_mode) or info.st_size > limit:
                raise BackupIntegrityError("El archivo de respaldo no es válido.")
            data = b""
            while len(data) < info.st_size:
                chunk = os.read(descriptor, min(info.st_size - len(data), 64 * 1024))
                if not chunk:
                    raise BackupIntegrityError("El archivo de respaldo está truncado.")
                data += chunk
            return data
        finally:
            os.close(descriptor)

    def _read_record(self, backup_id: str) -> BackupRecord:
        raw = self._read_private(self._existing_directory(backup_id) / "record.json", _RECORD_LIMIT)
        try:
            data = parse_json(raw)
        except (ValueError, RecursionError):
            raise BackupIntegrityError("El registro de respaldo no es JSON válido.") from None
        if not isinstance(data, dict):
            raise BackupIntegrityError("El registro de respaldo no es un objeto.")
        field = data.get("field", "gems")
        if not isinstance(field, str) or field not in _FIELDS:
            raise BackupIncompatible("El registro de respaldo contiene un tipo de campo inválido.")
        plan = _require_advanced_plan(data.get("advanced_plan"), historical=True) if field == ADVANCED_RECORD_FIELD else {}
        unified = _require_unified_plan(data.get("unified_plan")) if field == UNIFIED_RECORD_FIELD else {}
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
            field=field,
            character_codes=_require_codes(data.get("character_codes")),
            skill_selections=_require_skill_selections(data.get("skill_selections")),
            skin_selections=_require_skin_selections(data.get("skin_selections")),
            advanced_plan=plan,
            unified_plan=unified,
        )
        if record.id != backup_id:
            raise BackupIntegrityError("El identificador del registro no coincide.")
        if not isinstance(data.get("changed"), bool):
            raise BackupIntegrityError("El registro de respaldo contiene changed inválido.")
        try:
            if datetime.fromisoformat(record.created_at).utcoffset() is None:
                raise ValueError
        except ValueError:
            raise BackupIntegrityError("La fecha del respaldo no es válida.") from None
        return record

    def load(self, backup_id: str) -> BackupBundle:
        """Carga y verifica el respaldo completo antes de cualquier reenvío."""
        self._require_mount()
        record = self._read_record(backup_id)
        directory = self._directory(backup_id)
        original = self._read_private(directory / "original.json", self.limit)
        candidate = self._read_private(directory / "candidate.json", self.limit)
        if len(original) != record.original_size or sha256(original).hexdigest() != record.original_sha256:
            raise BackupIntegrityError("El original del respaldo no coincide con su registro.")
        if len(candidate) != record.candidate_size or sha256(candidate).hexdigest() != record.candidate_sha256:
            raise BackupIntegrityError("El candidato del respaldo no coincide con su registro.")
        reconstruct_cloud_save(original)
        if record.changed != (original != candidate):
            raise BackupIntegrityError("El indicador de cambio del respaldo no coincide.")
        if record.field == UNIFIED_RECORD_FIELD:
            if not record.unified_plan:
                raise BackupIntegrityError("El respaldo unificado no contiene su plan.")
            if not record.changed:
                return BackupBundle(record, original, candidate)
            try:
                current = prepare_unified_edit(original, record.unified_plan)
            except CloudSaveError:
                raise BackupIntegrityError(
                    "El candidato del respaldo no es reproducible desde el original."
                ) from None
            if current.candidate != candidate or current.change_count != record.candidate_gems:
                raise BackupIntegrityError(
                    "El candidato del respaldo no es reproducible desde el original."
                )
            return BackupBundle(record, original, candidate, tuple(item.key for item in current.categories if item.changes))
        if record.field == CHARACTER_RECORD_FIELD:
            try:
                original_unlocked = read_characters(original).unlocked
            except CharacterFieldMissing:
                raise BackupIntegrityError(
                    "El original del respaldo no contiene los personajes."
                ) from None
            if len(original_unlocked) != record.original_gems:
                raise BackupIntegrityError("El original del respaldo no conserva el valor registrado.")
            if not record.changed:
                return BackupBundle(record, original, candidate)
            try:
                current = prepare_character_unlock_edit(original, record.character_codes)
            except CloudSaveError:
                raise BackupIntegrityError(
                    "El candidato del respaldo no es reproducible desde el original."
                ) from None
            if current.candidate != candidate or len(current.new_unlocked) != record.candidate_gems:
                raise BackupIntegrityError(
                    "El candidato del respaldo no es reproducible desde el original."
                )
            return BackupBundle(record, original, candidate)
        if record.field == SKILL_RECORD_FIELD:
            try:
                original_unlocked = read_skills(original).unlocked
            except SkillFieldMissing:
                raise BackupIntegrityError(
                    "El original del respaldo no contiene las habilidades."
                ) from None
            if len(original_unlocked) != record.original_gems:
                raise BackupIntegrityError("El original del respaldo no conserva el valor registrado.")
            if not record.changed:
                return BackupBundle(record, original, candidate)
            try:
                current = prepare_skill_unlock_edit(
                    original,
                    [
                        {"code": code, "index": index}
                        for code, index in record.skill_selections
                    ],
                )
            except CloudSaveError:
                raise BackupIntegrityError(
                    "El candidato del respaldo no es reproducible desde el original."
                ) from None
            if current.candidate != candidate or len(current.new_unlocked) != record.candidate_gems:
                raise BackupIntegrityError(
                    "El candidato del respaldo no es reproducible desde el original."
                )
            return BackupBundle(record, original, candidate)
        if record.field == SKIN_RECORD_FIELD:
            try:
                original_unlocked = read_skins(original).unlocked
            except SkinFieldMissing:
                raise BackupIntegrityError(
                    "El original del respaldo no contiene las skins."
                ) from None
            if len(original_unlocked) != record.original_gems:
                raise BackupIntegrityError("El original del respaldo no conserva el valor registrado.")
            if not record.changed:
                return BackupBundle(record, original, candidate)
            try:
                current = prepare_skin_unlock_edit(
                    original,
                    [
                        {"code": code, "index": index}
                        for code, index in record.skin_selections
                    ],
                )
            except CloudSaveError:
                raise BackupIntegrityError(
                    "El candidato del respaldo no es reproducible desde el original."
                ) from None
            if current.candidate != candidate or len(current.new_unlocked) != record.candidate_gems:
                raise BackupIntegrityError(
                    "El candidato del respaldo no es reproducible desde el original."
                )
            return BackupBundle(record, original, candidate)
        if record.field == ADVANCED_RECORD_FIELD:
            if not record.advanced_plan:
                raise BackupIntegrityError("El respaldo avanzado no contiene su plan.")
            if not record.changed:
                return BackupBundle(record, original, candidate)
            try:
                current = prepare_advanced_edit(original, record.advanced_plan)
            except CloudSaveError:
                raise BackupIntegrityError(
                    "El candidato del respaldo no es reproducible desde el original."
                ) from None
            if current.candidate != candidate or len(current.changes) != record.candidate_gems:
                raise BackupIntegrityError(
                    "El candidato del respaldo no es reproducible desde el original."
                )
            return BackupBundle(record, original, candidate)
        if record.field == FISH_CHIP_RECORD_FIELD:
            try:
                original_fish_chip = read_fish_chip(original).fish_chip
            except FishChipFieldMissing:
                raise BackupIntegrityError("El original del respaldo no contiene el saldo de fichas.") from None
            if original_fish_chip != record.original_gems:
                raise BackupIntegrityError("El original del respaldo no conserva el valor registrado.")
            try:
                current = prepare_fish_chip_edit(original, record.candidate_gems)
            except CloudSaveError:
                raise BackupIntegrityError(
                    "El candidato del respaldo no es reproducible desde el original."
                ) from None
            if current.candidate != candidate and not legacy_fish_chip_candidate_matches(
                original, record.candidate_gems, candidate
            ):
                raise BackupIntegrityError(
                    "El candidato del respaldo no es reproducible desde el original."
                )
            return BackupBundle(record, original, candidate)
        if record.field == PROGRESS_RECORD_FIELD:
            try:
                original_progress = read_fish_progress(original).cumulative_fish_count
            except FishProgressFieldMissing:
                raise BackupIntegrityError(
                    "El original del respaldo no contiene el progreso acumulado de fichas."
                ) from None
            if original_progress != record.original_gems:
                raise BackupIntegrityError("El original del respaldo no conserva el valor registrado.")
            if not record.changed:
                return BackupBundle(record, original, candidate)
            try:
                current = prepare_fish_progress_edit(original, record.candidate_gems)
            except CloudSaveError:
                raise BackupIntegrityError(
                    "El candidato del respaldo no es reproducible desde el original."
                ) from None
            if current.candidate != candidate:
                raise BackupIntegrityError(
                    "El candidato del respaldo no es reproducible desde el original."
                )
            return BackupBundle(record, original, candidate)
        if read_gems(original).gems != record.original_gems:
            raise BackupIntegrityError("El original del respaldo no conserva el valor registrado.")
        legacy = replay_legacy_gems_edit(original, record.candidate_gems)
        if legacy.candidate != candidate:
            try:
                current = prepare_gems_edit(original, record.candidate_gems)
            except GemsEditError:
                raise BackupIntegrityError("El candidato del respaldo no es reproducible desde el original.") from None
            if current.candidate != candidate:
                raise BackupIntegrityError("El candidato del respaldo no es reproducible desde el original.")
        return BackupBundle(record, original, candidate)

    def index(self, *, require_parent: bool = False) -> list[BackupIndexEntry]:
        """Enumera registros e incidencias sin leer el contenido de las partidas."""
        self._require_mount()
        if require_parent:
            try:
                if not self.root.parent.is_dir() or not os.access(self.root.parent, os.R_OK | os.X_OK):
                    raise BackupStorageUnavailable("El almacén de respaldos no está disponible.")
            except OSError:
                raise BackupStorageUnavailable("El almacén de respaldos no está disponible.") from None
        try:
            if not stat.S_ISDIR(self.root.lstat().st_mode):
                raise BackupStorageUnavailable("La ruta de respaldos no es un directorio.")
            entries = list(self.root.iterdir())
        except FileNotFoundError:
            return []
        except OSError:
            raise BackupStorageUnavailable("No se pudo leer el directorio de respaldos.") from None
        indexed = []
        for entry in entries:
            if not _ID.fullmatch(entry.name):
                continue
            try:
                indexed.append(BackupIndexEntry(entry.name, self._read_record(entry.name)))
            except (BackupStoreError, OSError) as exc:
                indexed.append(BackupIndexEntry(entry.name, None, backup_problem(exc)))
        indexed.sort(
            key=lambda entry: (
                datetime.fromisoformat(entry.record.created_at) if entry.record else datetime.min.replace(tzinfo=timezone.utc),
                entry.id,
            ),
            reverse=True,
        )
        return indexed

    def list(self, limit: int = 25) -> list[BackupRecord]:
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
            raise BackupStoreError("Límite de listado inválido.")
        records = [entry.record for entry in self.index()]
        if any(record is None for record in records):
            raise BackupIntegrityError("El historial contiene respaldos ilegibles.")
        return [record for record in records[:limit] if record is not None]

    def count(self) -> int:
        return len(self.index())

    def append_event(self, backup_id: str, event: dict[str, Any]) -> None:
        """Añade una línea al diario privado; no acepta contenido de la partida."""
        directory = self._directory(backup_id)
        if not directory.is_dir():
            raise BackupNotFound("No se encontró el respaldo solicitado.")
        payload = {"at": _now(), **event}
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        path = directory / "events.jsonl"
        line = self._seal(path, encoded) + b"\n"
        flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW
        try:
            descriptor = os.open(path, flags, 0o600)
        except OSError:
            raise BackupStoreError("No se pudo abrir el diario del respaldo.") from None
        try:
            view = memoryview(line)
            while view:
                written = os.write(descriptor, view)
                view = view[written:]
        except OSError:
            raise BackupStoreError("No se pudo registrar el evento del respaldo.") from None
        finally:
            os.close(descriptor)

    @staticmethod
    def _event_object(raw: bytes) -> dict[str, Any]:
        try:
            data = parse_json(raw)
        except (ValueError, RecursionError):
            raise BackupIntegrityError("El diario del respaldo no es válido.") from None
        if not isinstance(data, dict):
            raise BackupIntegrityError("El diario del respaldo no es válido.")
        return data

    def events(self, backup_id: str) -> list[dict[str, Any]]:
        path = self._existing_directory(backup_id) / "events.jsonl"
        try:
            raw = self._read_plain(path, _JOURNAL_LIMIT)
        except BackupNotFound:
            return []
        if self.cipher_key is None:
            return [self._event_object(line) for line in raw.splitlines() if line]
        events = []
        offset = 0
        while offset < len(raw):
            # El cifrado histórico puede contener saltos de línea dentro de cada
            # bloque. Solo se acepta un límite que autentique el bloque entero.
            end = raw.find(b"\n", offset)
            while end != -1 and end - offset <= _RECORD_LIMIT:
                if end == len(raw) - 1 or raw.startswith(_SEAL_MAGIC, end + 1):
                    try:
                        event = self._open(path, raw[offset:end])
                    except BackupUnreadable:
                        pass
                    else:
                        events.append(self._event_object(event))
                        offset = end + 1
                        break
                end = raw.find(b"\n", end + 1)
            else:
                raise BackupUnreadable("El diario del respaldo no se pudo autenticar.")
        return events

    def confirmation_attempted(self, backup_id: str) -> bool:
        path = self._existing_directory(backup_id) / "upload-attempt"
        try:
            marker = self._read_private(path, 1)
        except BackupNotFound:
            return False
        if marker != b"\n":
            raise BackupIntegrityError("El marcador de subida del respaldo no es válido.")
        return True

    def confirmation(self, backup_id: str) -> dict[str, Any] | None:
        path = self._existing_directory(backup_id) / "confirmation.json"
        try:
            raw = self._read_private(path, _RECORD_LIMIT)
        except BackupNotFound:
            return None
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

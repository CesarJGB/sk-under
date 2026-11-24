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

from Crypto.Cipher import AES

from ..cloud_save import MAX_INPUT_BYTES, CloudSaveError, reconstruct_cloud_save
from ..parsers.json_document import parse_json
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
from .gems_editor import GemsEdit, GemsEditError, prepare_gems_edit, read_gems, replay_legacy_gems_edit
from .skill_editor import (
    MAX_SKILLS,
    SKILL_RECORD_FIELD,
    SkillEdit,
    SkillFieldMissing,
    prepare_skill_unlock_edit,
    read_skills,
)

_ID = re.compile(r"^[0-9a-f]{32}$")
_FIELDS = frozenset({"gems", FISH_CHIP_RECORD_FIELD, CHARACTER_RECORD_FIELD, SKILL_RECORD_FIELD})
_RECORD_LIMIT = 64 * 1024
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
    field: str = "gems"
    character_codes: tuple[str, ...] = ()
    skill_selections: tuple[tuple[str, int], ...] = ()

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
    ) -> None:
        if isinstance(limit, bool) or not isinstance(limit, int) or not 0 < limit <= MAX_INPUT_BYTES:
            raise BackupStoreError("Límite de respaldo inválido.")
        if cipher_key is not None and (not isinstance(cipher_key, bytes) or len(cipher_key) != 32):
            raise BackupStoreError("La clave de cifrado de respaldos no tiene 32 bytes.")
        self.root = Path(root).expanduser().absolute()
        self.limit = limit
        self.cipher_key = cipher_key

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
            raise BackupIntegrityError(
                "El respaldo no está cifrado con la clave actual. Migra los respaldos antes de continuar."
            )
        cipher = AES.new(self.cipher_key, AES.MODE_SIV)
        cipher.update(self._context(path))
        try:
            return cipher.decrypt_and_verify(data[len(_SEAL_MAGIC) + _SEAL_TAG:], data[len(_SEAL_MAGIC):len(_SEAL_MAGIC) + _SEAL_TAG])
        except (ValueError, KeyError):
            raise BackupIntegrityError("El respaldo no se pudo descifrar o fue alterado.") from None

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
            descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        except OSError:
            raise BackupNotFound("No se encontró el respaldo solicitado.") from None
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
            raise BackupNotFound("No se pudo leer el respaldo solicitado.") from None
        finally:
            os.close(descriptor)
        if len(data) > limit:
            raise BackupIntegrityError("El archivo de respaldo supera el límite.")
        return data

    def save(
        self,
        edit: GemsEdit | FishChipEdit | SkillEdit,
        *,
        remote_source: str,
        remote_size: int,
        remote_sha256: str,
        field: str = "gems",
        original_value: int | None = None,
        new_value: int | None = None,
        character_codes: tuple[str, ...] | None = None,
        skill_selections: list[dict[str, object]] | tuple[dict[str, object], ...] | None = None,
    ) -> BackupBundle:
        """Crea un respaldo y devuelve los bytes que quedaron en disco.

        ``field`` identifica el único grupo editado (``gems`` o ``fish_chip``).
        Los registros y las respuestas existentes conservan ``original_gems`` y
        ``candidate_gems`` como el valor del campo respaldado para mantener la
        compatibilidad de la Fase 6.13.
        """
        if field not in _FIELDS:
            raise BackupIntegrityError("El tipo de campo del respaldo no es válido.")
        codes = _require_codes(list(character_codes) if character_codes is not None else None)
        skills = _require_skill_selections(
            list(skill_selections) if skill_selections is not None else None
        )
        if field == CHARACTER_RECORD_FIELD:
            if edit.changed and not codes:
                raise BackupIntegrityError("El respaldo de personajes requiere la selección preparada.")
            skills = ()
        elif field == SKILL_RECORD_FIELD:
            if edit.changed and not skills:
                raise BackupIntegrityError("El respaldo de habilidades requiere la selección preparada.")
            codes = ()
        else:
            codes = ()
            skills = ()
        if remote_sha256 != edit.original_sha256 or remote_size != len(edit.original):
            raise BackupIntegrityError("La copia remota no coincide con el original preparado.")
        if original_value is None:
            original_value = getattr(edit, "original_gems", getattr(edit, "original_fish_chip", None))
        if new_value is None:
            new_value = getattr(edit, "new_gems", getattr(edit, "new_fish_chip", None))
        original_value = _require_int(original_value, "original_value")
        new_value = _require_int(new_value, "candidate_value")
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
            descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        except OSError:
            raise BackupNotFound("No se encontró el respaldo solicitado.") from None
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
        raw = self._read_private(self._directory(backup_id) / "record.json", _RECORD_LIMIT)
        try:
            data = parse_json(raw)
        except (ValueError, RecursionError):
            raise BackupIntegrityError("El registro de respaldo no es JSON válido.") from None
        if not isinstance(data, dict):
            raise BackupIntegrityError("El registro de respaldo no es un objeto.")
        field = data.get("field", "gems")
        if field not in _FIELDS:
            raise BackupIntegrityError("El registro de respaldo contiene un tipo de campo inválido.")
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
        if record.changed != (original != candidate):
            raise BackupIntegrityError("El indicador de cambio del respaldo no coincide.")
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

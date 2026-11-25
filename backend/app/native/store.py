"""Almacén privado de perfiles de instalación y sesiones nativas.

Los identificadores de instalación y los tokens se cifran con AES-SIV y se
asocian al perfil o a la sesión. La base SQLite vive en un directorio ``0700``
con archivo ``0600`` y no contiene correos, contraseñas, tokens ni
identificadores en claro. Las sesiones se identifican por el hash SHA-256 de la
cookie; el valor de la cookie nunca se guarda.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import stat
import time
from contextlib import closing, contextmanager
from dataclasses import dataclass, field
from hashlib import sha256
from hmac import compare_digest, new as hmac_new
from pathlib import Path
from typing import Callable
from uuid import uuid4

from Crypto.Cipher import AES

from .distributions import get_distribution
from .errors import (
    NativeInstallationInvalid,
    NativeLoginThrottled,
    NativeProfileExists,
    NativeProfileIdentityMismatch,
    NativeProfileInvalid,
    NativeProfileNotFound,
    NativeSaveIdentityMismatch,
    NativeSessionExpired,
    NativeSessionRequired,
    NativeStoreMisconfigured,
    NativeStoreUnavailable,
)

_COOKIE = re.compile(r"^[A-Za-z0-9_-]{43}$")
_PROFILE = re.compile(r"^[0-9a-f]{32}$")
_DISTRO = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_SUBJECT = re.compile(r"^[0-9a-f]{64}$")
_EMAIL_HASH = re.compile(r"^[0-9a-f]{64}$")
_ATTEMPT_OUTCOMES = frozenset(
    {
        "ok",
        "pending",
        "native_credentials_rejected",
        "native_identity_mismatch",
        "native_profile_identity_mismatch",
        "native_distribution_rejected",
        "native_auth_unavailable",
        "native_auth_protocol",
        "native_login_throttled",
        "native_session_rejected",
        "native_installation_invalid",
        "native_device_binding_throttled",
        "native_save_identity_mismatch",
        "native_profile_invalid",
        "native_profile_not_found",
        "other",
    }
)


def _credential(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip()) and len(value) <= 512 and all(
        33 <= ord(char) <= 126 for char in value
    )


@dataclass(frozen=True)
class Profile:
    id: str
    label: str
    distribution: str
    distro_id: str = field(repr=False)
    unique_id: str | None = field(repr=False)
    subject: str | None = field(repr=False)
    allow_write: bool
    created_at: int
    bound_at: int | None
    email_hash: str | None = field(default=None, repr=False)
    auto_generated: bool = False
    binding_wait_until: int | None = None
    last_save_error: str | None = None

    @property
    def installation_ready(self) -> bool:
        return self.unique_id is not None

    @property
    def bound(self) -> bool:
        return self.subject is not None

    @property
    def binding_pending(self) -> bool:
        return self.binding_wait_until is not None

    def public(self) -> dict[str, object]:
        return {
            "id": self.id,
            "label": self.label,
            "distribution": self.distribution,
            "installation_ready": self.installation_ready,
            "bound": self.bound,
            "write_allowed": self.allow_write,
            "auto_generated": self.auto_generated,
            "binding_pending": self.binding_pending,
            "binding_wait_until": self.binding_wait_until,
            "last_save_error": self.last_save_error,
        }


@dataclass(frozen=True)
class NativeSessionRecord:
    id: str = field(repr=False)
    cookie: str = field(repr=False)
    subject: str = field(repr=False)
    profile: Profile
    token: str = field(repr=False)
    unique_id: str | None = field(repr=False)
    expires_at: int
    idle_expires_at: int
    created_at: int
    email: str | None = field(default=None, repr=False)


@dataclass(frozen=True)
class LoginAttemptStats:
    accepted: bool
    retry_after: int


class NativeStore:
    def __init__(
        self,
        root: Path,
        key: bytes,
        *,
        idle_seconds: int = 1800,
        absolute_seconds: int = 7 * 86400,
        login_attempts: int = 5,
        login_window_seconds: int = 900,
        now: Callable[[], float] = time.time,
    ) -> None:
        if len(key) != 32:
            raise NativeStoreMisconfigured("La clave del almacén nativo no tiene 32 bytes.")
        for value, name, minimum, maximum in (
            (idle_seconds, "idle_seconds", 60, 86400),
            (absolute_seconds, "absolute_seconds", 3600, 30 * 86400),
            (login_attempts, "login_attempts", 1, 50),
            (login_window_seconds, "login_window_seconds", 60, 86400),
        ):
            if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
                raise NativeStoreMisconfigured(f"El valor {name} del almacén nativo no es válido.")
        self.root = Path(root).expanduser().absolute()
        self.key = key
        self.idle_seconds = idle_seconds
        self.absolute_seconds = absolute_seconds
        self.login_attempts = login_attempts
        self.login_window_seconds = login_window_seconds
        self.now = now
        try:
            self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
            info = self.root.stat()
            if not stat.S_ISDIR(info.st_mode) or self.root.is_symlink() or info.st_mode & 0o077:
                raise OSError
            self.database = self.root / "native.sqlite3"
            descriptor = os.open(self.database, os.O_CREAT | os.O_NOFOLLOW | os.O_RDWR, 0o600)
            os.close(descriptor)
            if self.database.stat().st_mode & 0o077:
                raise OSError
            with closing(self.connect()) as db, db:
                db.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS encryption (
                        id INTEGER PRIMARY KEY CHECK (id = 1), verifier BLOB NOT NULL
                    );
                    CREATE TABLE IF NOT EXISTS profiles (
                        id TEXT PRIMARY KEY,
                        label TEXT NOT NULL,
                        distribution TEXT NOT NULL,
                        sealed BLOB NOT NULL,
                        subject TEXT,
                        allow_write INTEGER NOT NULL DEFAULT 0,
                        created_at INTEGER NOT NULL,
                        bound_at INTEGER,
                        email_hash TEXT,
                        auto_generated INTEGER NOT NULL DEFAULT 0,
                        binding_wait_until INTEGER,
                        last_save_error TEXT,
                        UNIQUE (label, distribution)
                    );
                    CREATE UNIQUE INDEX IF NOT EXISTS profiles_subject
                        ON profiles(subject) WHERE subject IS NOT NULL;
                    CREATE TABLE IF NOT EXISTS sessions (
                        id TEXT PRIMARY KEY,
                        profile_id TEXT NOT NULL REFERENCES profiles(id),
                        subject TEXT NOT NULL,
                        token BLOB NOT NULL,
                        email_hash TEXT NOT NULL,
                        uid_hash TEXT NOT NULL,
                        player_hash TEXT NOT NULL,
                        session_expires INTEGER NOT NULL,
                        created_at INTEGER NOT NULL,
                        last_seen INTEGER NOT NULL,
                        revoked INTEGER NOT NULL DEFAULT 0
                    );
                    CREATE INDEX IF NOT EXISTS sessions_by_profile ON sessions(profile_id);
                    CREATE INDEX IF NOT EXISTS sessions_by_subject ON sessions(subject);
                    CREATE TABLE IF NOT EXISTS attempts (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        at INTEGER NOT NULL,
                        ip_hash TEXT NOT NULL,
                        email_hash TEXT NOT NULL,
                        outcome TEXT NOT NULL
                    );
                    CREATE INDEX IF NOT EXISTS attempts_by_ip ON attempts(ip_hash, at);
                    CREATE INDEX IF NOT EXISTS attempts_by_email ON attempts(email_hash, at);
                    CREATE TABLE IF NOT EXISTS events (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        at INTEGER NOT NULL,
                        event TEXT NOT NULL,
                        outcome TEXT NOT NULL,
                        code TEXT,
                        subject TEXT
                    );
                    CREATE TABLE IF NOT EXISTS accounts (
                        subject TEXT PRIMARY KEY,
                        distribution TEXT NOT NULL,
                        save_subject TEXT NOT NULL,
                        created_at INTEGER NOT NULL,
                        last_seen INTEGER NOT NULL
                    );
                    """
                )
                self._migrate_profiles(db)
                db.execute(
                    "CREATE UNIQUE INDEX IF NOT EXISTS profiles_email "
                    "ON profiles(email_hash, distribution) WHERE email_hash IS NOT NULL"
                )
                verifier = hmac_new(self.key, b"sk-under/native-store", sha256).digest()
                db.execute("INSERT OR IGNORE INTO encryption VALUES (1, ?)", (verifier,))
                saved = db.execute("SELECT verifier FROM encryption WHERE id = 1").fetchone()
                if saved is None or not compare_digest(saved["verifier"], verifier):
                    raise NativeStoreMisconfigured(
                        "La clave configurada no corresponde al almacén nativo existente."
                    )
        except NativeStoreMisconfigured:
            raise
        except (OSError, ValueError, sqlite3.Error):
            raise NativeStoreUnavailable(
                "El servidor no puede abrir el almacén privado de sesiones nativas."
            ) from None

    @staticmethod
    def _migrate_profiles(db: sqlite3.Connection) -> None:
        """Añade las columnas de la Fase 6.9 a un almacén de la Fase 6.8.

        ``CREATE TABLE IF NOT EXISTS`` no modifica una tabla existente. La
        migración es idempotente y solo añade columnas; no reescribe perfiles,
        sesiones ni identificadores cifrados.
        """

        columns = {
            row["name"] for row in db.execute("PRAGMA table_info(profiles)").fetchall()
        }
        additions = (
            ("email_hash", "TEXT"),
            ("auto_generated", "INTEGER NOT NULL DEFAULT 0"),
            ("binding_wait_until", "INTEGER"),
            ("last_save_error", "TEXT"),
        )
        for name, declaration in additions:
            if name not in columns:
                db.execute(f"ALTER TABLE profiles ADD COLUMN {name} {declaration}")

    def connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.database.as_uri() + "?mode=rw", uri=True, timeout=5)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")
        db.execute("PRAGMA secure_delete = ON")
        db.execute("PRAGMA busy_timeout = 5000")
        return db

    # Cifrado y derivaciones -------------------------------------------------

    def _seal(self, context: str, values: dict[str, object]) -> bytes:
        cipher = AES.new(self.key, AES.MODE_SIV)
        cipher.update(context.encode("utf-8"))
        payload = json.dumps(values, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        encrypted, tag = cipher.encrypt_and_digest(payload)
        return tag + encrypted

    def _open(self, context: str, sealed: object) -> dict[str, object]:
        if not isinstance(sealed, bytes) or len(sealed) < 17:
            raise NativeStoreMisconfigured("El almacén nativo contiene un registro cifrado inválido.")
        cipher = AES.new(self.key, AES.MODE_SIV)
        cipher.update(context.encode("utf-8"))
        try:
            payload = cipher.decrypt_and_verify(sealed[16:], sealed[:16])
            values = json.loads(payload)
        except (ValueError, UnicodeDecodeError, RecursionError):
            raise NativeStoreMisconfigured("El servidor no puede descifrar el almacén nativo.") from None
        if not isinstance(values, dict):
            raise NativeStoreMisconfigured("El almacén nativo contiene un registro inválido.")
        return values

    def _digest(self, domain: str, value: str) -> str:
        return hmac_new(self.key, domain.encode("utf-8") + b"\x00" + value.encode("utf-8"), sha256).hexdigest()

    def hash_ip(self, ip: str) -> str:
        return self._digest("ip", ip)

    def hash_email(self, email: str) -> str:
        return self._digest("email", email.strip().casefold())

    def identity_subject(self, *, email: str, uid: int, player_id: int) -> str:
        return self._digest("native-identity", f"{email.strip().casefold()}\x00{uid}\x00{player_id}")

    def hash_uid(self, uid: int) -> str:
        return self._digest("uid", str(uid))

    def hash_player(self, player_id: int) -> str:
        return self._digest("player", str(player_id))

    def save_subject(self, distribution: str, payload: bytes) -> str:
        try:
            document = json.loads(payload)
        except (ValueError, UnicodeDecodeError, RecursionError):
            raise NativeSaveIdentityMismatch("La partida no contiene identificadores de cuenta válidos.") from None
        if not isinstance(document, dict):
            raise NativeSaveIdentityMismatch("La partida no contiene identificadores de cuenta válidos.")
        identity = [document.get("cloudSaveId"), document.get("platformId")]
        if any(not isinstance(part, str) or not part or len(part) > 512 for part in identity):
            raise NativeSaveIdentityMismatch("La partida no contiene identificadores de cuenta válidos.")
        serialized = json.dumps(identity, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        return hmac_new(
            self.key,
            b"native-save\x00" + distribution.encode("utf-8") + b"\x00" + serialized,
            sha256,
        ).hexdigest()

    # Perfiles ---------------------------------------------------------------

    def _profile(self, row: sqlite3.Row) -> Profile:
        sealed = self._open("profile:" + row["id"], row["sealed"])
        distro = sealed.get("distro")
        unique = sealed.get("unique")
        if not isinstance(distro, str) or not isinstance(unique, (str, type(None))):
            raise NativeStoreMisconfigured("El perfil de instalación no se puede descifrar.")
        return Profile(
            id=row["id"],
            label=row["label"],
            distribution=row["distribution"],
            distro_id=distro,
            unique_id=unique,
            subject=row["subject"],
            allow_write=bool(row["allow_write"]),
            created_at=row["created_at"],
            bound_at=row["bound_at"],
            email_hash=row["email_hash"],
            auto_generated=bool(row["auto_generated"]),
            binding_wait_until=row["binding_wait_until"],
            last_save_error=row["last_save_error"],
        )

    def create_profile(
        self,
        *,
        label: str,
        distribution_id: str,
        distro_id: str,
        unique_id: str | None = None,
        allow_write: bool = False,
        email_hash: str | None = None,
        auto_generated: bool = False,
    ) -> Profile:
        label = label.strip() if isinstance(label, str) else ""
        if not 1 <= len(label) <= 80 or not label.isprintable():
            raise NativeProfileInvalid("La etiqueta del perfil debe tener entre 1 y 80 caracteres visibles.")
        distribution = get_distribution(distribution_id)
        if not distribution.enabled or not distribution.validated:
            from .errors import NativeDistributionDisabled

            raise NativeDistributionDisabled("Solo se pueden aprovisionar distribuciones validadas.")
        if not isinstance(distro_id, str) or not _DISTRO.fullmatch(distro_id):
            raise NativeInstallationInvalid("El identificador de distribución no tiene un formato válido.")
        if unique_id is not None and not _credential(unique_id):
            raise NativeInstallationInvalid("El identificador de instalación no tiene un formato válido.")
        if email_hash is not None and not _EMAIL_HASH.fullmatch(email_hash):
            raise NativeProfileInvalid("El hash de correo del perfil no es válido.")
        if not isinstance(auto_generated, bool):
            raise NativeProfileInvalid("El indicador de perfil automático no es válido.")
        profile_id = uuid4().hex
        sealed = self._seal("profile:" + profile_id, {"distro": distro_id, "unique": unique_id})
        try:
            with closing(self.connect()) as db, db:
                db.execute(
                    "INSERT INTO profiles (id, label, distribution, sealed, subject, allow_write, created_at, "
                    "email_hash, auto_generated) VALUES (?, ?, ?, ?, NULL, ?, ?, ?, ?)",
                    (
                        profile_id, label, distribution.id, sealed, int(bool(allow_write)),
                        int(self.now()), email_hash, int(auto_generated),
                    ),
                )
        except sqlite3.IntegrityError:
            if email_hash is not None:
                raise NativeProfileIdentityMismatch(
                    "Esta cuenta ya tiene un perfil de instalación en esta distribución."
                ) from None
            raise NativeProfileExists("Ya existe un perfil con esa etiqueta para la distribución.") from None
        return self.profile(profile_id)

    def profile_by_email_hash(self, email_hash: str, distribution_id: str) -> Profile | None:
        if not isinstance(email_hash, str) or not _EMAIL_HASH.fullmatch(email_hash):
            raise NativeProfileInvalid("El hash de correo del perfil no es válido.")
        if not isinstance(distribution_id, str) or not distribution_id:
            raise NativeProfileInvalid("La distribución del perfil no es válida.")
        with closing(self.connect()) as db:
            row = db.execute(
                "SELECT * FROM profiles WHERE email_hash = ? AND distribution = ?",
                (email_hash, distribution_id),
            ).fetchone()
        return self._profile(row) if row else None

    def profile_by_subject(self, subject: str) -> Profile | None:
        if not isinstance(subject, str) or not _SUBJECT.fullmatch(subject):
            raise NativeProfileInvalid("La identidad del perfil no es válida.")
        with closing(self.connect()) as db:
            row = db.execute("SELECT * FROM profiles WHERE subject = ?", (subject,)).fetchone()
        return self._profile(row) if row else None

    def profile(self, profile_id: str) -> Profile:
        if not isinstance(profile_id, str) or not _PROFILE.fullmatch(profile_id):
            raise NativeProfileNotFound("El perfil de instalación no existe.")
        with closing(self.connect()) as db:
            row = db.execute("SELECT * FROM profiles WHERE id = ?", (profile_id,)).fetchone()
        if row is None:
            raise NativeProfileNotFound("El perfil de instalación no existe.")
        return self._profile(row)

    def find_profile(self, label: str, distribution_id: str) -> Profile | None:
        with closing(self.connect()) as db:
            row = db.execute(
                "SELECT * FROM profiles WHERE label = ? AND distribution = ?",
                (label, distribution_id),
            ).fetchone()
        return self._profile(row) if row else None

    def list_profiles(self, distribution_id: str | None = None) -> list[Profile]:
        with closing(self.connect()) as db:
            if distribution_id is None:
                rows = db.execute("SELECT * FROM profiles ORDER BY created_at, label").fetchall()
            else:
                rows = db.execute(
                    "SELECT * FROM profiles WHERE distribution = ? ORDER BY created_at, label",
                    (distribution_id,),
                ).fetchall()
        return [self._profile(row) for row in rows]

    def bind(self, profile_id: str, subject: str, *, email_hash: str | None = None) -> Profile:
        if not isinstance(subject, str) or not _SUBJECT.fullmatch(subject):
            raise NativeStoreMisconfigured("La identidad derivada no es válida.")
        if email_hash is not None and not _EMAIL_HASH.fullmatch(email_hash):
            raise NativeProfileInvalid("El hash de correo del perfil no es válido.")
        with closing(self.connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM profiles WHERE id = ?", (profile_id,)).fetchone()
            if row is None:
                raise NativeProfileNotFound("El perfil de instalación no existe.")
            stored_email = row["email_hash"]
            if stored_email is not None and email_hash is not None and not compare_digest(
                stored_email, email_hash
            ):
                raise NativeProfileIdentityMismatch(
                    "Este perfil de instalación ya está vinculado a otra cuenta. "
                    "No se reutilizan identificadores entre cuentas."
                )
            if row["subject"] is None:
                try:
                    db.execute(
                        "UPDATE profiles SET subject = ?, bound_at = ?, "
                        "email_hash = COALESCE(email_hash, ?) WHERE id = ? AND subject IS NULL",
                        (subject, int(self.now()), email_hash, profile_id),
                    )
                except sqlite3.IntegrityError:
                    raise NativeProfileIdentityMismatch(
                        "Esta cuenta ya tiene otro perfil de instalación vinculado."
                    ) from None
                row = db.execute("SELECT * FROM profiles WHERE id = ?", (profile_id,)).fetchone()
            elif not compare_digest(row["subject"], subject):
                raise NativeProfileIdentityMismatch(
                    "Este perfil de instalación ya está vinculado a otra cuenta. "
                    "No se reutilizan identificadores entre cuentas."
                )
            elif email_hash is not None and row["email_hash"] is None:
                try:
                    db.execute(
                        "UPDATE profiles SET email_hash = ? WHERE id = ? AND email_hash IS NULL",
                        (email_hash, profile_id),
                    )
                except sqlite3.IntegrityError:
                    raise NativeProfileIdentityMismatch(
                        "Esta cuenta ya tiene otro perfil de instalación vinculado."
                    ) from None
                row = db.execute("SELECT * FROM profiles WHERE id = ?", (profile_id,)).fetchone()
        return self._profile(row)

    def set_binding_wait(self, profile_id: str, until: int, code: str) -> Profile:
        if type(until) is not int or until <= int(self.now()):
            raise NativeProfileInvalid("La espera de vinculación no es válida.")
        if not isinstance(code, str) or not code or len(code) > 64:
            raise NativeProfileInvalid("El código de vinculación no es válido.")
        with closing(self.connect()) as db, db:
            db.execute(
                "UPDATE profiles SET binding_wait_until = ?, last_save_error = ? WHERE id = ?",
                (until, code, profile_id),
            )
            row = db.execute("SELECT * FROM profiles WHERE id = ?", (profile_id,)).fetchone()
        if row is None:
            raise NativeProfileNotFound("El perfil de instalación no existe.")
        return self._profile(row)

    def clear_binding_wait(self, profile_id: str) -> Profile:
        with closing(self.connect()) as db, db:
            db.execute(
                "UPDATE profiles SET binding_wait_until = NULL, last_save_error = NULL WHERE id = ?",
                (profile_id,),
            )
            row = db.execute("SELECT * FROM profiles WHERE id = ?", (profile_id,)).fetchone()
        if row is None:
            raise NativeProfileNotFound("El perfil de instalación no existe.")
        return self._profile(row)

    def set_save_error(self, profile_id: str, code: str | None) -> Profile:
        if code is not None and (not isinstance(code, str) or not code or len(code) > 64):
            raise NativeProfileInvalid("El código de guardado no es válido.")
        with closing(self.connect()) as db, db:
            db.execute("UPDATE profiles SET last_save_error = ? WHERE id = ?", (code, profile_id))
            row = db.execute("SELECT * FROM profiles WHERE id = ?", (profile_id,)).fetchone()
        if row is None:
            raise NativeProfileNotFound("El perfil de instalación no existe.")
        return self._profile(row)

    def delete_unbound_profile(self, profile_id: str) -> None:
        """Elimina un perfil automático que no llegó a vincularse a una cuenta."""

        with closing(self.connect()) as db, db:
            db.execute(
                "DELETE FROM profiles WHERE id = ? AND subject IS NULL AND auto_generated = 1",
                (profile_id,),
            )

    def set_installation(self, profile_id: str, unique_id: str, subject: str) -> Profile:
        if not _credential(unique_id):
            raise NativeInstallationInvalid("El identificador de instalación no tiene un formato válido.")
        with closing(self.connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM profiles WHERE id = ?", (profile_id,)).fetchone()
            if row is None:
                raise NativeProfileNotFound("El perfil de instalación no existe.")
            if row["subject"] is None or not compare_digest(row["subject"], subject):
                raise NativeProfileIdentityMismatch("El perfil no pertenece a la sesión actual.")
            values = self._open("profile:" + profile_id, row["sealed"])
            values["unique"] = unique_id
            sealed = self._seal("profile:" + profile_id, values)
            db.execute("UPDATE profiles SET sealed = ? WHERE id = ?", (sealed, profile_id))
            row = db.execute("SELECT * FROM profiles WHERE id = ?", (profile_id,)).fetchone()
        return self._profile(row)

    def update_installation(
        self, profile_id: str, distro_id: str, unique_id: str, subject: str
    ) -> Profile:
        """Actualiza el par de un perfil ya vinculado a la misma identidad.

        Solo se usa cuando el portal devuelve un distro vigente distinto del
        guardado y la identidad (subject) ya se verificó. No permite cambiar
        de cuenta ni reutilizar el perfil para otro subject.
        """

        if not isinstance(distro_id, str) or not _DISTRO.fullmatch(distro_id):
            raise NativeInstallationInvalid("El identificador de distribución no tiene un formato válido.")
        if not _credential(unique_id):
            raise NativeInstallationInvalid("El identificador de instalación no tiene un formato válido.")
        if not isinstance(subject, str) or not _SUBJECT.fullmatch(subject):
            raise NativeProfileIdentityMismatch("La identidad del perfil no es válida.")
        with closing(self.connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM profiles WHERE id = ?", (profile_id,)).fetchone()
            if row is None:
                raise NativeProfileNotFound("El perfil de instalación no existe.")
            if row["subject"] is None or not compare_digest(row["subject"], subject):
                raise NativeProfileIdentityMismatch("El perfil no pertenece a la identidad verificada.")
            sealed = self._seal("profile:" + profile_id, {"distro": distro_id, "unique": unique_id})
            db.execute(
                "UPDATE profiles SET sealed = ?, binding_wait_until = NULL, last_save_error = NULL "
                "WHERE id = ?",
                (sealed, profile_id),
            )
            row = db.execute("SELECT * FROM profiles WHERE id = ?", (profile_id,)).fetchone()
        return self._profile(row)

    # Sesiones ---------------------------------------------------------------

    def create_session(
        self,
        cookie: str,
        *,
        profile_id: str,
        subject: str,
        token: str,
        session_expire: int,
        email_hash: str,
        uid_hash: str,
        player_hash: str,
        email: str | None = None,
    ) -> int:
        if not isinstance(cookie, str) or not _COOKIE.fullmatch(cookie):
            raise NativeStoreMisconfigured("El identificador de sesión generado no es válido.")
        if not _credential(token):
            raise NativeStoreMisconfigured("La sesión recibida no contiene un token válido.")
        if email is not None and (not isinstance(email, str) or not email.strip() or len(email) > 320):
            raise NativeStoreMisconfigured("El correo de la sesión no es válido.")
        if type(session_expire) is not int:
            raise NativeStoreMisconfigured("La caducidad de la sesión no es válida.")
        now = int(self.now())
        expires_at = min(session_expire, now + self.absolute_seconds)
        if expires_at <= now:
            raise NativeSessionExpired("La sesión del proveedor ya está caducada.")
        session_id = sha256(cookie.encode("ascii")).hexdigest()
        values: dict[str, object] = {"token": token}
        if email is not None:
            values["email"] = email.strip()
        sealed = self._seal("session:" + session_id, values)
        with closing(self.connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            profile = db.execute("SELECT subject FROM profiles WHERE id = ?", (profile_id,)).fetchone()
            if profile is None:
                raise NativeProfileNotFound("El perfil de instalación no existe.")
            if profile["subject"] is None or not compare_digest(profile["subject"], subject):
                raise NativeProfileIdentityMismatch("El perfil no pertenece a la cuenta autenticada.")
            db.execute(
                "DELETE FROM sessions WHERE session_expires <= ? "
                "OR last_seen + ? <= ? OR (revoked = 1 AND last_seen < ?)",
                (now, self.idle_seconds, now, now - 86400),
            )
            db.execute(
                "INSERT INTO sessions (id, profile_id, subject, token, email_hash, uid_hash, player_hash, "
                "session_expires, created_at, last_seen, revoked) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)",
                (session_id, profile_id, subject, sealed, email_hash, uid_hash, player_hash,
                 expires_at, now, now),
            )
        return expires_at

    def session(self, cookie: str) -> NativeSessionRecord:
        if not isinstance(cookie, str) or not _COOKIE.fullmatch(cookie):
            raise NativeSessionRequired("Inicia sesión para continuar.")
        session_id = sha256(cookie.encode("ascii")).hexdigest()
        now = int(self.now())
        with closing(self.connect()) as db, db:
            row = db.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
            if row is None:
                raise NativeSessionRequired("Inicia sesión para continuar.")
            if bool(row["revoked"]) or row["session_expires"] <= now:
                raise NativeSessionExpired("La sesión caducó. Vuelve a iniciar sesión.")
            idle_expires = row["last_seen"] + self.idle_seconds
            if idle_expires <= now:
                raise NativeSessionExpired("La sesión caducó por inactividad. Vuelve a iniciar sesión.")
            db.execute("UPDATE sessions SET last_seen = ? WHERE id = ?", (now, session_id))
            profile_id = row["profile_id"]
            subject = row["subject"]
            sealed = row["token"]
            expires_at = row["session_expires"]
            created_at = row["created_at"]
            idle_expires = now + self.idle_seconds
        profile = self.profile(profile_id)
        if profile.subject is None or not compare_digest(profile.subject, subject):
            raise NativeSessionExpired("La sesión ya no corresponde al perfil. Vuelve a iniciar sesión.")
        opened = self._open("session:" + session_id, sealed)
        token = opened.get("token")
        email = opened.get("email")
        if not isinstance(token, str) or not token:
            raise NativeStoreMisconfigured("La sesión no se puede descifrar.")
        if email is not None and not isinstance(email, str):
            raise NativeStoreMisconfigured("La sesión contiene un correo inválido.")
        return NativeSessionRecord(
            id=session_id,
            cookie=cookie,
            subject=subject,
            profile=profile,
            token=token,
            unique_id=profile.unique_id,
            expires_at=expires_at,
            idle_expires_at=idle_expires,
            created_at=created_at,
            email=email,
        )

    def revoke(self, cookie: str) -> None:
        if not isinstance(cookie, str) or not _COOKIE.fullmatch(cookie):
            return
        session_id = sha256(cookie.encode("ascii")).hexdigest()
        with closing(self.connect()) as db, db:
            db.execute("DELETE FROM sessions WHERE id = ?", (session_id,))

    def session_stats(self) -> tuple[int, int]:
        now = int(self.now())
        with closing(self.connect()) as db:
            row = db.execute(
                "SELECT COUNT(*) AS total, "
                "SUM(CASE WHEN revoked = 0 AND session_expires > ? THEN 1 ELSE 0 END) AS active "
                "FROM sessions",
                (now,),
            ).fetchone()
        return int(row["total"] or 0), int(row["active"] or 0)

    # Límite de intentos -----------------------------------------------------

    def reserve_login_attempt(self, ip_hash: str, email_hash: str) -> int:
        """Reserva un intento antes de autenticar, de forma atómica.

        La comprobación y la inserción ocurren en la misma transacción
        ``BEGIN IMMEDIATE``. Un intento en curso cuenta como no exitoso, de
        modo que dos solicitudes concurrentes no pueden superar el límite
        leyendo un contador obsoleto.
        """

        if not _SUBJECT.fullmatch(ip_hash) or not _SUBJECT.fullmatch(email_hash):
            raise NativeStoreMisconfigured("La clave del límite de intentos no es válida.")
        now = int(self.now())
        window_start = now - self.login_window_seconds
        with closing(self.connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("DELETE FROM attempts WHERE at < ?", (now - 86400,))
            ip_row = db.execute(
                "SELECT COUNT(*) AS total, MIN(at) AS oldest FROM attempts "
                "WHERE ip_hash = ? AND at >= ? AND outcome != 'ok'",
                (ip_hash, window_start),
            ).fetchone()
            email_row = db.execute(
                "SELECT COUNT(*) AS total, MIN(at) AS oldest FROM attempts "
                "WHERE email_hash = ? AND at >= ? AND outcome != 'ok'",
                (email_hash, window_start),
            ).fetchone()
            limit = max(int(ip_row["total"]), int(email_row["total"]))
            if limit >= self.login_attempts:
                oldest = min(
                    value for value in (ip_row["oldest"], email_row["oldest"]) if value is not None
                )
                retry_after = max(1, int(oldest) + self.login_window_seconds - now)
                raise NativeLoginThrottled(
                    "Demasiados intentos de acceso en esta ventana. Espera antes de reintentar.",
                    retry_after=retry_after,
                )
            cursor = db.execute(
                "INSERT INTO attempts (at, ip_hash, email_hash, outcome) VALUES (?, ?, ?, 'pending')",
                (now, ip_hash, email_hash),
            )
            return int(cursor.lastrowid)

    def finish_login_attempt(self, attempt_id: int, outcome: str) -> None:
        if type(attempt_id) is not int or attempt_id <= 0:
            return
        safe_outcome = outcome if outcome in _ATTEMPT_OUTCOMES else "other"
        with closing(self.connect()) as db, db:
            db.execute(
                "UPDATE attempts SET outcome = ? WHERE id = ?",
                (safe_outcome, attempt_id),
            )

    def check_login_rate(self, ip_hash: str, email_hash: str) -> None:
        """Comprobación de solo lectura; el servicio usa la reserva atómica."""

        now = int(self.now())
        window_start = now - self.login_window_seconds
        with closing(self.connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("DELETE FROM attempts WHERE at < ?", (now - 86400,))
            ip_row = db.execute(
                "SELECT COUNT(*) AS total, MIN(at) AS oldest FROM attempts "
                "WHERE ip_hash = ? AND at >= ? AND outcome != 'ok'",
                (ip_hash, window_start),
            ).fetchone()
            email_row = db.execute(
                "SELECT COUNT(*) AS total, MIN(at) AS oldest FROM attempts "
                "WHERE email_hash = ? AND at >= ? AND outcome != 'ok'",
                (email_hash, window_start),
            ).fetchone()
            limit = max(int(ip_row["total"]), int(email_row["total"]))
            if limit >= self.login_attempts:
                oldest = min(
                    value for value in (ip_row["oldest"], email_row["oldest"]) if value is not None
                )
                retry_after = max(1, int(oldest) + self.login_window_seconds - now)
                raise NativeLoginThrottled(
                    "Demasiados intentos de acceso en esta ventana. Espera antes de reintentar.",
                    retry_after=retry_after,
                )

    def record_attempt(self, ip_hash: str, email_hash: str, outcome: str) -> None:
        """Registra un intento ya resuelto (compatibilidad y diagnóstico)."""

        safe_outcome = outcome if outcome in _ATTEMPT_OUTCOMES else "other"
        with closing(self.connect()) as db, db:
            db.execute(
                "INSERT INTO attempts (at, ip_hash, email_hash, outcome) VALUES (?, ?, ?, ?)",
                (int(self.now()), ip_hash, email_hash, safe_outcome),
            )

    def cleanup(self, *, unbound_profile_age: int = 7 * 86400) -> None:
        """Elimina sesiones caducadas, intentos viejos y perfiles no vinculados.

        Se ejecuta al arrancar el servicio. No toca perfiles vinculados,
        respaldos ni identificadores de instalación válidos.
        """

        now = int(self.now())
        with closing(self.connect()) as db, db:
            db.execute(
                "DELETE FROM sessions WHERE session_expires <= ? OR revoked = 1",
                (now - 86400,),
            )
            db.execute("DELETE FROM attempts WHERE at < ?", (now - 7 * 86400,))
            db.execute(
                "DELETE FROM profiles WHERE subject IS NULL AND auto_generated = 1 "
                "AND created_at < ?",
                (now - unbound_profile_age,),
            )

    # Identidad de guardado y auditoría -------------------------------------

    def bind_save_subject(self, subject: str, distribution: str, save_subject: str) -> None:
        if not _SUBJECT.fullmatch(save_subject):
            raise NativeSaveIdentityMismatch("La identidad de la partida no es válida.")
        now = int(self.now())
        with closing(self.connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            db.execute(
                "INSERT OR IGNORE INTO accounts (subject, distribution, save_subject, created_at, last_seen) "
                "VALUES (?, ?, ?, ?, ?)",
                (subject, distribution, save_subject, now, now),
            )
            row = db.execute("SELECT save_subject FROM accounts WHERE subject = ?", (subject,)).fetchone()
            if row is None or not compare_digest(row["save_subject"], save_subject):
                raise NativeSaveIdentityMismatch(
                    "La partida devuelta no corresponde a la cuenta autenticada."
                )
            db.execute("UPDATE accounts SET last_seen = ? WHERE subject = ?", (now, subject))

    def record_event(
        self,
        event: str,
        outcome: str,
        *,
        code: str | None = None,
        subject: str | None = None,
    ) -> None:
        if not isinstance(event, str) or len(event) > 64 or not event.isascii():
            raise ValueError("nombre de evento inválido")
        safe_outcome = outcome if isinstance(outcome, str) and len(outcome) <= 64 else "unknown"
        safe_code = code if isinstance(code, str) and len(code) <= 64 else None
        safe_subject = subject if isinstance(subject, str) and _SUBJECT.fullmatch(subject) else None
        with closing(self.connect()) as db, db:
            db.execute(
                "INSERT INTO events (at, event, outcome, code, subject) VALUES (?, ?, ?, ?, ?)",
                (int(self.now()), event, safe_outcome, safe_code, safe_subject),
            )

    def recent_events(self, limit: int = 20) -> list[dict[str, object]]:
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
            raise ValueError("límite de eventos inválido")
        with closing(self.connect()) as db:
            rows = db.execute(
                "SELECT at, event, outcome, code, subject FROM events ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            {
                "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(row["at"])),
                "event": row["event"],
                "outcome": row["outcome"],
                "code": row["code"],
                "subject": (row["subject"][:12] if row["subject"] else None),
            }
            for row in rows
        ]

    def profile_stats(self) -> tuple[int, int]:
        with closing(self.connect()) as db:
            row = db.execute(
                "SELECT COUNT(*) AS total, "
                "SUM(CASE WHEN subject IS NOT NULL THEN 1 ELSE 0 END) AS bound "
                "FROM profiles"
            ).fetchone()
        return int(row["total"] or 0), int(row["bound"] or 0)

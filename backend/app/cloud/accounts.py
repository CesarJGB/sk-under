"""Cuentas Android Global autorizadas por el operador con una sesión ya emitida."""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import re
import sqlite3
from contextlib import closing, contextmanager
from dataclasses import dataclass, field
from hashlib import sha256
from hmac import compare_digest, digest
from pathlib import Path
from secrets import token_urlsafe
from time import time
from urllib.parse import urlsplit
from uuid import uuid4

from Crypto.Cipher import AES

from ..cloud_save import MAX_INPUT_BYTES, CloudSaveError
from ..settings import Settings
from .backup_store import LabBackupStore
from .blob_upload import BlobSaveUploader
from .gems_editor import read_gems
from .lab_service import CloudLabService
from .modern import ModernCloudSaveProvider
from .provider import CloudProviderUnauthenticated

TICKET_TTL = 600
BROWSER_TTL = 90 * 86400
_TOKEN = re.compile(r"[A-Za-z0-9_-]{43}")
_ACCOUNT = re.compile(r"[0-9a-f]{32}")


class AccountError(Exception):
    def __init__(self, code: str, message: str, status: int = 409):
        super().__init__(message)
        self.code = code
        self.status = status


class AccountMismatch(CloudSaveError):
    code = "cloud_account_mismatch"


def _hash_token(value: str) -> str:
    return sha256(value.encode("ascii")).hexdigest()


def _subject(key: bytes, payload: bytes) -> str:
    data = json.loads(payload)
    identity = [data.get("cloudSaveId"), data.get("platformId")]
    if any(not isinstance(part, str) or not part or len(part) > 512 for part in identity):
        raise AccountMismatch("La partida carece de identificadores de cuenta válidos.")
    return digest(key, b"android-global\x00" + json.dumps(identity).encode(), "sha256").hex()


@dataclass(frozen=True)
class AccountProvider:
    remote: ModernCloudSaveProvider
    key: bytes = field(repr=False)
    subject: str = field(repr=False)

    def download(self, limit: int = MAX_INPUT_BYTES):
        save = self.remote.download(limit)
        if not compare_digest(_subject(self.key, save.payload), self.subject):
            raise AccountMismatch("La partida devuelta no corresponde a la cuenta vinculada.")
        return save


class CloudAccounts:
    def __init__(self, settings: Settings) -> None:
        origin = settings.cloud_accounts_origin
        if origin not in settings.allowed_origins:
            raise AccountError("cloud_accounts_origin", "Configura el origen seguro para las cuentas.", 503)
        parsed = urlsplit(origin)
        local = settings.env == "development" and parsed.hostname in {"localhost", "127.0.0.1", "::1"}
        if not (parsed.scheme == "https" or local):
            raise AccountError("cloud_accounts_origin", "Configura el origen seguro para las cuentas.", 503)
        key = settings.cloud_accounts_key
        raw_key = key.get_secret_value() if key else ""
        if not re.fullmatch(r"[0-9a-fA-F]{64}", raw_key):
            raise AccountError("cloud_accounts_key", "Falta la clave de cifrado de las cuentas.", 503)
        self.key = bytes.fromhex(raw_key)
        self.origin = origin
        self.secure = parsed.scheme == "https"
        self.cookie_name = "__Host-sk_under" if self.secure else "sk_under_dev"
        self.write_enabled = settings.cloud_write_enabled
        self.root = settings.cloud_accounts_dir or settings.cloud_backup_dir.parent / "accounts"
        try:
            if not self.root.is_absolute() or self.root.resolve() == settings.cloud_backup_dir.resolve():
                raise ValueError
            self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
            if self.root.is_symlink() or self.root.stat().st_mode & 0o077:
                raise OSError
            self.database = self.root / "accounts.sqlite3"
            os.close(os.open(self.database, os.O_CREAT | os.O_NOFOLLOW | os.O_RDWR, 0o600))
            if self.database.stat().st_mode & 0o077:
                raise OSError
            with closing(self.connect()) as db, db:
                db.executescript("""
                    CREATE TABLE IF NOT EXISTS encryption (
                        id INTEGER PRIMARY KEY CHECK (id = 1), verifier BLOB NOT NULL
                    );
                    CREATE TABLE IF NOT EXISTS browsers (
                        id TEXT PRIMARY KEY, expires INTEGER NOT NULL
                    );
                    CREATE TABLE IF NOT EXISTS accounts (
                        id TEXT PRIMARY KEY, subject TEXT NOT NULL UNIQUE,
                        owner TEXT REFERENCES browsers(id), label TEXT NOT NULL,
                        sealed BLOB, expires INTEGER, can_write INTEGER NOT NULL DEFAULT 0
                    );
                    CREATE INDEX IF NOT EXISTS accounts_by_owner ON accounts(owner);
                    CREATE TABLE IF NOT EXISTS grants (
                        token TEXT PRIMARY KEY, account_id TEXT UNIQUE NOT NULL REFERENCES accounts(id),
                        sealed BLOB NOT NULL, session_expires INTEGER NOT NULL,
                        can_write INTEGER NOT NULL, expires INTEGER NOT NULL
                    );
                """)
                verifier = digest(self.key, b"sk-under/cloud-accounts", "sha256")
                db.execute("INSERT OR IGNORE INTO encryption VALUES (1, ?)", (verifier,))
                saved = db.execute("SELECT verifier FROM encryption WHERE id = 1").fetchone()
                if not compare_digest(saved["verifier"], verifier):
                    raise AccountError("cloud_accounts_key", "La clave no corresponde al almacén de cuentas.", 503)
        except (OSError, ValueError, sqlite3.Error):
            raise AccountError(
                "cloud_accounts_storage", "El servidor no puede abrir el almacén privado de cuentas.", 503
            ) from None

    def connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.database)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")
        db.execute("PRAGMA secure_delete = ON")
        return db

    def seal(self, account_id: str, values: tuple[str, str, str]) -> bytes:
        cipher = AES.new(self.key, AES.MODE_SIV)
        cipher.update(("cloud-session:" + account_id).encode())
        encrypted, tag = cipher.encrypt_and_digest(json.dumps(values).encode())
        return tag + encrypted

    def open(self, account_id: str, sealed: bytes) -> tuple[str, str, str]:
        cipher = AES.new(self.key, AES.MODE_SIV)
        cipher.update(("cloud-session:" + account_id).encode())
        try:
            return tuple(json.loads(cipher.decrypt_and_verify(sealed[16:], sealed[:16])))
        except ValueError:
            raise AccountError("cloud_accounts_key", "El servidor no puede descifrar la sesión de la cuenta.", 503) from None

    def issue(self, label: str, values: tuple[str, str, str], *, expires: int, can_write: bool) -> str:
        if expires <= time():
            raise AccountError("cloud_session_expired", "La sesión de ChillyRoom ya caducó.")
        save = ModernCloudSaveProvider(*values).download()
        read_gems(save.payload)
        subject = _subject(self.key, save.payload)
        ticket = token_urlsafe(32)
        with closing(self.connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("DELETE FROM grants WHERE expires <= ?", (int(time()),))
            db.execute("INSERT OR IGNORE INTO accounts (id, subject, label) VALUES (?, ?, ?)",
                       (uuid4().hex, subject, label))
            account = db.execute("SELECT id FROM accounts WHERE subject = ?", (subject,)).fetchone()
            db.execute("REPLACE INTO grants VALUES (?, ?, ?, ?, ?, ?)",
                       (_hash_token(ticket), account["id"], self.seal(account["id"], values),
                        expires, can_write, int(time()) + TICKET_TTL))
        return ticket

    def owner(self, db: sqlite3.Connection, cookie: str) -> str | None:
        if _TOKEN.fullmatch(cookie):
            owner = _hash_token(cookie)
            found = db.execute("SELECT 1 FROM browsers WHERE id = ? AND expires > ?", (owner, int(time())))
            if found.fetchone():
                return owner
        return None

    def claim(self, cookie: str, ticket: str) -> str:
        token = _hash_token(ticket)
        with closing(self.connect()) as db:
            pending = db.execute("SELECT account_id FROM grants WHERE token = ?", (token,)).fetchone()
        if pending is None:
            raise AccountError("cloud_grant_invalid", "El enlace de vinculación ya se usó o caducó.", 404)
        with self.locked(pending["account_id"]), closing(self.connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            grant = db.execute(
                """SELECT grants.*, accounts.owner, browsers.expires AS owner_expires
                   FROM grants JOIN accounts ON accounts.id = account_id
                   LEFT JOIN browsers ON browsers.id = accounts.owner
                   WHERE token = ? AND grants.expires > ? AND session_expires > ?""",
                (token, int(time()), int(time())),
            ).fetchone()
            if grant is None:
                raise AccountError("cloud_grant_invalid", "El enlace de vinculación ya se usó o caducó.", 404)
            owner = self.owner(db, cookie)
            if (grant["owner_expires"] or 0) > time() and grant["owner"] != owner:
                raise AccountError("cloud_account_linked", "Abre el enlace en el navegador que ya tiene vinculada esta cuenta.")
            if owner is None:
                cookie = token_urlsafe(32)
                owner = _hash_token(cookie)
                db.execute("INSERT INTO browsers VALUES (?, ?)", (owner, int(time()) + BROWSER_TTL))
            else:
                db.execute("UPDATE browsers SET expires = ? WHERE id = ?", (int(time()) + BROWSER_TTL, owner))
            db.execute("UPDATE accounts SET owner = ?, sealed = ?, expires = ?, can_write = ? WHERE id = ?",
                       (owner, grant["sealed"], grant["session_expires"], grant["can_write"], grant["account_id"]))
            db.execute("DELETE FROM grants WHERE token = ?", (grant["token"],))
        return cookie

    def list(self, cookie: str) -> list[dict]:
        with closing(self.connect()) as db:
            owner = self.owner(db, cookie)
            rows = db.execute("SELECT id, label, expires, can_write FROM accounts WHERE owner = ? ORDER BY label, id",
                              (owner,))
            return [
                {
                    "id": row["id"], "label": row["label"], "platform": "android-global",
                    "connected": bool(row["expires"] and row["expires"] > time()),
                    "write_ready": bool(self.write_enabled and row["can_write"] and row["expires"] and row["expires"] > time()),
                }
                for row in rows
            ]

    @contextmanager
    def locked(self, account_id: str):
        if not _ACCOUNT.fullmatch(account_id):
            raise AccountError("cloud_account_missing", "La cuenta vinculada no existe.", 404)
        path = self.root / f"{account_id}.lock"
        with os.fdopen(os.open(path, os.O_CREAT | os.O_NOFOLLOW | os.O_RDWR, 0o600), "rb") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            yield

    def owned(self, db: sqlite3.Connection, cookie: str, account_id: str) -> sqlite3.Row:
        owner = self.owner(db, cookie)
        if owner is None:
            raise AccountError("cloud_browser_required", "Vincula una cuenta en este navegador.", 401)
        row = db.execute("SELECT * FROM accounts WHERE id = ? AND owner = ?", (account_id, owner)).fetchone()
        if row is None:
            raise AccountError("cloud_account_missing", "La cuenta vinculada no existe.", 404)
        return row

    def update(self, cookie: str, account_id: str, *, label: str | None = None) -> None:
        with self.access(cookie, account_id) as (db, _), db:
            if label is not None:
                db.execute("UPDATE accounts SET label = ? WHERE id = ?", (label, account_id))
                return
            db.execute("UPDATE accounts SET owner = NULL, sealed = NULL, expires = NULL, can_write = 0 WHERE id = ?",
                       (account_id,))
            db.execute("DELETE FROM grants WHERE account_id = ?", (account_id,))

    @contextmanager
    def access(self, cookie: str, account_id: str):
        with closing(self.connect()) as db:
            self.owned(db, cookie, account_id)
            with self.locked(account_id):
                yield db, self.owned(db, cookie, account_id)

    @contextmanager
    def service(self, cookie: str, account_id: str, *, offline: bool = False):
        with self.access(cookie, account_id) as (db, row):
            store = LabBackupStore(self.root / "backups" / account_id)
            if offline:
                yield store
                return
            if not row["sealed"] or row["expires"] <= time():
                raise AccountError("cloud_session_expired", "La sesión caducó. Solicita un nuevo enlace para reconectar.")
            values = self.open(account_id, row["sealed"])
            provider = AccountProvider(ModernCloudSaveProvider(*values), self.key, row["subject"])
            write = self.write_enabled and bool(row["can_write"])
            uploader = BlobSaveUploader(*values, enabled=True) if write else None
            try:
                yield CloudLabService(provider, store, uploader=uploader, write_enabled=write)
            except CloudProviderUnauthenticated:
                with db:
                    db.execute("UPDATE accounts SET expires = 0, sealed = NULL WHERE id = ? AND sealed = ?",
                               (account_id, row["sealed"]))
                raise AccountError("cloud_session_expired", "ChillyRoom rechazó la sesión. Reconecta esta cuenta.") from None


def main() -> None:
    parser = argparse.ArgumentParser(description="Emitir un enlace privado para una sesión Android Global verificada.")
    parser.add_argument("--label", required=True)
    parser.add_argument("--expires", type=int, required=True, help="Caducidad real del token en segundos Unix")
    parser.add_argument("--allow-write", action="store_true", help="Autorizar escritura para esta cuenta")
    args = parser.parse_args()
    settings = Settings()
    credentials = (settings.cloud_session_token, settings.cloud_unique_id, settings.cloud_distro_id)
    if not all(credentials):
        parser.error("Falta la sesión emitida por ChillyRoom en el entorno privado del operador.")
    if not 1 <= len(label := args.label.strip()) <= 80 or not label.isprintable():
        parser.error("La etiqueta debe tener entre 1 y 80 caracteres visibles.")
    try:
        accounts = CloudAccounts(settings)
        ticket = accounts.issue(label, tuple(value.get_secret_value() for value in credentials),
                                expires=args.expires, can_write=args.allow_write)
    except CloudSaveError as exc:
        parser.exit(1, f"No se pudo verificar la cuenta en ChillyRoom ({exc.code}).\n")
    except AccountError as exc:
        parser.exit(1, f"{exc}\n")
    print(f"{accounts.origin}/partida#vincular={ticket}")


if __name__ == "__main__":
    main()

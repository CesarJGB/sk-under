"""Servicio de autenticación nativa, sesiones y editor de gemas por cuenta.

Cada sesión web queda ligada a una sola identidad de ChillyRoom: el perfil de
instalación se vincula a la identidad en el primer acceso y los respaldos viven
en un directorio derivado de esa identidad. No hay una sesión global ni un
``account_id`` elegible desde el navegador; todas las operaciones usan
exclusivamente la cookie del titular.
"""

from __future__ import annotations

import fcntl
import os
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from secrets import token_urlsafe
from time import time
from typing import Callable
from urllib.parse import urlsplit

from ..cloud.backup_store import LabBackupStore
from ..cloud.gems_editor import MAX_GEMS, MIN_GEMS, read_gems
from ..cloud.lab_service import CloudLabService
from ..cloud.provider import (
    AcquiredCloudSave,
    CloudProviderUnauthenticated,
    CloudSaveMetadata,
)
from ..cloud_save import MAX_INPUT_BYTES, CloudSaveError
from ..settings import Settings
from .client import NativeAuthClient
from .distributions import DISTRIBUTIONS, Distribution, get_distribution, require_enabled
from .errors import (
    NativeError,
    NativeIdentityMismatch,
    NativeInstallationRequired,
    NativeMisconfigured,
    NativeProfileMissing,
    NativeProfileNotFound,
    NativeProfileRequired,
    NativeSaveIdentityMismatch,
    NativeSessionExpired,
    NativeSessionRejected,
    NativeSessionRequired,
    NativeWriteDenied,
    NativeWriteDisabled,
)
from .store import NativeSessionRecord, NativeStore, Profile


def _iso(timestamp: int) -> str:
    return datetime.fromtimestamp(timestamp, UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


@dataclass(frozen=True)
class NativeSaveProvider:
    """Proveedor por sesión que además fija la identidad de la partida."""

    remote: object
    store: NativeStore
    subject: str = field(repr=False)
    distribution: str

    def download(self, limit: int = MAX_INPUT_BYTES) -> AcquiredCloudSave:
        save = self.remote.download(limit)
        save_subject = self.store.save_subject(self.distribution, save.payload)
        self.store.bind_save_subject(self.subject, self.distribution, save_subject)
        return save

    def metadata(self) -> CloudSaveMetadata:
        return self.download().metadata


@dataclass(frozen=True)
class LoginResult:
    cookie: str = field(repr=False)
    expires_at: int
    idle_expires_at: int
    body: dict[str, object]


@dataclass(frozen=True)
class NativeRuntime:
    service: "NativeAuthService | None"
    problem: NativeError | None
    enabled: bool


class NativeAuthService:
    def __init__(
        self,
        *,
        store: NativeStore,
        client: NativeAuthClient,
        origin: str,
        secure: bool,
        write_enabled: bool,
        backup_root: Path,
        provider_factory: Callable[[str, str, str], object],
        uploader_factory: Callable[[str, str, str], object],
        min_gems: int = MIN_GEMS,
        max_gems: int = MAX_GEMS,
        now: Callable[[], float] = time,
    ) -> None:
        self.store = store
        self.client = client
        self.origin = origin
        self.secure = secure
        self.write_enabled = write_enabled
        self.backup_root = Path(backup_root).expanduser().absolute()
        self.provider_factory = provider_factory
        self.uploader_factory = uploader_factory
        self.min_gems = min_gems
        self.max_gems = max_gems
        self.now = now
        self.cookie_name = "__Host-sk_native" if secure else "sk_native_dev"

    # Configuración y estado -------------------------------------------------

    def config(self, cookie: str = "") -> dict[str, object]:
        profiles = []
        if self.store is not None:
            profiles = [
                profile.public()
                for profile in self.store.list_profiles()
                if get_distribution(profile.distribution).enabled
            ]
        return {
            "available": True,
            "configured": True,
            "native_auth_ready": bool(profiles),
            "write_enabled": self.write_enabled,
            "secure": self.secure,
            "min_gems": self.min_gems,
            "max_gems": self.max_gems,
            "login_available": bool(profiles),
            "profiles": profiles,
            "distributions": [distribution.public() for distribution in DISTRIBUTIONS],
            "session": self.session_state(cookie),
        }

    def session_state(self, cookie: str = "") -> dict[str, object]:
        if not cookie:
            return {"active": False, "reason": "none"}
        try:
            session = self.store.session(cookie)
        except NativeSessionExpired:
            return {
                "active": False,
                "reason": "expired",
                "message": "La sesión caducó. Inicia sesión de nuevo.",
            }
        except NativeSessionRequired:
            return {"active": False, "reason": "none"}
        return self._view(session)

    def require_session(self, cookie: str) -> NativeSessionRecord:
        return self.store.session(cookie)

    def _view(self, session: NativeSessionRecord) -> dict[str, object]:
        return self._view_values(session.profile, session.expires_at, session.idle_expires_at)

    def _view_values(self, profile: Profile, expires_at: int, idle_expires_at: int) -> dict[str, object]:
        distribution = get_distribution(profile.distribution)
        installation_ready = profile.installation_ready
        return {
            "active": True,
            "identity_verified": True,
            "account": {
                "label": profile.label,
                "distribution": distribution.id,
                "distribution_label": distribution.label,
                "platform": distribution.platform,
            },
            "session_expires_at": _iso(expires_at),
            "idle_expires_at": _iso(idle_expires_at),
            "installation_ready": installation_ready,
            "write_enabled": self.write_enabled,
            "write_ready": self.write_enabled and profile.allow_write and installation_ready,
            "min_gems": self.min_gems,
            "max_gems": self.max_gems,
        }

    # Inicio y cierre de sesión ---------------------------------------------

    def login(
        self,
        *,
        email: str,
        password: str,
        distribution_id: str,
        profile_id: str | None,
        ip: str,
        existing_cookie: str = "",
    ) -> LoginResult:
        distribution = require_enabled(distribution_id)
        profile = self._resolve_profile(distribution, profile_id)
        ip_hash = self.store.hash_ip(ip)
        email_hash = self.store.hash_email(email)
        self.store.check_login_rate(ip_hash, email_hash)

        outcome = "other"
        try:
            session = self.client.authenticate(
                email,
                password,
                distribution=distribution,
                distro_id=profile.distro_id,
            )
            if session.email.strip().casefold() != email.strip().casefold():
                raise NativeIdentityMismatch("El correo de la sesión no coincide con la cuenta solicitada.")
            if session.distro_id != profile.distro_id:
                raise NativeIdentityMismatch("La sesión no corresponde al perfil de instalación.")
            subject = self.store.identity_subject(
                email=session.email, uid=session.uid, player_id=session.player_id
            )
            profile = self.store.bind(profile.id, subject)
            outcome = "ok"
        except NativeError as exc:
            outcome = exc.code
            self._event("login", "rejected", code=exc.code)
            raise
        finally:
            try:
                self.store.record_attempt(ip_hash, email_hash, outcome)
            except Exception:
                # Un fallo del diario no debe ocultar el resultado del login.
                pass

        if existing_cookie:
            self.store.revoke(existing_cookie)

        save: dict[str, object] | None = None
        save_error: str | None = None
        if profile.unique_id is not None:
            try:
                save = self._verify_save(profile, session.token, subject)
            except NativeSaveIdentityMismatch:
                # Una partida de otra cuenta es un fallo de identidad, no un
                # aviso: no se crea sesión para esa copia.
                self._event("login", "rejected", code="native_save_identity_mismatch", subject=subject)
                raise
            except CloudProviderUnauthenticated:
                # El gateway aceptó las credenciales, pero BlobSave rechazó el
                # token. No se crea una sesión que no puede operar.
                self._event("login", "rejected", code="native_session_rejected", subject=subject)
                raise NativeSessionRejected(
                    "ChillyRoom rechazó la sesión emitida para el servicio de guardado. "
                    "No se creó ninguna sesión web."
                ) from None
            except NativeError as exc:
                save_error = exc.code
            except CloudSaveError as exc:
                save_error = exc.code
        else:
            save_error = "native_installation_required"

        cookie = token_urlsafe(32)
        expires_at = self.store.create_session(
            cookie,
            profile_id=profile.id,
            subject=subject,
            token=session.token,
            session_expire=session.expire,
            email_hash=email_hash,
            uid_hash=self.store.hash_uid(session.uid),
            player_hash=self.store.hash_player(session.player_id),
        )
        idle_expires_at = int(self.now()) + self.store.idle_seconds
        self._event("login", "ok", subject=subject)
        view = self._view_values(profile, expires_at, idle_expires_at)
        view["save"] = save
        view["save_error"] = save_error
        return LoginResult(
            cookie=cookie,
            expires_at=expires_at,
            idle_expires_at=idle_expires_at,
            body=view,
        )

    def logout(self, cookie: str) -> None:
        self.store.revoke(cookie)
        self._event("logout", "ok")

    def complete_installation(self, cookie: str, unique_id: str) -> dict[str, object]:
        session = self.store.session(cookie)
        profile = self.store.set_installation(session.profile.id, unique_id, session.subject)
        session = self.store.session(cookie)
        save: dict[str, object] | None = None
        save_error: str | None = None
        try:
            save = self._verify_save(profile, session.token, session.subject)
        except CloudProviderUnauthenticated:
            self.store.revoke(cookie)
            self._event("installation", "rejected", code="native_session_expired", subject=session.subject)
            raise NativeSessionExpired(
                "ChillyRoom rechazó la sesión al comprobar la instalación. Vuelve a iniciar sesión."
            ) from None
        except (NativeError, CloudSaveError) as exc:
            save_error = exc.code
        view = self._view_values(profile, session.expires_at, session.idle_expires_at)
        view["save"] = save
        view["save_error"] = save_error
        self._event("installation", "ok" if save else "pending", subject=session.subject)
        return view

    # Operaciones del editor ------------------------------------------------

    def load(self, session: NativeSessionRecord) -> dict[str, object]:
        return self._operate(session, lambda: self._lab(session).load().summary() | {
            "downloaded_at": _iso(int(self.now()))
        })

    def prepare(self, session: NativeSessionRecord, new_gems: object, source_sha256: str) -> dict[str, object]:
        return self._operate(
            session,
            lambda: self._lab(session).prepare(new_gems, expected_source=source_sha256).summary(),
        )

    def confirm(self, session: NativeSessionRecord, backup_id: str, expected_sha256: str) -> dict[str, object]:
        self._require_write(session)
        with self._subject_lock(session.subject):
            return self._operate(
                session,
                lambda: self._lab(session).confirm(backup_id, expected_sha256, single_attempt=True).summary(),
            )

    def restore(self, session: NativeSessionRecord, backup_id: str) -> dict[str, object]:
        self._require_write(session)
        with self._subject_lock(session.subject):
            return self._operate(session, lambda: self._lab(session).restore(backup_id).summary())

    def verify(self, session: NativeSessionRecord, backup_id: str) -> dict[str, object]:
        return self._operate(session, lambda: self._lab(session).verify(backup_id).summary())

    def backups(self, session: NativeSessionRecord) -> list[dict[str, object]]:
        store = LabBackupStore(self.backup_root / session.subject)
        return [
            record.summary() | {"confirmed": store.confirmation(record.id) is not None}
            for record in store.list()
        ]

    # Diagnóstico saneado ----------------------------------------------------

    def diagnostics(self) -> dict[str, object]:
        total_profiles, bound_profiles = self.store.profile_stats()
        total_sessions, active_sessions = self.store.session_stats()
        return {
            "enabled": True,
            "configured": True,
            "write_enabled": self.write_enabled,
            "cookie_secure": self.secure,
            "origin_scheme": urlsplit(self.origin).scheme,
            "store_ready": True,
            "profiles_total": total_profiles,
            "profiles_bound": bound_profiles,
            "sessions_total": total_sessions,
            "sessions_active": active_sessions,
            "idle_seconds": self.store.idle_seconds,
            "login_attempts": self.store.login_attempts,
            "login_window_seconds": self.store.login_window_seconds,
            "distributions": [
                {"id": item.id, "enabled": item.enabled, "validated": item.validated}
                for item in DISTRIBUTIONS
            ],
            "events": self.store.recent_events(),
        }

    # Internos ---------------------------------------------------------------

    def _resolve_profile(self, distribution: Distribution, profile_id: str | None) -> Profile:
        profiles = [
            profile for profile in self.store.list_profiles(distribution.id)
            if get_distribution(profile.distribution).enabled
        ]
        if profile_id:
            profile = self.store.profile(profile_id)
            if profile.distribution != distribution.id:
                raise NativeProfileNotFound("El perfil no corresponde a la distribución seleccionada.")
            return profile
        if not profiles:
            raise NativeProfileMissing(
                "No hay un perfil de instalación aprovisionado para Android Global. "
                "El propietario debe aprovisionarlo antes de iniciar sesión."
            )
        if len(profiles) == 1:
            return profiles[0]
        raise NativeProfileRequired("Selecciona el perfil de instalación que corresponde a esta cuenta.")

    def _verify_save(self, profile: Profile, token: str, subject: str) -> dict[str, object]:
        if profile.unique_id is None:
            raise NativeInstallationRequired("Completa el identificador de instalación para descargar la partida.")
        provider = NativeSaveProvider(
            self.provider_factory(token, profile.unique_id, profile.distro_id),
            self.store,
            subject,
            profile.distribution,
        )
        save = provider.download()
        gems = read_gems(save.payload)
        self._event("save_verify", "ok", subject=subject)
        return {
            "verified": True,
            "bytes": save.metadata.size,
            "sha256": save.metadata.sha256,
            "gems": gems.gems,
            "sections": None,
            "remote_source": save.metadata.source,
        }

    def _lab(self, session: NativeSessionRecord) -> CloudLabService:
        if session.unique_id is None:
            raise NativeInstallationRequired(
                "Completa el identificador de instalación para acceder a la partida."
            )
        write = self.write_enabled and session.profile.allow_write
        provider = NativeSaveProvider(
            self.provider_factory(session.token, session.unique_id, session.profile.distro_id),
            self.store,
            session.subject,
            session.profile.distribution,
        )
        uploader = (
            self.uploader_factory(session.token, session.unique_id, session.profile.distro_id)
            if write else None
        )
        return CloudLabService(
            provider,
            LabBackupStore(self.backup_root / session.subject),
            uploader=uploader,
            write_enabled=write,
            admin_configured=True,
        )

    def _require_write(self, session: NativeSessionRecord) -> None:
        if not self.write_enabled:
            raise NativeWriteDisabled(
                "La escritura remota está deshabilitada en este entorno experimental."
            )
        if not session.profile.allow_write:
            raise NativeWriteDenied("Esta cuenta está autorizada solo para lectura.")
        if session.unique_id is None:
            raise NativeInstallationRequired("Completa la instalación antes de escribir.")

    def _operate(self, session: NativeSessionRecord, operation):
        try:
            return operation()
        except CloudProviderUnauthenticated:
            self.store.revoke(session.cookie)
            self._event("session", "rejected", code="native_session_expired", subject=session.subject)
            raise NativeSessionExpired(
                "ChillyRoom rechazó la sesión. Vuelve a iniciar sesión."
            ) from None

    @contextmanager
    def _subject_lock(self, subject: str):
        locks = self.backup_root / "_locks"
        locks.mkdir(mode=0o700, parents=True, exist_ok=True)
        descriptor = os.open(locks / f"{subject}.lock", os.O_CREAT | os.O_NOFOLLOW | os.O_RDWR, 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle, fcntl.LOCK_UN)

    def _event(self, event: str, outcome: str, *, code: str | None = None, subject: str | None = None) -> None:
        try:
            self.store.record_event(event, outcome, code=code, subject=subject)
        except Exception:
            pass


def _default_provider(token: str, unique_id: str, distro_id: str):
    from ..cloud.modern import ModernCloudSaveProvider

    return ModernCloudSaveProvider(token, unique_id, distro_id)


def _default_uploader(token: str, unique_id: str, distro_id: str):
    from ..cloud.blob_upload import BlobSaveUploader

    return BlobSaveUploader(token, unique_id, distro_id, enabled=True)


def _native_dirs(settings: Settings) -> tuple[Path, Path]:
    base = Path.home() / ".local" / "share" / "sk-under"
    store_dir = settings.native_store_dir or base / "native"
    backup_dir = settings.native_backup_dir or base / "native-backups"
    return Path(store_dir).expanduser().absolute(), Path(backup_dir).expanduser().absolute()


def build_native(settings: Settings) -> NativeRuntime:
    if not settings.native_auth_enabled:
        return NativeRuntime(None, None, False)
    try:
        origin = (settings.native_origin or settings.cloud_accounts_origin).removesuffix("/")
        if not origin:
            raise NativeMisconfigured(
                "Configura SK_NATIVE_ORIGIN con el origen HTTPS exacto del editor."
            )
        parsed = urlsplit(origin)
        local = settings.env == "development" and parsed.hostname in {"localhost", "127.0.0.1", "::1"}
        if origin not in settings.allowed_origins:
            raise NativeMisconfigured(
                "El origen del editor debe estar incluido exactamente en SK_ALLOWED_ORIGINS."
            )
        if not (parsed.scheme == "https" or local):
            raise NativeMisconfigured("El origen del editor debe usar HTTPS.")
        key = settings.native_store_key
        raw_key = key.get_secret_value() if key else ""
        if len(raw_key) != 64 or any(char not in "0123456789abcdefABCDEF" for char in raw_key):
            raise NativeMisconfigured(
                "Falta SK_NATIVE_STORE_KEY (32 bytes aleatorios en 64 dígitos hexadecimales)."
            )
        store_dir, backup_dir = _native_dirs(settings)
        if store_dir == backup_dir:
            raise NativeMisconfigured("Los directorios nativos de sesiones y respaldos deben ser distintos.")
        store = NativeStore(
            store_dir,
            bytes.fromhex(raw_key),
            idle_seconds=settings.native_idle_seconds,
            absolute_seconds=settings.native_absolute_seconds,
            login_attempts=settings.native_login_attempts,
            login_window_seconds=settings.native_login_window_seconds,
        )
        service = NativeAuthService(
            store=store,
            client=NativeAuthClient(),
            origin=origin,
            secure=parsed.scheme == "https",
            write_enabled=settings.native_write_enabled,
            backup_root=backup_dir,
            provider_factory=_default_provider,
            uploader_factory=_default_uploader,
        )
        distro = settings.native_distro_id.get_secret_value() if settings.native_distro_id else ""
        unique = settings.native_unique_id.get_secret_value() if settings.native_unique_id else None
        if distro:
            label = settings.native_profile_label
            if store.find_profile(label, "android-global") is None:
                store.create_profile(
                    label=label,
                    distribution_id="android-global",
                    distro_id=distro,
                    unique_id=unique,
                    allow_write=settings.native_profile_allow_write,
                )
        return NativeRuntime(service, None, True)
    except NativeError as exc:
        return NativeRuntime(None, exc, True)
    except (OSError, ValueError):
        return NativeRuntime(
            None,
            NativeMisconfigured("No se pudo inicializar el servicio de autenticación nativa."),
            True,
        )

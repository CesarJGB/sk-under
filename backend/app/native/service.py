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
import threading
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from secrets import token_urlsafe
from time import time
from typing import Callable
from urllib.parse import urlsplit

from ..cloud.advanced_editor import read_advanced_source
from ..cloud.backup_store import LabBackupStore
from ..cloud.fish_chip_editor import MAX_FISH_CHIP, MIN_FISH_CHIP, read_fish_chip
from ..cloud.fish_progress_editor import read_fish_progress
from ..cloud.gems_editor import MAX_GEMS, MIN_GEMS, read_gems
from ..cloud.lab_service import CloudLabService
from ..cloud.provider import (
    AcquiredCloudSave,
    CloudProviderDeviceBindingThrottled,
    CloudProviderUnauthenticated,
    CloudProviderUnavailable,
    CloudSaveMetadata,
)
from ..cloud_save import MAX_INPUT_BYTES, CloudSaveError
from ..settings import Settings
from .client import (
    GatewaySession,
    NativeAuthClient,
    NativeAuthRejected,
    NativeDistributionRejected,
)
from .distributions import DISTRIBUTIONS, Distribution, get_distribution, require_enabled
from .errors import (
    NativeDeviceBindingThrottled,
    NativeError,
    NativeIdentityMismatch,
    NativeInstallationRequired,
    NativeMisconfigured,
    NativeNoCloudSave,
    NativePortalIdentityMismatch,
    NativeProfileIdentityMismatch,
    NativeProfileInvalid,
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
from .portal import PortalClient, PortalPlayer
from .identity import (
    GeneratedIdentity,
    generate_identity,
    is_generated_distro,
    is_generated_unique,
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
class _Candidate:
    """Resultado de probar un jugador del portal antes de crear el perfil."""

    distro_id: str = field(repr=False)
    unique_id: str = field(repr=False)
    session: GatewaySession
    subject: str = field(repr=False)
    save: dict[str, object] | None
    save_error: str | None
    retry_after: int | None = None
    reuse_profile: bool = False


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
        min_fish_chip: int = MIN_FISH_CHIP,
        max_fish_chip: int = MAX_FISH_CHIP,
        auto_identity: bool = True,
        auto_allow_write: bool = False,
        portal_client: PortalClient | None = None,
        backup_key: bytes | None = None,
        identity_factory: Callable[[], GeneratedIdentity] = generate_identity,
        now: Callable[[], float] = time,
    ) -> None:
        if backup_key is not None and (not isinstance(backup_key, bytes) or len(backup_key) != 32):
            raise ValueError("La clave de respaldos nativos no tiene 32 bytes.")
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
        self.min_fish_chip = min_fish_chip
        self.max_fish_chip = max_fish_chip
        self.auto_identity = bool(auto_identity)
        self.auto_allow_write = bool(auto_allow_write)
        self.portal_client = portal_client
        self._discovery_lock = threading.Lock()
        self.backup_key = backup_key
        self.identity_factory = identity_factory
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
        login_available = self.auto_identity or bool(profiles)
        return {
            "available": True,
            "configured": True,
            "native_auth_ready": login_available,
            "write_enabled": self.write_enabled,
            "secure": self.secure,
            "min_gems": self.min_gems,
            "max_gems": self.max_gems,
            "min_fish_chip": self.min_fish_chip,
            "max_fish_chip": self.max_fish_chip,
            "fish_chip_write_policy": "confirmed_by_owner",
            "character_write_policy": "confirmed_by_owner",
            "skill_write_policy": "confirmed_by_owner",
            "skin_write_policy": "confirmed_by_owner",
            "login_available": login_available,
            "auto_identity": self.auto_identity,
            "portal_enabled": self.portal_client is not None,
            "requires_profile_selection": (not self.auto_identity and len(profiles) > 1),
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
            "auto_identity": profile.auto_generated,
            "binding_wait_until": _iso(profile.binding_wait_until) if profile.binding_wait_until else None,
            "save_error": profile.last_save_error,
            "write_enabled": self.write_enabled,
            "write_ready": self.write_enabled and profile.allow_write and installation_ready,
            "min_gems": self.min_gems,
            "max_gems": self.max_gems,
            "min_fish_chip": self.min_fish_chip,
            "max_fish_chip": self.max_fish_chip,
            "fish_chip_write_policy": "confirmed_by_owner",
            "character_write_policy": "confirmed_by_owner",
            "skill_write_policy": "confirmed_by_owner",
            "skin_write_policy": "confirmed_by_owner",
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
        ip_hash = self.store.hash_ip(ip)
        email_hash = self.store.hash_email(email)
        attempt_id = self.store.reserve_login_attempt(ip_hash, email_hash)

        profile: Profile | None = None
        created = False
        outcome = "other"
        try:
            if profile_id:
                profile = self._resolve_profile(distribution, profile_id)
                if profile.email_hash is not None and profile.email_hash != email_hash:
                    raise NativeProfileIdentityMismatch(
                        "Ese perfil de instalación pertenece a otra cuenta y no se reutiliza."
                    )
                session, subject, save, save_error = self._login_known_profile(
                    profile, email, password, distribution, email_hash
                )
            elif self.auto_identity:
                existing = self.store.profile_by_email_hash(email_hash, distribution.id)
                if existing is not None:
                    profile = existing
                    session, subject, save, save_error = self._login_known_profile(
                        profile, email, password, distribution, email_hash
                    )
                else:
                    # Serializa la primera resolución de una cuenta: el portal
                    # y la vinculación son costosos y no deben duplicarse si dos
                    # pestañas inician sesión a la vez.
                    with self._discovery_lock:
                        existing = self.store.profile_by_email_hash(email_hash, distribution.id)
                        if existing is not None:
                            profile = existing
                            session, subject, save, save_error = self._login_known_profile(
                                profile, email, password, distribution, email_hash
                            )
                        else:
                            profile, session, subject, save, save_error, created = self._discover_profile(
                                email, password, distribution, email_hash
                            )
            else:
                profile = self._resolve_profile(distribution, None)
                session, subject, save, save_error = self._login_known_profile(
                    profile, email, password, distribution, email_hash
                )
            outcome = "ok"
        except NativeError as exc:
            outcome = exc.code
            if created and profile is not None:
                self._discard_unbound_auto(profile.id)
            self._event("login", "rejected", code=exc.code)
            raise
        finally:
            try:
                self.store.finish_login_attempt(attempt_id, outcome)
            except Exception:
                # Un fallo del diario no debe ocultar el resultado del login.
                pass

        if existing_cookie:
            self.store.revoke(existing_cookie)

        if profile is None:
            raise NativeProfileNotFound("No se pudo resolver el perfil de instalación.")
        profile = self.store.profile(profile.id)

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

    def prepare_unified(
        self, session: NativeSessionRecord, plan: dict[str, object], source_sha256: str
    ) -> dict[str, object]:
        """Prepara todos los cambios sobre un único candidato y un único respaldo."""
        return self._operate(
            session,
            lambda: self._lab(session).prepare_unified(
                plan, expected_source=source_sha256
            ).summary(),
        )

    def prepare_fish_chip(
        self, session: NativeSessionRecord, new_fish_chip: object, source_sha256: str
    ) -> dict[str, object]:
        """Escritura autorizada de las dos rutas de pesca.

        Aplica el mismo entero a ``gameData.fishChip`` y a
        ``itemData.materials.material_fish``. No se habilitan otros campos de
        pesca. El respaldo y la restauración comparten el almacén existente y
        la confirmación sigue exigiendo la misma autorización del perfil.
        """
        return self._operate(
            session,
            lambda: self._lab(session).prepare_fish_chip(
                new_fish_chip, expected_source=source_sha256
            ).summary(),
        )

    def prepare_fish_progress(
        self, session: NativeSessionRecord, new_cumulative_fish_count: object, source_sha256: str
    ) -> dict[str, object]:
        """Prepara el cambio aislado del progreso acumulado de fichas.

        Solo modifica ``itemData.cumulativeFishCount``. No cambia el saldo, el
        material espejo, los historiales ni las recompensas reclamadas.
        """
        return self._operate(
            session,
            lambda: self._lab(session).prepare_fish_progress(
                new_cumulative_fish_count, expected_source=source_sha256
            ).summary(),
        )

    def prepare_advanced(
        self, session: NativeSessionRecord, plan: dict[str, object], source_sha256: str
    ) -> dict[str, object]:
        """Prepara un lote atómico de materiales, semillas, moneda de temporada,
        tarjeta de renacimiento y pase de batalla local."""
        return self._operate(
            session,
            lambda: self._lab(session).prepare_advanced(
                plan, expected_source=source_sha256
            ).summary(),
        )

    def prepare_characters(
        self, session: NativeSessionRecord, codes: list[str], source_sha256: str
    ) -> dict[str, object]:
        """Prepara el desbloqueo confirmado de los personajes seleccionados.

        Solo cambia ``gameData.heroUnlock`` para los códigos indicados. Los
        niveles, habilidades, skins y el resto de la partida no se modifican.
        """
        return self._operate(
            session,
            lambda: self._lab(session).prepare_characters(
                codes, expected_source=source_sha256
            ).summary(),
        )

    def prepare_skills(
        self,
        session: NativeSessionRecord,
        skills: list[dict[str, object]],
        source_sha256: str,
    ) -> dict[str, object]:
        """Prepara el desbloqueo confirmado de habilidades seleccionadas.

        Solo activa posiciones existentes de ``gameData.heroSkillUnlock`` y
        conserva ``gameData.heroSkill`` y los demás campos de la partida.
        """
        return self._operate(
            session,
            lambda: self._lab(session).prepare_skills(
                skills, expected_source=source_sha256
            ).summary(),
        )

    def prepare_skins(
        self,
        session: NativeSessionRecord,
        skins: list[dict[str, object]],
        source_sha256: str,
    ) -> dict[str, object]:
        """Prepara el desbloqueo de skins seleccionadas.

        Solo cambia a ``1`` posiciones existentes de ``gameData.skinLock`` y
        conserva la skin equipada, los personajes y el resto de la partida.
        """
        return self._operate(
            session,
            lambda: self._lab(session).prepare_skins(
                skins, expected_source=source_sha256
            ).summary(),
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
        store = LabBackupStore(self.backup_root / session.subject, cipher_key=self.backup_key)
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

    def _login_known_profile(
        self,
        profile: Profile,
        email: str,
        password: str,
        distribution: Distribution,
        email_hash: str,
    ) -> tuple[GatewaySession, str, dict[str, object] | None, str | None]:
        session = self.client.authenticate(
            email,
            password,
            distribution=distribution,
            distro_id=profile.distro_id,
            unique_id=profile.unique_id,
        )
        if session.email.strip().casefold() != email.strip().casefold():
            raise NativeIdentityMismatch("El correo de la sesión no coincide con la cuenta solicitada.")
        if session.distro_id != profile.distro_id:
            raise NativeIdentityMismatch("La sesión no corresponde al perfil de instalación.")
        subject = self.store.identity_subject(
            email=session.email, uid=session.uid, player_id=session.player_id
        )
        self.store.bind(profile.id, subject, email_hash=email_hash)
        save, save_error = self._save_or_error(profile, session.token, subject)
        return session, subject, save, save_error

    def _save_or_error(
        self,
        profile: Profile,
        token: str,
        subject: str,
    ) -> tuple[dict[str, object] | None, str | None]:
        if profile.unique_id is None:
            return None, "native_installation_required"
        try:
            return self._verify_save(profile, token, subject), None
        except NativeSaveIdentityMismatch:
            raise
        except CloudProviderUnauthenticated:
            raise NativeSessionRejected(
                "ChillyRoom rechazó la sesión emitida para el servicio de guardado. "
                "No se creó ninguna sesión web."
            ) from None
        except (NativeError, CloudSaveError) as exc:
            return None, exc.code

    def _discover_profile(
        self,
        email: str,
        password: str,
        distribution: Distribution,
        email_hash: str,
    ) -> tuple[Profile, GatewaySession, str, dict[str, object] | None, str | None, bool]:
        """Resuelve el jugador con el portal y crea el perfil autónomo.

        El portal es la fuente autorizada del distro del jugador. Si la cuenta
        no tiene jugadores, se genera una instalación nueva. Si el portal falla,
        no se inventa un distro: se devuelve el error para no crear un jugador
        vacío que no corresponde a la partida del titular.
        """

        identity = self.identity_factory()
        if not is_generated_distro(identity.distro_id) or not is_generated_unique(identity.unique_id):
            raise NativeProfileInvalid(
                "El generador de identidad produjo un par que no cumple el formato observado."
            )
        players: tuple[PortalPlayer, ...] = ()
        if self.portal_client is not None:
            portal = self.portal_client.profile(email, password)
            players = portal.soulknight_players()
        if players:
            candidate = self._select_portal_candidate(
                email, password, distribution, identity.unique_id, players
            )
        else:
            candidate = self._probe_candidate(
                email,
                password,
                distribution,
                distro_id=identity.distro_id,
                unique_id=identity.unique_id,
                portal_pid=None,
            )
        existing = self.store.profile_by_subject(candidate.subject)
        if candidate.reuse_profile or existing is not None:
            if existing is None:
                raise NativeProfileIdentityMismatch(
                    "El perfil existente cambió durante el acceso. Reintenta el inicio de sesión."
                )
            return self._adopt_existing_profile(
                existing, email, password, distribution, email_hash, candidate
            )
        profile = self._create_auto_profile(distribution, email_hash, candidate)
        return (
            profile,
            candidate.session,
            candidate.subject,
            candidate.save,
            candidate.save_error,
            True,
        )

    def _adopt_existing_profile(
        self,
        existing: Profile,
        email: str,
        password: str,
        distribution: Distribution,
        email_hash: str,
        candidate: _Candidate,
    ) -> tuple[Profile, GatewaySession, str, dict[str, object] | None, str | None, bool]:
        """Reutiliza un perfil de la Fase 6.8 ya vinculado a la misma identidad.

        El índice de subject impide crear un segundo perfil para la misma
        cuenta. Si el par guardado sigue funcionando, se usa; si el portal
        devolvió un distro vigente distinto, se actualiza el par solo tras
        verificar el mismo subject.
        """

        if existing.distribution != distribution.id:
            raise NativeProfileIdentityMismatch(
                "El perfil existente pertenece a otra distribución."
            )
        if existing.email_hash is not None and existing.email_hash != email_hash:
            raise NativeProfileIdentityMismatch(
                "El perfil existente pertenece a otra cuenta."
            )
        if existing.distro_id == candidate.distro_id and existing.unique_id == candidate.unique_id:
            profile = self.store.bind(existing.id, candidate.subject, email_hash=email_hash)
            profile = self._apply_candidate_state(profile, candidate)
            return (
                profile, candidate.session, candidate.subject,
                candidate.save, candidate.save_error, False,
            )
        try:
            session, subject, save, save_error = self._login_known_profile(
                existing, email, password, distribution, email_hash
            )
            return self.store.profile(existing.id), session, subject, save, save_error, False
        except (NativeAuthRejected, NativeDistributionRejected, NativeIdentityMismatch):
            profile = self.store.update_installation(
                existing.id, candidate.distro_id, candidate.unique_id, candidate.subject
            )
            profile = self.store.bind(profile.id, candidate.subject, email_hash=email_hash)
            save, save_error = self._save_or_error(
                profile, candidate.session.token, candidate.subject
            )
            profile = self.store.profile(profile.id)
            return (
                profile, candidate.session, candidate.subject,
                save, save_error, False,
            )

    def _apply_candidate_state(self, profile: Profile, candidate: _Candidate) -> Profile:
        if candidate.retry_after is not None:
            profile = self.store.set_binding_wait(
                profile.id,
                int(self.now()) + candidate.retry_after,
                "native_device_binding_throttled",
            )
        elif candidate.save_error is not None:
            profile = self.store.set_save_error(profile.id, candidate.save_error)
        else:
            profile = self.store.clear_binding_wait(profile.id)
        return profile

    def _select_portal_candidate(
        self,
        email: str,
        password: str,
        distribution: Distribution,
        unique_id: str,
        players: tuple[PortalPlayer, ...],
    ) -> _Candidate:
        first: _Candidate | None = None
        mismatch = False
        for player in players[:8]:
            try:
                candidate = self._probe_candidate(
                    email,
                    password,
                    distribution,
                    distro_id=player.distro_id,
                    unique_id=unique_id,
                    portal_pid=player.pid,
                )
            except NativePortalIdentityMismatch:
                mismatch = True
                continue
            except NativeAuthRejected:
                raise
            except NativeDistributionRejected:
                continue
            if first is None:
                first = candidate
            if candidate.reuse_profile or candidate.save is not None:
                return candidate
            if candidate.save_error == "native_device_binding_throttled":
                return candidate
            if candidate.save_error not in (None, "native_no_cloud_save"):
                return candidate
        if first is None:
            if mismatch:
                raise NativePortalIdentityMismatch(
                    "El portal devolvió jugadores que no corresponden a la cuenta del gateway."
                )
            raise NativePortalUnavailable(
                "El portal no devolvió un jugador de Soul Knight utilizable."
            )
        return first

    def _probe_candidate(
        self,
        email: str,
        password: str,
        distribution: Distribution,
        *,
        distro_id: str,
        unique_id: str,
        portal_pid: int | None,
    ) -> _Candidate:
        session = self.client.authenticate(
            email,
            password,
            distribution=distribution,
            distro_id=distro_id,
            unique_id=unique_id,
        )
        if session.email.strip().casefold() != email.strip().casefold():
            raise NativeIdentityMismatch("El correo de la sesión no coincide con la cuenta solicitada.")
        if session.distro_id != distro_id:
            raise NativeIdentityMismatch("La sesión no corresponde al jugador del portal.")
        if portal_pid is not None and session.player_id != portal_pid:
            raise NativePortalIdentityMismatch(
                "El distro del portal no corresponde al jugador devuelto por el gateway."
            )
        subject = self.store.identity_subject(
            email=session.email, uid=session.uid, player_id=session.player_id
        )
        existing = self.store.profile_by_subject(subject)
        if existing is not None and existing.distribution == distribution.id:
            # Ya hay un perfil ligado a esta identidad (por ejemplo, uno de la
            # Fase 6.8). No se prueba el unique nuevo para no consumir otra
            # vinculación: se reutiliza el par guardado.
            return _Candidate(
                distro_id, unique_id, session, subject, None, None, reuse_profile=True
            )
        try:
            save = self._candidate_save(
                session.token, unique_id, distro_id, distribution, subject
            )
            return _Candidate(distro_id, unique_id, session, subject, save, None)
        except CloudProviderDeviceBindingThrottled as exc:
            return _Candidate(
                distro_id, unique_id, session, subject, None,
                "native_device_binding_throttled", exc.retry_after,
            )
        except CloudProviderUnauthenticated:
            raise NativeSessionRejected(
                "ChillyRoom rechazó la sesión emitida para el servicio de guardado."
            ) from None
        except CloudProviderUnavailable as exc:
            if getattr(exc, "provider_code", None) == 100504:
                return _Candidate(
                    distro_id, unique_id, session, subject, None, "native_no_cloud_save"
                )
            return _Candidate(distro_id, unique_id, session, subject, None, exc.code)
        except (NativeError, CloudSaveError) as exc:
            return _Candidate(distro_id, unique_id, session, subject, None, exc.code)

    def _candidate_save(
        self,
        token: str,
        unique_id: str,
        distro_id: str,
        distribution: Distribution,
        subject: str,
    ) -> dict[str, object]:
        provider = NativeSaveProvider(
            self.provider_factory(token, unique_id, distro_id),
            self.store,
            subject,
            distribution.id,
        )
        save = provider.download()
        gems = read_gems(save.payload)
        try:
            fish_snapshot = read_fish_chip(save.payload)
            fish_chip = fish_snapshot.fish_chip
            material_fish = fish_snapshot.material_fish
        except CloudSaveError:
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
        return {
            "verified": True,
            "bytes": save.metadata.size,
            "sha256": save.metadata.sha256,
            "gems": gems.gems,
            "fish_chip": fish_chip,
            "fish_chip_path": "gameData.fishChip",
            "material_fish": material_fish,
            "material_fish_path": "itemData.materials.material_fish",
            "cumulative_fish_count": cumulative_fish_count,
            "cumulative_fish_count_path": "itemData.cumulativeFishCount",
            "fish_chip_write_policy": "confirmed_by_owner",
            "character_write_policy": "confirmed_by_owner",
            "skill_write_policy": "confirmed_by_owner",
            "skin_write_policy": "confirmed_by_owner",
            "sections": None,
            "advanced": advanced,
            "remote_source": save.metadata.source,
        }

    def _create_auto_profile(
        self,
        distribution: Distribution,
        email_hash: str,
        candidate: _Candidate,
    ) -> Profile:
        try:
            profile = self.store.create_profile(
                label=self._auto_label(email_hash),
                distribution_id=distribution.id,
                distro_id=candidate.distro_id,
                unique_id=candidate.unique_id,
                allow_write=self.auto_allow_write,
                email_hash=email_hash,
                auto_generated=True,
            )
        except NativeProfileIdentityMismatch:
            raise NativeProfileIdentityMismatch(
                "Otra solicitud creó el perfil de esta cuenta al mismo tiempo. Reintenta el acceso."
            ) from None
        try:
            self.store.bind(profile.id, candidate.subject, email_hash=email_hash)
        except NativeError:
            self._discard_unbound_auto(profile.id)
            raise
        return self._apply_candidate_state(profile, candidate)

    @staticmethod
    def _auto_label(email_hash: str) -> str:
        return "Cuenta " + email_hash[:12]

    def _discard_unbound_auto(self, profile_id: str) -> None:
        try:
            profile = self.store.profile(profile_id)
        except NativeError:
            return
        if profile.subject is None and profile.auto_generated:
            try:
                self.store.delete_unbound_profile(profile_id)
            except (NativeError, OSError, ValueError):
                pass

    @staticmethod
    def _binding_message(seconds: int) -> str:
        seconds = max(60, int(seconds))
        hours, remainder = divmod(seconds, 3600)
        minutes = max(1, remainder // 60)
        if hours:
            wait = f"{hours} h {minutes} min"
        else:
            wait = f"{minutes} min"
        return (
            "ChillyRoom limita la vinculación de dispositivos nuevos para esta cuenta. "
            f"La identificación generada se conserva; vuelve a intentarlo en aproximadamente {wait}."
        )

    def _require_binding_ready(self, profile: Profile) -> None:
        until = profile.binding_wait_until
        if until is None:
            return
        remaining = until - int(self.now())
        if remaining > 0:
            raise NativeDeviceBindingThrottled(
                self._binding_message(remaining), retry_after=remaining
            )
        self.store.clear_binding_wait(profile.id)

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
        self._require_binding_ready(profile)
        provider = NativeSaveProvider(
            self.provider_factory(token, profile.unique_id, profile.distro_id),
            self.store,
            subject,
            profile.distribution,
        )
        try:
            save = provider.download()
        except CloudProviderDeviceBindingThrottled as exc:
            until = int(self.now()) + exc.retry_after
            self.store.set_binding_wait(profile.id, until, "native_device_binding_throttled")
            self._event("save_verify", "throttled", code="native_device_binding_throttled", subject=subject)
            raise NativeDeviceBindingThrottled(
                self._binding_message(exc.retry_after), retry_after=exc.retry_after
            ) from None
        except CloudProviderUnauthenticated:
            self.store.set_save_error(profile.id, "native_session_rejected")
            raise
        except CloudProviderUnavailable as exc:
            if getattr(exc, "provider_code", None) == 100504:
                self.store.set_save_error(profile.id, "native_no_cloud_save")
                raise NativeNoCloudSave(
                    "La cuenta no tiene una partida en la nube para este jugador. "
                    "No se creó ni se sobrescribió ninguna copia."
                ) from None
            self.store.set_save_error(profile.id, exc.code)
            raise
        except (NativeError, CloudSaveError):
            self.store.set_save_error(profile.id, "native_save_error")
            raise
        self.store.clear_binding_wait(profile.id)
        gems = read_gems(save.payload)
        try:
            fish_snapshot = read_fish_chip(save.payload)
            fish_chip = fish_snapshot.fish_chip
            material_fish = fish_snapshot.material_fish
        except CloudSaveError:
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
        self._event("save_verify", "ok", subject=subject)
        return {
            "verified": True,
            "bytes": save.metadata.size,
            "sha256": save.metadata.sha256,
            "gems": gems.gems,
            "fish_chip": fish_chip,
            "fish_chip_path": "gameData.fishChip",
            "material_fish": material_fish,
            "material_fish_path": "itemData.materials.material_fish",
            "cumulative_fish_count": cumulative_fish_count,
            "cumulative_fish_count_path": "itemData.cumulativeFishCount",
            "fish_chip_write_policy": "confirmed_by_owner",
            "character_write_policy": "confirmed_by_owner",
            "skill_write_policy": "confirmed_by_owner",
            "skin_write_policy": "confirmed_by_owner",
            "sections": None,
            "advanced": advanced,
            "remote_source": save.metadata.source,
        }

    def _lab(self, session: NativeSessionRecord) -> CloudLabService:
        if session.unique_id is None:
            raise NativeInstallationRequired(
                "Completa el identificador de instalación para acceder a la partida."
            )
        self._require_binding_ready(session.profile)
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
            LabBackupStore(self.backup_root / session.subject, cipher_key=self.backup_key),
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
        except CloudProviderDeviceBindingThrottled as exc:
            until = int(self.now()) + exc.retry_after
            self.store.set_binding_wait(
                session.profile.id, until, "native_device_binding_throttled"
            )
            self._event(
                "session", "throttled", code="native_device_binding_throttled", subject=session.subject
            )
            raise NativeDeviceBindingThrottled(
                self._binding_message(exc.retry_after), retry_after=exc.retry_after
            ) from None
        except CloudProviderUnavailable as exc:
            if getattr(exc, "provider_code", None) == 100504:
                self.store.set_save_error(session.profile.id, "native_no_cloud_save")
                raise NativeNoCloudSave(
                    "La cuenta no tiene una partida en la nube para este jugador."
                ) from None
            raise

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
            auto_identity=settings.native_auto_identity,
            auto_allow_write=settings.native_auto_allow_write,
            portal_client=(
                PortalClient()
                if settings.native_auto_identity and settings.native_portal_enabled
                else None
            ),
            backup_key=settings.native_backup_key_bytes(),
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
        store.cleanup()
        return NativeRuntime(service, None, True)
    except NativeError as exc:
        return NativeRuntime(None, exc, True)
    except (OSError, ValueError):
        return NativeRuntime(
            None,
            NativeMisconfigured("No se pudo inicializar el servicio de autenticación nativa."),
            True,
        )

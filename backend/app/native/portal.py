"""Cliente del portal oficial de cuentas de ChillyRoom (solo lectura).

El portal expone, para una cuenta autenticada, la lista de jugadores de Soul
Knight con ``registerDistroId`` y ``lastLoginDistroId``. La Fase 6.9 comprobó
que ese distro identifica al jugador que contiene la partida: usarlo en
``/UserAuth/Login`` devuelve el mismo ``player.id`` y BlobSave sirve la copia
con el identificador de instalación correcto.

El cliente no guarda la contraseña, la sesión del portal ni los identificadores.
No intenta resolver captchas ni eludir controles: si el portal pide un desafío o
rechaza el acceso, el servicio lo comunica y no reintenta.
"""

from __future__ import annotations

import hashlib
import http.client
import http.cookiejar
import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Callable
from uuid import UUID

from .errors import (
    NativeError,
    NativePortalChallengeRequired,
    NativePortalIdentityMismatch,
    NativePortalRejected,
    NativePortalUnavailable,
)

PORTAL_BASE = "https://accounts.chillyroom.com"
AUTH_PATH = "/.redwood/functions/auth"
CSRF_PATH = "/.redwood/functions/api/csrf-refresh"
GRAPHQL_PATH = "/.redwood/functions/graphql"
MAX_PORTAL_BYTES = 2_048_576
DEFAULT_TIMEOUT = 30.0
PROFILE_QUERY = """query Profile {
  getUserProfileByToken {
    accountInfo { userId email }
    gamesInfo {
      gameId
      players {
        pid
        gameId
        gameName
        registerDistroId
        lastLoginDistroId
      }
    }
  }
}"""
_UUID = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")


@dataclass(frozen=True)
class PortalPlayer:
    pid: int = field(repr=False)
    game_id: str
    game_name: str
    register_distro_id: str = field(repr=False)
    last_login_distro_id: str = field(repr=False)

    @property
    def distro_id(self) -> str:
        return self.last_login_distro_id or self.register_distro_id

    def public(self) -> dict[str, object]:
        return {
            "pid_sha256": hashlib.sha256(str(self.pid).encode()).hexdigest(),
            "game_id": self.game_id,
            "game_name": self.game_name,
            "distro_id_sha256": hashlib.sha256(self.distro_id.encode()).hexdigest(),
        }


@dataclass(frozen=True)
class PortalProfile:
    email: str = field(repr=False)
    players: tuple[PortalPlayer, ...]

    def soulknight_players(self) -> tuple[PortalPlayer, ...]:
        return tuple(
            player for player in self.players
            if player.game_id == "1" or "soulknight" in player.game_name.casefold()
        )


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        return None


def _uuid(value: object) -> str | None:
    if not isinstance(value, str) or not _UUID.fullmatch(value):
        return None
    try:
        UUID(value)
    except ValueError:
        return None
    return value


def _pid(value: object) -> int | None:
    if type(value) is int and value > 0:
        return value
    if isinstance(value, str) and value.isascii() and value.isdigit() and int(value) > 0:
        return int(value)
    return None


def parse_portal_profile(document: object, expected_email: str) -> PortalProfile:
    """Valida la respuesta GraphQL y extrae solo los jugadores de Soul Knight."""

    if not isinstance(document, dict):
        raise NativePortalUnavailable("El portal devolvió una respuesta no válida.")
    data = document.get("data")
    if not isinstance(data, dict):
        raise NativePortalUnavailable("El portal no devolvió el perfil solicitado.")
    profile = data.get("getUserProfileByToken")
    if not isinstance(profile, dict):
        raise NativePortalUnavailable("El portal no devolvió el perfil solicitado.")
    account = profile.get("accountInfo")
    if not isinstance(account, dict):
        raise NativePortalUnavailable("El portal no devolvió la identidad de la cuenta.")
    email = account.get("email")
    if isinstance(email, str) and email.strip() and email.strip().casefold() != expected_email.strip().casefold():
        raise NativePortalIdentityMismatch("El portal devolvió una cuenta distinta de la solicitada.")
    games = profile.get("gamesInfo")
    players: list[PortalPlayer] = []
    seen: set[str] = set()
    if isinstance(games, list):
        for game in games:
            if not isinstance(game, dict):
                continue
            entries = game.get("players")
            if not isinstance(entries, list):
                continue
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                pid = _pid(entry.get("pid"))
                game_id = entry.get("gameId")
                game_name = entry.get("gameName")
                register = _uuid(entry.get("registerDistroId"))
                last = _uuid(entry.get("lastLoginDistroId"))
                distro = last or register
                if pid is None or distro is None or distro in seen:
                    continue
                seen.add(distro)
                players.append(
                    PortalPlayer(
                        pid=pid,
                        game_id=str(game_id) if game_id is not None else "",
                        game_name=str(game_name) if game_name is not None else "",
                        register_distro_id=register or "",
                        last_login_distro_id=last or "",
                    )
                )
    return PortalProfile(email=expected_email, players=tuple(players))


class PortalClient:
    """Sesión de portal efímera; no persiste cookies ni credenciales."""

    def __init__(
        self,
        *,
        base_url: str = PORTAL_BASE,
        timeout: float = DEFAULT_TIMEOUT,
        fetch: Callable[[str, str, dict[str, str], bytes | None], tuple[int, dict[str, str], bytes]] | None = None,
    ) -> None:
        if not isinstance(base_url, str) or not base_url.startswith("https://"):
            raise ValueError("El portal debe usar HTTPS.")
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not 0 < timeout <= 60:
            raise ValueError("Tiempo de espera del portal inválido.")
        self.base_url = base_url.rstrip("/")
        self.timeout = float(timeout)
        self._fetch = fetch or self._urllib_fetch
        self._jar = http.cookiejar.CookieJar()
        self._manual_cookies: dict[str, str] = {}
        self._opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({}),
            urllib.request.HTTPCookieProcessor(self._jar),
            _NoRedirect(),
        )

    def _urllib_fetch(
        self, method: str, url: str, headers: dict[str, str], body: bytes | None
    ) -> tuple[int, dict[str, str], bytes]:
        request = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            response = self._opener.open(request, timeout=self.timeout)
        except urllib.error.HTTPError as exc:
            response = exc
        except (urllib.error.URLError, TimeoutError, OSError, http.client.HTTPException):
            raise NativePortalUnavailable("No se pudo contactar con el portal de cuentas.") from None
        with response:
            raw = response.read(MAX_PORTAL_BYTES + 1)
            if len(raw) > MAX_PORTAL_BYTES:
                raise NativePortalUnavailable("La respuesta del portal supera el límite.")
            return response.status, dict(response.headers), raw

    def _cookie(self, name: str) -> str:
        for cookie in self._jar:
            if cookie.name == name:
                return cookie.value
        return self._manual_cookies.get(name, "")

    def _remember_cookies(self, headers: dict[str, str]) -> None:
        """Guarda cookies de un transporte inyectado (pruebas sin red)."""

        value = headers.get("Set-Cookie") or headers.get("set-cookie")
        if not isinstance(value, str):
            return
        for part in value.split(","):
            name, separator, remainder = part.strip().partition("=")
            if not separator or not name:
                continue
            token = remainder.split(";", 1)[0].strip()
            if token:
                self._manual_cookies[name] = token

    def _request(
        self,
        method: str,
        path: str,
        *,
        body: object | None = None,
        headers: dict[str, str] | None = None,
        csrf: str = "",
    ) -> tuple[int, bytes]:
        base_headers = {
            "Accept": "application/json",
            "User-Agent": "SK-Under/phase6-9 read-only portal",
            "Origin": self.base_url,
            "Referer": self.base_url + "/",
        }
        if body is not None:
            base_headers["Content-Type"] = "application/json"
        if csrf:
            base_headers["x-csrf-token"] = csrf
        if headers:
            base_headers.update(headers)
        payload = (
            json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            if body is not None else None
        )
        try:
            status, response_headers, raw = self._fetch(
                method, self.base_url + path, base_headers, payload
            )
            if isinstance(response_headers, dict):
                self._remember_cookies(response_headers)
        except NativeError:
            raise
        except (OSError, urllib.error.URLError, http.client.HTTPException, TimeoutError):
            raise NativePortalUnavailable("No se pudo contactar con el portal de cuentas.") from None
        return status, raw

    def profile(self, email: str, password: str) -> PortalProfile:
        """Autentica en el portal y devuelve los jugadores de la cuenta.

        La contraseña y la sesión del portal viven solo en esta llamada. No se
        reintenta ni se resuelven captchas.
        """

        if not isinstance(email, str) or not isinstance(password, str) or not email.strip() or not password:
            raise NativePortalRejected("Faltan las credenciales de la cuenta.")
        try:
            self._request("GET", "/login")
            status, _ = self._request(
                "POST",
                AUTH_PATH,
                body={"account": email.strip(), "password": password, "type": 3, "method": "login"},
            )
            if status in (401, 403):
                raise NativePortalChallengeRequired(
                    "El portal de ChillyRoom pidió una verificación adicional. "
                    "Inicia sesión manualmente en el portal y vuelve a intentarlo."
                )
            if status == 429:
                raise NativePortalChallengeRequired(
                    "El portal de ChillyRoom limitó temporalmente los intentos. Espera antes de reintentar."
                )
            if status != 200:
                raise NativePortalRejected(
                    "El portal de ChillyRoom rechazó las credenciales de la cuenta."
                )
            if not self._cookie("session"):
                raise NativePortalUnavailable("El portal no emitió una sesión utilizable.")
            self._request("POST", CSRF_PATH, body={})
            csrf = self._cookie("csrf-token")
            if not csrf:
                raise NativePortalUnavailable("El portal no emitió el token de protección de la solicitud.")
            status, raw = self._request(
                "POST",
                GRAPHQL_PATH,
                body={"operationName": "Profile", "variables": {}, "query": PROFILE_QUERY},
                headers={
                    "Apollo-Require-Preflight": "1",
                    "auth-provider": "chillyRoomAuth",
                    "Authorization": "Bearer " + self._cookie("session"),
                },
                csrf=csrf,
            )
            if status == 429:
                raise NativePortalChallengeRequired(
                    "El portal limitó temporalmente las consultas. Espera antes de reintentar."
                )
            if status != 200:
                raise NativePortalUnavailable(
                    "El portal no pudo devolver el perfil de la cuenta en este intento."
                )
            try:
                document = json.loads(raw)
            except (ValueError, UnicodeDecodeError, RecursionError):
                raise NativePortalUnavailable("El portal devolvió una respuesta no válida.") from None
            if isinstance(document, dict) and document.get("errors"):
                raise NativePortalUnavailable("El portal no autorizó la consulta del perfil.")
            return parse_portal_profile(document, email)
        finally:
            self._jar.clear()
            self._manual_cookies.clear()

"""Cliente de autenticación nativa de ChillyRoom para Soul Knight 8.8.0.

Reproduce el contrato verificado en la Fase 6.7: ``POST /UserAuth/Login`` con
JSON plano, cabeceras de juego y la cabecera obligatoria ``x-distro-id``. No
reintenta, no sigue redirecciones, no desactiva TLS y no usa proxies del
entorno. La contraseña solo vive en memoria durante la petición.

El transporte es inyectable para que las pruebas no toquen la red.
"""

from __future__ import annotations

import http.client
import json
import re
import time
import urllib.error
import urllib.request
import zlib
from collections.abc import Callable
from dataclasses import dataclass, field
from hashlib import sha256

from .distributions import Distribution
from .errors import NativeError

LOGIN_URL = "https://api-gateway.soulknight.chillyroom.com/UserAuth/Login"
MAX_RESPONSE_BYTES = 1_048_576
DEFAULT_TIMEOUT = 30.0
USER_AGENT = (
    "Dalvik/2.1.0 (Linux; U; Android 11; sdk_gphone_x86_64 "
    "Build/RSR1.240422.006)"
)
_DISTRO = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_EMAIL = re.compile(r"^[^@\s]{1,128}@[^@\s.]{1,190}(?:\.[^@\s.]{1,63})+$")

type Transport = Callable[[str, bytes, dict[str, str], float], tuple[int, str, bytes]]


class NativeAuthRejected(NativeError):
    code = "native_credentials_rejected"
    status = 401

    def __init__(self, status: int, provider_code: object = None) -> None:
        # El cuerpo remoto no se conserva ni se muestra: puede contener datos.
        super().__init__(
            "El proveedor rechazó el inicio de sesión. Revisa las credenciales; "
            "no se reintenta automáticamente."
        )
        self.provider_status = status
        self.provider_code = provider_code if type(provider_code) is int else None


class NativeDistributionRejected(NativeError):
    code = "native_distribution_rejected"
    status = 502


class NativeProviderThrottled(NativeError):
    code = "native_auth_throttled"
    status = 429

    def __init__(self) -> None:
        super().__init__(
            "El proveedor limitó temporalmente los intentos. Espera antes de volver a intentarlo."
        )
        self.retry_after = 60


class NativeAuthUnavailable(NativeError):
    code = "native_auth_unavailable"
    status = 502


class NativeAuthProtocol(NativeError):
    code = "native_auth_protocol"
    status = 502


@dataclass(frozen=True)
class GatewaySession:
    """Sesión emitida por el gateway; ``repr`` oculta los secretos."""

    token: str = field(repr=False)
    uid: int
    email: str = field(repr=False)
    player_id: int
    expire: int
    distro_id: str = field(repr=False)
    legacy_host: str | None = field(default=None, repr=False)
    legacy_token: str | None = field(default=None, repr=False)

    def is_valid(self, *, now: float | None = None) -> bool:
        return self.expire > int(now if now is not None else time.time())

    def summary(self) -> dict[str, object]:
        return {
            "uid_sha256": sha256(str(self.uid).encode()).hexdigest(),
            "player_id_sha256": sha256(str(self.player_id).encode()).hexdigest(),
            "email_sha256": sha256(self.email.casefold().encode()).hexdigest(),
            "token_sha256": sha256(self.token.encode()).hexdigest(),
            "distro_id_sha256": sha256(self.distro_id.encode()).hexdigest(),
            "expire": self.expire,
            "has_legacy_token": bool(self.legacy_token),
        }


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        return None


def urllib_transport(url: str, body: bytes, headers: dict[str, str], timeout: float) -> tuple[int, str, bytes]:
    """Transporte HTTPS con TLS normal, sin proxies del entorno ni redirecciones."""
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({}),
        _NoRedirect(),
    )
    try:
        response = opener.open(request, timeout=timeout)
    except urllib.error.HTTPError as exc:
        response = exc
    except (urllib.error.URLError, TimeoutError, OSError, http.client.HTTPException):
        raise NativeAuthUnavailable("No se pudo contactar con el servicio de autenticación.") from None

    with response:
        try:
            raw = response.read(MAX_RESPONSE_BYTES + 1)
        except http.client.IncompleteRead:
            raise NativeAuthProtocol("La respuesta de autenticación está incompleta.") from None
        if len(raw) > MAX_RESPONSE_BYTES:
            raise NativeAuthProtocol("La respuesta de autenticación supera el límite.")
        length = response.headers.get("Content-Length")
        if length is not None:
            try:
                expected = int(length)
            except ValueError:
                raise NativeAuthProtocol("La respuesta de autenticación tiene una longitud inválida.") from None
            if expected < 0 or expected != len(raw):
                raise NativeAuthProtocol("La respuesta de autenticación está incompleta.")
        return response.status, response.headers.get("Content-Encoding", ""), raw


def decode_response(raw: bytes, encoding: str) -> bytes:
    if len(raw) > MAX_RESPONSE_BYTES:
        raise NativeAuthProtocol("La respuesta de autenticación supera el límite.")
    value = encoding.strip().lower()
    if value in ("", "identity"):
        return raw
    if value != "gzip":
        raise NativeAuthProtocol("El servicio devolvió una codificación desconocida.")
    decoder = zlib.decompressobj(16 + zlib.MAX_WBITS)
    try:
        result = decoder.decompress(raw, MAX_RESPONSE_BYTES + 1)
    except zlib.error:
        raise NativeAuthProtocol("La respuesta gzip del servicio está corrupta.") from None
    if len(result) > MAX_RESPONSE_BYTES:
        raise NativeAuthProtocol("La respuesta descomprimida supera el límite.")
    if not decoder.eof or decoder.unused_data:
        raise NativeAuthProtocol("La respuesta gzip está incompleta o tiene bytes adicionales.")
    return result


def _as_int(value: object, name: str) -> int:
    if type(value) is int:
        return value
    if isinstance(value, str) and value.isascii() and value.isdigit():
        return int(value)
    raise NativeAuthProtocol(f"La respuesta no contiene {name} válido.")


def _as_text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise NativeAuthProtocol(f"La respuesta no contiene {name} válido.")
    return value


def build_login_headers(distribution: Distribution, unique_id: str | None = None) -> dict[str, str]:
    """Cabeceras observadas para Android Global 8.8.0.

    La Fase 6.7 comprobó que ``x-unique-id`` no es obligatoria para el login;
    el cliente oficial la envía. La Fase 6.9 la incluye cuando el perfil ya
    tiene una identificación generada, porque el servicio de guardado vincula
    ese código a la cuenta. ``x-distro-id`` sigue siendo obligatoria.
    """
    if not distribution.enabled or not distribution.validated or distribution.platform is None:
        from .errors import NativeDistributionDisabled

        raise NativeDistributionDisabled("La distribución no está validada.")
    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
        "User-Agent": USER_AGENT,
        "x-game-id": "1",
        "x-game": "Soulknight",
        "x-app-version": distribution.protocol_app_version,
        "x-game-version": distribution.protocol_game_version,
        "x-platform": distribution.platform,
        "x-game-lang": "en",
        "x-locale": "en_US",
    }
    if unique_id is not None:
        if not isinstance(unique_id, str) or not unique_id or len(unique_id) > 512 or any(
            not 33 <= ord(char) <= 126 for char in unique_id
        ):
            from .errors import NativeInstallationInvalid

            raise NativeInstallationInvalid("El identificador de instalación no es válido.")
        headers["x-unique-id"] = unique_id
    return headers


def build_login_body(email: str, password: str) -> bytes:
    if not isinstance(email, str) or not _EMAIL.fullmatch(email.strip()):
        raise NativeAuthRejected(0)
    if not isinstance(password, str) or not password or len(password) > 1024:
        raise NativeAuthRejected(0)
    try:
        return json.dumps(
            {
                "loginType": 3,
                "account": email.strip(),
                "password": password,
                "credential": None,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
    except UnicodeEncodeError:
        raise NativeAuthRejected(0) from None


class NativeAuthClient:
    """Cliente mínimo, sin reintentos y con validación de identidad."""

    def __init__(
        self,
        *,
        timeout: float = DEFAULT_TIMEOUT,
        transport: Transport = urllib_transport,
        now: Callable[[], float] = time.time,
    ) -> None:
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not 0 < timeout <= 60:
            raise ValueError("Tiempo de espera fuera del rango permitido.")
        self.timeout = float(timeout)
        self.transport = transport
        self.now = now

    def authenticate(
        self,
        email: str,
        password: str,
        *,
        distribution: Distribution,
        distro_id: str,
        unique_id: str | None = None,
    ) -> GatewaySession:
        if not isinstance(distro_id, str) or not _DISTRO.fullmatch(distro_id):
            raise NativeDistributionRejected("El identificador de distribución no tiene un formato válido.")
        body = build_login_body(email, password)
        headers = build_login_headers(distribution, unique_id) | {"x-distro-id": distro_id}

        try:
            status, encoding, raw = self.transport(LOGIN_URL, body, headers, self.timeout)
        except NativeError:
            raise
        except (OSError, urllib.error.URLError, http.client.HTTPException, TimeoutError):
            raise NativeAuthUnavailable("No se pudo contactar con el servicio de autenticación.") from None

        if len(raw) > MAX_RESPONSE_BYTES:
            raise NativeAuthProtocol("La respuesta de autenticación supera el límite.")
        document = decode_response(raw, encoding)

        if status == 429:
            raise NativeProviderThrottled()
        if status != 200:
            provider_code = _provider_error_code(document)
            if provider_code == 10003:
                raise NativeDistributionRejected(
                    "El proveedor rechazó la distribución aprovisionada. Revisa el perfil de instalación."
                )
            if status >= 500:
                raise NativeAuthUnavailable("El servicio de autenticación no está disponible.")
            raise NativeAuthRejected(status, provider_code)

        try:
            payload = json.loads(document)
        except (ValueError, UnicodeDecodeError, RecursionError):
            raise NativeAuthProtocol("La respuesta de autenticación no contiene JSON válido.") from None
        if not isinstance(payload, dict):
            raise NativeAuthProtocol("La respuesta de autenticación no es un objeto JSON.")

        session = payload.get("session")
        user = payload.get("user")
        player = payload.get("player")
        if not isinstance(session, dict) or not isinstance(user, dict) or not isinstance(player, dict):
            raise NativeAuthProtocol("La respuesta de autenticación no contiene session, user y player.")

        token = _as_text(session.get("token"), "session.token")
        uid = _as_int(session.get("uid"), "session.uid")
        expire = _as_int(session.get("expire"), "session.expire")
        user_id = _as_int(user.get("id"), "user.id")
        email_value = _as_text(user.get("email"), "user.email")
        player_id = _as_int(player.get("id"), "player.id")

        from .errors import NativeIdentityMismatch

        if uid != user_id:
            raise NativeIdentityMismatch("La sesión no corresponde al usuario autenticado.")
        if email_value.strip().casefold() != email.strip().casefold():
            raise NativeIdentityMismatch("El correo de la respuesta no coincide con la cuenta solicitada.")
        if player_id <= 0:
            raise NativeIdentityMismatch("El proveedor no devolvió un jugador válido.")
        if expire <= int(self.now()):
            raise NativeIdentityMismatch("La sesión emitida ya está caducada.")

        legacy = payload.get("legacyGateway")
        legacy_host = legacy_token = None
        if isinstance(legacy, dict):
            host = legacy.get("host")
            token_value = legacy.get("token")
            if isinstance(host, str) and host:
                legacy_host = host
            if isinstance(token_value, str) and token_value:
                legacy_token = token_value

        return GatewaySession(
            token=token,
            uid=uid,
            email=email_value,
            player_id=player_id,
            expire=expire,
            distro_id=distro_id,
            legacy_host=legacy_host,
            legacy_token=legacy_token,
        )


def _provider_error_code(document: bytes) -> object:
    try:
        payload = json.loads(document)
    except (ValueError, UnicodeDecodeError, RecursionError):
        return None
    if not isinstance(payload, dict):
        return None
    for key in ("errorCode", "error", "code"):
        value = payload.get(key)
        if type(value) is int:
            return value
    return None

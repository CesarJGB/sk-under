"""Cliente Linux experimental para el login de ChillyRoom en Soul Knight.

El contrato se obtuvo de una observación autorizada del cliente oficial
Android Global 8.8.0 y de una prueba real desde Linux. La pieza que faltaba
en las fases anteriores era la cabecera ``x-distro-id``: sin ella el gateway
responde ``502`` con ``errorCode=10003``. El cuerpo es JSON plano; el gateway
rechaza un cuerpo gzip con ``400 Input validation failed``.

Este módulo no guarda contraseñas, no persiste tokens por defecto y no
desactiva la verificación TLS. Tampoco implementa reintentos: el proveedor
aplica un control de frecuencia al login.
"""

from __future__ import annotations

import gzip
import hashlib
import http.client
import json
import re
import time
import urllib.error
import urllib.request
import zlib
from dataclasses import dataclass, field
from typing import Any

LOGIN_URL = "https://api-gateway.soulknight.chillyroom.com/UserAuth/Login"
MAX_RESPONSE_BYTES = 1_048_576
DEFAULT_TIMEOUT = 30.0
USER_AGENT = (
    "Dalvik/2.1.0 (Linux; U; Android 11; sdk_gphone_x86_64 "
    "Build/RSR1.240422.006)"
)
_DISTRO_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


class NativeAuthError(Exception):
    """Error base del cliente experimental."""


class AuthTransportError(NativeAuthError):
    """No se pudo completar el transporte HTTPS."""


class AuthRejected(NativeAuthError):
    """El gateway rechazó la solicitud; no se conserva el cuerpo remoto."""

    def __init__(self, status: int, code: object = None, message: str = "") -> None:
        self.status = status
        self.code = code
        self.message = message
        super().__init__(f"El gateway rechazó el login (HTTP {status}).")


class AuthProtocolError(NativeAuthError):
    """La respuesta no cumple el contrato observado."""


class AuthIdentityError(NativeAuthError):
    """La respuesta no permite vincular la sesión con la cuenta solicitada."""


@dataclass(frozen=True)
class Session:
    """Sesión emitida por el gateway; los secretos no aparecen en repr."""

    token: str = field(repr=False)
    uid: int
    email: str = field(repr=False)
    player_id: int
    expire: int
    distro_id: str
    legacy_host: str | None = None
    legacy_token: str | None = field(default=None, repr=False)

    def is_valid(self, *, now: float | None = None) -> bool:
        return self.expire > int(now if now is not None else time.time())

    def summary(self) -> dict[str, object]:
        """Resumen apto para registros: sin token, correo ni UID en claro."""

        return {
            "uid_sha256": hashlib.sha256(str(self.uid).encode()).hexdigest(),
            "player_id_sha256": hashlib.sha256(str(self.player_id).encode()).hexdigest(),
            "email_sha256": hashlib.sha256(self.email.casefold().encode()).hexdigest(),
            "token_sha256": hashlib.sha256(self.token.encode()).hexdigest(),
            "expire": self.expire,
            "expire_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(self.expire)),
            "distro_id_sha256": hashlib.sha256(self.distro_id.encode()).hexdigest(),
            "has_legacy_token": bool(self.legacy_token),
        }


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        return None


def _decode_response(raw: bytes, encoding: str) -> bytes:
    if len(raw) > MAX_RESPONSE_BYTES:
        raise AuthProtocolError("La respuesta supera el límite permitido.")
    value = encoding.strip().lower()
    if value in ("", "identity"):
        return raw
    if value != "gzip":
        raise AuthProtocolError("Codificación de respuesta desconocida.")
    decoder = zlib.decompressobj(16 + zlib.MAX_WBITS)
    try:
        result = decoder.decompress(raw, MAX_RESPONSE_BYTES + 1)
    except zlib.error:
        raise AuthProtocolError("Respuesta gzip corrupta.") from None
    if len(result) > MAX_RESPONSE_BYTES:
        raise AuthProtocolError("La respuesta descomprimida supera el límite.")
    if not decoder.eof or decoder.unused_data:
        raise AuthProtocolError("Respuesta gzip incompleta o con datos adicionales.")
    return result


def _as_int(value: object, field_name: str) -> int:
    if type(value) is int:
        return value
    if isinstance(value, str) and value.isascii() and value.isdigit():
        return int(value)
    raise AuthProtocolError(f"El campo {field_name} no es un entero válido.")


def _as_text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value:
        raise AuthProtocolError(f"El campo {field_name} no es texto válido.")
    return value


def build_login_headers(distro_id: str) -> dict[str, str]:
    """Cabeceras observadas en el login real de Android Global 8.8.0.

    ``x-distro-id`` es obligatoria. El cliente oficial también envía
    ``x-unique-id``, pero la prueba sin esa cabecera devolvió ``200``.
    """

    if not isinstance(distro_id, str) or not _DISTRO_RE.fullmatch(distro_id):
        raise AuthProtocolError("El identificador de distribución no es válido.")
    return {
        "Content-Type": "application/json; charset=utf-8",
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
        "User-Agent": USER_AGENT,
        "x-game-id": "1",
        "x-game": "Soulknight",
        "x-app-version": "8.8.0",
        "x-game-version": "8.8.0",
        "x-platform": "android",
        "x-game-lang": "en",
        "x-locale": "en_US",
        "x-distro-id": distro_id,
    }


def build_login_body(email: str, password: str) -> bytes:
    if not isinstance(email, str) or not email.strip():
        raise NativeAuthError("Falta el correo.")
    if not isinstance(password, str) or not password:
        raise NativeAuthError("Falta la contraseña.")
    return json.dumps(
        {
            "loginType": 3,
            "account": email,
            "password": password,
            "credential": None,
        },
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")


def authenticate(
    email: str,
    password: str,
    *,
    distro_id: str,
    timeout: float = DEFAULT_TIMEOUT,
    url: str = LOGIN_URL,
) -> Session:
    """Autentica una cuenta y devuelve una sesión nueva.

    La contraseña solo se usa para construir el cuerpo en memoria. No se
    registra, no se escribe en disco y no se incluye en ``repr``.
    """

    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)):
        raise NativeAuthError("Tiempo de espera inválido.")
    if not 0 < timeout <= 60:
        raise NativeAuthError("Tiempo de espera fuera del rango permitido.")
    body = build_login_body(email, password)
    headers = build_login_headers(distro_id)
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        response = urllib.request.build_opener(_NoRedirect()).open(request, timeout=timeout)
    except urllib.error.HTTPError as exc:
        response = exc
    except (urllib.error.URLError, TimeoutError, OSError, http.client.HTTPException):
        raise AuthTransportError("No se pudo contactar con el gateway.") from None

    with response:
        try:
            raw = response.read(MAX_RESPONSE_BYTES + 1)
        except http.client.IncompleteRead:
            raise AuthProtocolError("Respuesta HTTP incompleta.") from None
        if len(raw) > MAX_RESPONSE_BYTES:
            raise AuthProtocolError("La respuesta supera el límite permitido.")
        length = response.headers.get("Content-Length")
        if length is not None:
            try:
                expected = int(length)
            except ValueError:
                raise AuthProtocolError("Longitud HTTP inválida.") from None
            if expected < 0 or expected != len(raw):
                raise AuthProtocolError("Respuesta HTTP incompleta.")
        document = _decode_response(raw, response.headers.get("Content-Encoding", ""))

    if response.status != 200:
        code = None
        message = ""
        try:
            error_doc = json.loads(document)
        except (ValueError, UnicodeDecodeError):
            error_doc = None
        if isinstance(error_doc, dict):
            code = error_doc.get("errorCode", error_doc.get("code"))
            candidate = error_doc.get("message", error_doc.get("msg"))
            if isinstance(candidate, str):
                message = candidate[:120]
        raise AuthRejected(response.status, code, message)

    try:
        payload = json.loads(document)
    except (ValueError, UnicodeDecodeError, RecursionError):
        raise AuthProtocolError("La respuesta no contiene JSON válido.") from None
    if not isinstance(payload, dict):
        raise AuthProtocolError("La respuesta no es un objeto JSON.")

    session = payload.get("session")
    user = payload.get("user")
    player = payload.get("player")
    if not isinstance(session, dict) or not isinstance(user, dict) or not isinstance(player, dict):
        raise AuthProtocolError("La respuesta no contiene session, user y player.")

    token = _as_text(session.get("token"), "session.token")
    uid = _as_int(session.get("uid"), "session.uid")
    expire = _as_int(session.get("expire"), "session.expire")
    user_id = _as_int(user.get("id"), "user.id")
    email_value = _as_text(user.get("email"), "user.email")
    player_id = _as_int(player.get("id"), "player.id")

    if uid != user_id:
        raise AuthIdentityError("session.uid no coincide con user.id.")
    if email_value.casefold() != email.casefold():
        raise AuthIdentityError("El correo de la respuesta no coincide.")
    if expire <= int(time.time()):
        raise AuthIdentityError("La sesión recibida ya está caducada.")

    legacy = payload.get("legacyGateway")
    legacy_host = legacy_token = None
    if isinstance(legacy, dict):
        host = legacy.get("host")
        token_value = legacy.get("token")
        if isinstance(host, str) and host:
            legacy_host = host
        if isinstance(token_value, str) and token_value:
            legacy_token = token_value

    return Session(
        token=token,
        uid=uid,
        email=email_value,
        player_id=player_id,
        expire=expire,
        distro_id=distro_id,
        legacy_host=legacy_host,
        legacy_token=legacy_token,
    )

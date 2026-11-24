"""API privada de autenticación nativa y editor de gemas por sesión.

La cookie de sesión es ``HttpOnly``, ``SameSite=Strict`` y ``Secure`` en HTTPS.
Las operaciones POST exigen el origen exacto, JSON sin compresión y un cuerpo
limitado. Ninguna ruta acepta un identificador de cuenta desde el navegador:
la sesión se resuelve siempre a partir de la cookie del titular.
"""

from __future__ import annotations

import logging
import sqlite3
from hmac import compare_digest
from time import time
from typing import Annotated

from fastapi import APIRouter, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from pydantic import BaseModel, ConfigDict, StringConstraints, field_validator

from ..cloud.fish_chip_editor import MAX_FISH_CHIP, MIN_FISH_CHIP
from ..cloud.gems_editor import MAX_GEMS, MIN_GEMS
from ..cloud_save import CloudSaveError
from ..errors import PRIVATE_HEADERS, EditorError
from ..models import (
    CloudLabConfirmInput,
    CloudLabFishChipPrepareInput,
    CloudLabPrepareInput,
    CloudLabRestoreInput,
    CloudLabVerifyInput,
)
from ..net import client_ip
from ..native.distributions import DISTRIBUTIONS
from ..native.errors import (
    NativeDisabled,
    NativeError,
    NativeMisconfigured,
    NativeOriginDenied,
)
from ..native.service import NativeAuthService
from .cloud_lab import _http_error
from .uploads import BoundedJSONRequest

logger = logging.getLogger(__name__)
JSON_LIMIT = 8192

router = APIRouter(prefix="/api/v1/cloud/native", tags=["Autenticación nativa"])


def _runtime(request: Request) -> tuple[NativeAuthService | None, NativeError | None, bool]:
    return (
        getattr(request.app.state, "native_service", None),
        getattr(request.app.state, "native_problem", None),
        bool(getattr(request.app.state, "native_enabled", False)),
    )


def _require_service(request: Request) -> NativeAuthService:
    service, problem, enabled = _runtime(request)
    if service is not None:
        return service
    if problem is not None:
        raise problem
    if not enabled:
        raise NativeDisabled(
            "La autenticación nativa está deshabilitada en este servidor. "
            "El propietario debe habilitarla en el entorno privado."
        )
    raise NativeMisconfigured("El servicio de autenticación nativa no está configurado.")


def _cookie(request: Request, service: NativeAuthService | None = None) -> str:
    if service is None:
        service, _, _ = _runtime(request)
    name = service.cookie_name if service else "__Host-sk_native"
    return request.cookies.get(name, "")


class NativeRoute(APIRoute):
    def get_route_handler(self):
        handle = super().get_route_handler()

        async def guarded(request: Request) -> Response:
            settings = request.app.state.settings
            service, _, _ = _runtime(request)
            try:
                origin = request.headers.get("origin")
                expected = service.origin if service else None
                if expected is not None:
                    if origin is not None and origin != expected:
                        raise NativeOriginDenied("El origen de la solicitud no está autorizado.")
                    if request.method not in {"GET", "HEAD"} and origin != expected:
                        raise NativeOriginDenied("El origen de la solicitud no está autorizado.")
                elif request.method not in {"GET", "HEAD"}:
                    if origin is None or origin not in settings.allowed_origins:
                        raise NativeOriginDenied("El origen de la solicitud no está autorizado.")
                fetch_site = request.headers.get("sec-fetch-site")
                if fetch_site is not None and fetch_site not in {"same-origin", "same-site", "none"}:
                    raise NativeOriginDenied("La solicitud no proviene del editor autorizado.")
                if request.method == "POST":
                    content_type = request.headers.get("content-type", "").partition(";")[0].strip().lower()
                    encoding = request.headers.get("content-encoding", "identity").lower()
                    if content_type != "application/json" or encoding != "identity":
                        raise EditorError(415, "invalid_content_type", "Envía JSON UTF-8 sin compresión.")
                    request = BoundedJSONRequest(request, JSON_LIMIT)
                response = await handle(request)
            except NativeError as exc:
                headers = {}
                retry_after = getattr(exc, "retry_after", None)
                if isinstance(retry_after, int) and retry_after > 0:
                    headers["Retry-After"] = str(retry_after)
                raise EditorError(exc.status, exc.code, str(exc), headers=headers) from None
            except CloudSaveError as exc:
                raise _http_error(exc) from None
            except (OSError, sqlite3.Error) as exc:
                logger.warning("Native store error in %s (%s)", self.name, type(exc).__name__)
                raise EditorError(
                    503, "native_store_unavailable", "El almacén privado de sesiones no está disponible."
                ) from None
            except (EditorError, RequestValidationError):
                raise
            except Exception as exc:
                logger.error("Native auth error in %s (%s)", self.name, type(exc).__name__)
                raise EditorError(
                    500, "native_error", "No se pudo completar la operación de autenticación nativa."
                ) from None
            response.headers.update(PRIVATE_HEADERS)
            return response

        return guarded


router.route_class = NativeRoute

Email = Annotated[str, StringConstraints(min_length=3, max_length=254, strip_whitespace=True)]
Password = Annotated[str, StringConstraints(min_length=1, max_length=1024)]
DistributionId = Annotated[str, StringConstraints(min_length=1, max_length=64)]
ProfileId = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{32}$")]
UniqueId = Annotated[str, StringConstraints(min_length=1, max_length=512, pattern=r"^[!-~]+$")]


class LoginInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    distribution: DistributionId
    email: Email
    password: Password
    profile_id: ProfileId | None = None

    @field_validator("email")
    @classmethod
    def valid_email(cls, value: str) -> str:
        local, _, domain = value.partition("@")
        if (
            not local
            or not domain
            or "." not in domain
            or any(char.isspace() or ord(char) < 33 for char in value)
        ):
            raise ValueError("El correo no tiene un formato válido.")
        return value


class InstallationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    unique_id: UniqueId


class PrepareInput(CloudLabPrepareInput):
    source_sha256: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$", min_length=64, max_length=64)]


class FishChipPrepareInput(CloudLabFishChipPrepareInput):
    source_sha256: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$", min_length=64, max_length=64)]


def _disabled_config(settings) -> dict[str, object]:
    origin = settings.native_origin or settings.cloud_accounts_origin
    return {
        "available": False,
        "enabled": False,
        "configured": False,
        "native_auth_ready": False,
        "write_enabled": settings.native_write_enabled,
        "secure": origin.startswith("https://"),
        "min_gems": MIN_GEMS,
        "max_gems": MAX_GEMS,
        "min_fish_chip": MIN_FISH_CHIP,
        "max_fish_chip": MAX_FISH_CHIP,
        "fish_chip_write_policy": "experimental",
        "login_available": False,
        "auto_identity": False,
        "requires_profile_selection": False,
        "profiles": [],
        "distributions": [distribution.public() for distribution in DISTRIBUTIONS],
        "session": {"active": False, "reason": "disabled"},
        "problem_code": "native_auth_disabled",
        "message": "La autenticación nativa está deshabilitada en este servidor.",
    }


@router.get("/config", summary="Distribuciones, perfiles y estado de la sesión")
def config(request: Request) -> dict[str, object]:
    settings = request.app.state.settings
    service, problem, enabled = _runtime(request)
    if service is None:
        if not enabled:
            return _disabled_config(settings)
        return {
            **_disabled_config(settings),
            "enabled": True,
            "native_auth_ready": False,
            "problem_code": problem.code if problem else "native_auth_misconfigured",
            "message": str(problem) if problem else "El servicio de autenticación nativa no está disponible.",
            "session": {"active": False, "reason": "unavailable"},
        }
    body = service.config(_cookie(request, service))
    body["enabled"] = True
    body["problem_code"] = None
    body["message"] = None
    return body


@router.get("/session", summary="Estado de la sesión del navegador")
def session(request: Request) -> dict[str, object]:
    service, problem, enabled = _runtime(request)
    if service is None:
        return {
            "active": False,
            "reason": "disabled" if not enabled else "unavailable",
            "message": str(problem) if problem else None,
        }
    return service.session_state(_cookie(request, service))


@router.post("/login", summary="Autenticar con ChillyRoom y crear una sesión aislada")
def login(payload: LoginInput, request: Request, response: Response) -> dict[str, object]:
    service = _require_service(request)
    settings = request.app.state.settings
    client = client_ip(request, settings.native_trusted_proxies)
    result = service.login(
        email=payload.email,
        password=payload.password,
        distribution_id=payload.distribution,
        profile_id=payload.profile_id,
        ip=client,
        existing_cookie=_cookie(request, service),
    )
    max_age = max(0, result.expires_at - int(time()))
    response.set_cookie(
        service.cookie_name,
        result.cookie,
        max_age=max_age,
        secure=service.secure,
        httponly=True,
        samesite="strict",
        path="/",
    )
    return result.body


@router.post("/logout", status_code=204, summary="Revocar la sesión del navegador")
def logout(request: Request, response: Response) -> None:
    service = _require_service(request)
    cookie = _cookie(request, service)
    service.logout(cookie)
    response.delete_cookie(service.cookie_name, secure=service.secure, httponly=True, samesite="strict", path="/")


@router.post("/installation", summary="Completar el identificador de instalación del perfil")
def installation(payload: InstallationInput, request: Request) -> dict[str, object]:
    service = _require_service(request)
    return service.complete_installation(_cookie(request, service), payload.unique_id)


@router.get("/save", summary="Descargar la partida de la cuenta autenticada")
def save(request: Request) -> dict[str, object]:
    service = _require_service(request)
    current = service.require_session(_cookie(request, service))
    return service.load(current)


@router.post("/prepare", summary="Preparar la edición de gemas y crear un respaldo")
def prepare(payload: PrepareInput, request: Request) -> dict[str, object]:
    service = _require_service(request)
    current = service.require_session(_cookie(request, service))
    return service.prepare(current, payload.new_gems, payload.source_sha256)


@router.post(
    "/prepare-fish-chip",
    summary="Preparar la edición experimental de fichas de pesca y crear un respaldo",
)
def prepare_fish_chip(payload: FishChipPrepareInput, request: Request) -> dict[str, object]:
    service = _require_service(request)
    current = service.require_session(_cookie(request, service))
    return service.prepare_fish_chip(current, payload.new_fish_chip, payload.source_sha256)


@router.post("/confirm", summary="Subir el candidato y verificar la persistencia")
def confirm(payload: CloudLabConfirmInput, request: Request) -> dict[str, object]:
    service = _require_service(request)
    current = service.require_session(_cookie(request, service))
    return service.confirm(current, payload.backup_id, payload.expected_sha256)


@router.post("/restore", summary="Restaurar el original de un respaldo confirmado")
def restore(payload: CloudLabRestoreInput, request: Request) -> dict[str, object]:
    service = _require_service(request)
    current = service.require_session(_cookie(request, service))
    return service.restore(current, payload.backup_id)


@router.post("/verify", summary="Verificar la nube frente a un respaldo")
def verify(payload: CloudLabVerifyInput, request: Request) -> dict[str, object]:
    service = _require_service(request)
    current = service.require_session(_cookie(request, service))
    return service.verify(current, payload.backup_id)


@router.get("/backups", summary="Listar los respaldos de la cuenta autenticada")
def backups(request: Request) -> dict[str, object]:
    service = _require_service(request)
    current = service.require_session(_cookie(request, service))
    return {"backups": service.backups(current)}


@router.get("/diagnostics", summary="Diagnóstico saneado del servicio nativo")
def diagnostics(request: Request) -> dict[str, object]:
    service, problem, enabled = _runtime(request)
    if service is None:
        return {
            "enabled": enabled,
            "configured": False,
            "problem_code": problem.code if problem else ("native_auth_disabled" if not enabled else None),
            "message": str(problem) if problem else None,
        }
    settings = request.app.state.settings
    token = settings.access_token
    header = request.headers.get("authorization", "")
    candidate = header[7:] if header.startswith("Bearer ") else ""
    authorized = (
        token is not None
        and candidate.isascii()
        and compare_digest(candidate, token.get_secret_value())
    )
    if not authorized:
        service.require_session(_cookie(request, service))
    return service.diagnostics()

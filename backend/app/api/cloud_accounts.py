"""API del editor por cuenta, autenticada con una cookie propia del navegador."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Request, Response
from fastapi.routing import APIRoute
from pydantic import BaseModel, StringConstraints, field_validator

from ..cloud.accounts import BROWSER_TTL, AccountError, CloudAccounts
from ..cloud.gems_editor import MAX_GEMS, MIN_GEMS
from ..cloud_save import CloudSaveError
from ..errors import PRIVATE_HEADERS, EditorError
from ..models import CloudLabConfirmInput, CloudLabPrepareInput, CloudLabRestoreInput, CloudLabVerifyInput
from .cloud_lab import _http_error
from .uploads import BoundedJSONRequest

LOGIN_MESSAGE = "El inicio de sesión con correo y contraseña de ChillyRoom aún no está disponible."
Hash = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$", min_length=64, max_length=64)]


class AccountRoute(APIRoute):
    def get_route_handler(self):
        handle = super().get_route_handler()

        async def guarded(request: Request) -> Response:
            accounts = request.app.state.cloud_accounts
            origin = request.headers.get("origin")
            if accounts and origin is not None and origin != accounts.origin:
                raise EditorError(403, "cloud_origin_denied", "Abre el editor desde el sitio principal de UnderDive.")
            if request.method == "POST":
                if not accounts:
                    if request.url.path.endswith("/login"):
                        raise EditorError(503, "cloud_login_unavailable", LOGIN_MESSAGE)
                    problem = request.app.state.cloud_accounts_problem
                    raise EditorError(problem.status, problem.code, str(problem))
                if origin != accounts.origin:
                    raise EditorError(403, "cloud_origin_denied", "El origen de la solicitud no está autorizado.")
                if (request.headers.get("content-type", "").partition(";")[0].strip().lower() != "application/json"
                        or request.headers.get("content-encoding", "identity").lower() != "identity"):
                    raise EditorError(415, "invalid_content_type", "Envía JSON UTF-8 sin compresión.")
                request = BoundedJSONRequest(request, 8192)
            try:
                response = await handle(request)
            except AccountError as exc:
                raise EditorError(exc.status, exc.code, str(exc)) from None
            except CloudSaveError as exc:
                raise _http_error(exc) from None
            except (OSError, sqlite3.Error):
                raise EditorError(503, "cloud_accounts_storage", "El almacén de cuentas no está disponible.") from None
            response.headers.update(PRIVATE_HEADERS)
            return response

        return guarded


router = APIRouter(prefix="/api/v1/cloud/accounts", tags=["Cuentas de ChillyRoom"], route_class=AccountRoute)


class ClaimInput(BaseModel):
    ticket: Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9_-]{43}$", min_length=43, max_length=43)]


class RenameInput(BaseModel):
    label: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]

    @field_validator("label")
    @classmethod
    def visible_label(cls, value: str) -> str:
        if not value.isprintable():
            raise ValueError("La etiqueta debe tener caracteres visibles.")
        return value


class PrepareInput(CloudLabPrepareInput):
    source_sha256: Hash


class UnlinkInput(BaseModel):
    confirmation: Literal["DESVINCULAR"]


def browser(request: Request) -> tuple[CloudAccounts, str]:
    accounts = request.app.state.cloud_accounts
    if not accounts:
        raise request.app.state.cloud_accounts_problem
    return accounts, request.cookies.get(accounts.cookie_name, "")


Browser = Annotated[tuple[CloudAccounts, str], Depends(browser)]


@router.get("")
def list_accounts(request: Request):
    accounts = request.app.state.cloud_accounts
    problem = request.app.state.cloud_accounts_problem
    return {
        "configured": accounts is not None,
        "message": str(problem) if problem else None,
        "password_login_available": False,
        "login_message": LOGIN_MESSAGE,
        "min_gems": MIN_GEMS,
        "max_gems": MAX_GEMS,
        "accounts": accounts.list(request.cookies.get(accounts.cookie_name, "")) if accounts else [],
    }


@router.post("/login")
def login():
    raise EditorError(503, "cloud_login_unavailable", LOGIN_MESSAGE)


@router.post("/claim")
def claim(payload: ClaimInput, response: Response, session: Browser):
    accounts, cookie = session
    cookie = accounts.claim(cookie, payload.ticket)
    response.set_cookie(accounts.cookie_name, cookie, max_age=BROWSER_TTL,
                        secure=accounts.secure, httponly=True, samesite="strict", path="/")
    return {"accounts": accounts.list(cookie)}


@router.post("/{account_id}/rename")
def rename(account_id: str, payload: RenameInput, session: Browser):
    accounts, cookie = session
    accounts.update(cookie, account_id, label=payload.label)
    return {"accounts": accounts.list(cookie)}


@router.post("/{account_id}/unlink")
def unlink(account_id: str, payload: UnlinkInput, session: Browser):
    accounts, cookie = session
    accounts.update(cookie, account_id)
    return {"accounts": accounts.list(cookie)}


@router.get("/{account_id}/save")
def download(account_id: str, session: Browser):
    accounts, cookie = session
    with accounts.service(cookie, account_id) as service:
        return service.load().summary() | {"downloaded_at": datetime.now(UTC).isoformat()}


@router.post("/{account_id}/prepare")
def prepare(account_id: str, payload: PrepareInput, session: Browser):
    accounts, cookie = session
    with accounts.service(cookie, account_id) as service:
        return service.prepare(payload.new_gems, expected_source=payload.source_sha256).summary()


@router.post("/{account_id}/confirm")
def confirm(account_id: str, payload: CloudLabConfirmInput, session: Browser):
    accounts, cookie = session
    with accounts.service(cookie, account_id) as service:
        return service.confirm(payload.backup_id, payload.expected_sha256, single_attempt=True).summary()


@router.post("/{account_id}/restore")
def restore(account_id: str, payload: CloudLabRestoreInput, session: Browser):
    accounts, cookie = session
    with accounts.service(cookie, account_id) as service:
        return service.restore(payload.backup_id).summary()


@router.post("/{account_id}/verify")
def verify(account_id: str, payload: CloudLabVerifyInput, session: Browser):
    accounts, cookie = session
    with accounts.service(cookie, account_id) as service:
        return service.verify(payload.backup_id).summary()


@router.get("/{account_id}/backups")
def backups(account_id: str, session: Browser):
    accounts, cookie = session
    with accounts.service(cookie, account_id, offline=True) as store:
        return {"backups": [
            record.summary() | {"confirmed": store.confirmation(record.id) is not None}
            for record in store.list()
        ]}

"""Rutas administrativas del laboratorio de gemas.

La lectura exige el token de acceso existente. La confirmación y la restauración
exigen además una cabecera administrativa comparada en tiempo constante con
``SK_CLOUD_ADMIN_TOKEN``. Ninguna ruta puede activar la escritura desde el
navegador: el servidor solo la habilita con variables de entorno.
"""

from __future__ import annotations

from hmac import compare_digest
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, Security
from fastapi.routing import APIRoute
from fastapi.security import APIKeyHeader

from ..cloud.backup_store import (
    BackupAlreadyConfirmed,
    BackupIntegrityError,
    BackupNotFound,
    BackupStorageUnavailable,
    BackupStoreError,
    InvalidBackupId,
)
from ..cloud.gems_editor import (
    MAX_GEMS,
    MIN_GEMS,
    GemsEditError,
    GemsFieldMissing,
    GemsVerificationError,
    InvalidGemsValue,
    UnsupportedAggregateSerialization,
)
from ..cloud.character_editor import CharacterEditError
from ..cloud.fish_chip_editor import FishChipEditError
from ..cloud.skin_editor import SkinEditError
from ..cloud.lab_service import (
    CloudLabService,
    LabAlreadyConfirmed,
    LabHashMismatch,
    LabNoChanges,
    LabRemoteChanged,
    LabServiceError,
    LabWriteDisabled,
)
from ..cloud.provider import (
    CloudProviderProtocolError,
    CloudProviderUnauthenticated,
    CloudProviderUnavailable,
)
from ..cloud.blob_upload import CloudUploadRejected
from ..cloud_save import AggregateFormatError, CloudSaveError, CopyLimitError
from ..errors import PRIVATE_HEADERS, EditorError
from ..models import (
    CloudBackupSummary,
    CloudLabBackups,
    CloudLabConfirmInput,
    CloudLabPrepared,
    CloudLabPrepareInput,
    CloudLabRestoreInput,
    CloudLabSave,
    CloudLabStatus,
    CloudLabVerification,
    CloudLabVerifyInput,
    CloudLabWriteResult,
)
from ..settings import Settings
from .uploads import BoundedJSONRequest, editor_bearer, require_access

router = APIRouter(
    prefix="/api/v1/cloud/lab",
    tags=["Laboratorio de nube"],
    dependencies=[Security(editor_bearer)],
)

cloud_admin_header = APIKeyHeader(
    name="X-SK-Cloud-Admin",
    scheme_name="CloudAdminToken",
    description=(
        "Token administrativo del servidor. Solo se exige para confirmar o restaurar. "
        "No se guarda en el navegador ni se puede habilitar desde el frontend."
    ),
    auto_error=False,
)


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_lab_service(request: Request) -> CloudLabService | None:
    return request.app.state.cloud_lab


def _require_service(request: Request) -> CloudLabService:
    service = get_lab_service(request)
    if service is None:
        raise EditorError(
            503,
            "cloud_lab_not_configured",
            "El laboratorio de nube no está configurado en el servidor.",
        )
    return service


async def require_cloud_admin(
    request: Request,
    credentials: Annotated[str | None, Security(cloud_admin_header)],
) -> None:
    settings: Settings = request.app.state.settings
    if not settings.cloud_write_enabled:
        raise EditorError(503, "cloud_write_disabled", "La escritura remota está deshabilitada.")
    secret = settings.cloud_admin_token
    if secret is None:
        raise EditorError(
            503,
            "cloud_admin_not_configured",
            "Falta configurar la autorización administrativa de escritura.",
        )
    if credentials is None or not credentials.isascii() or not compare_digest(credentials, secret.get_secret_value()):
        raise EditorError(
            403,
            "cloud_admin_denied",
            "La autorización administrativa falta o no es válida.",
        )


def _http_error(exc: CloudSaveError) -> EditorError:
    if isinstance(exc, BackupStorageUnavailable):
        return EditorError(503, exc.code, str(exc))
    if isinstance(exc, LabWriteDisabled):
        return EditorError(503, exc.code, "La escritura remota está deshabilitada en el servidor.")
    if isinstance(exc, (BackupNotFound,)):
        return EditorError(404, exc.code, str(exc))
    if isinstance(exc, (LabNoChanges, LabRemoteChanged, LabAlreadyConfirmed, BackupAlreadyConfirmed)):
        return EditorError(409, exc.code, str(exc))
    if isinstance(exc, (InvalidBackupId, LabHashMismatch, GemsEditError, FishChipEditError, CharacterEditError, SkinEditError)):
        return EditorError(422, exc.code, str(exc))
    if isinstance(exc, CopyLimitError):
        return EditorError(413, exc.code, str(exc))
    if isinstance(exc, CloudProviderUnauthenticated):
        return EditorError(
            502, "cloud_session_rejected", "El servicio de nube rechazó la sesión de laboratorio."
        )
    if isinstance(exc, CloudProviderUnavailable):
        return EditorError(502, exc.code, "ChillyRoom Cloud no respondió o devolvió un error de disponibilidad.")
    if isinstance(exc, (CloudProviderProtocolError, CloudUploadRejected)):
        return EditorError(502, exc.code, "No se pudo completar la operación con el servicio de nube.")
    if isinstance(exc, (BackupStoreError, BackupIntegrityError)):
        return EditorError(500, exc.code, "El respaldo privado no superó la verificación.")
    if isinstance(exc, (AggregateFormatError, GemsFieldMissing, GemsVerificationError,
                        UnsupportedAggregateSerialization, InvalidGemsValue)):
        return EditorError(422, exc.code, str(exc))
    if isinstance(exc, LabServiceError):
        return EditorError(502, exc.code, str(exc))
    return EditorError(422, exc.code, str(exc))


def _call(operation, *args, **kwargs):
    try:
        return operation(*args, **kwargs)
    except CloudSaveError as exc:
        raise _http_error(exc) from None


class LabRoute(APIRoute):
    """Autentica antes de leer el cuerpo y limita las solicitudes JSON."""

    def get_route_handler(self):
        handle = super().get_route_handler()

        async def guarded(request: Request) -> Response:
            settings: Settings = request.app.state.settings
            await require_access(request, settings)
            if request.method in {"POST", "PUT", "PATCH"}:
                content_type = request.headers.get("content-type", "").partition(";")[0].strip().lower()
                encoding = request.headers.get("content-encoding", "identity").lower()
                if content_type != "application/json" or encoding != "identity":
                    raise EditorError(415, "invalid_content_type", "Envía JSON UTF-8 sin compresión.")
                response = await handle(BoundedJSONRequest(request, 16_384))
            else:
                response = await handle(request)
            response.headers.update(PRIVATE_HEADERS)
            return response

        return guarded


router.route_class = LabRoute


@router.get("/status", response_model=CloudLabStatus, summary="Estado del laboratorio de gemas")
def lab_status(request: Request, settings: Annotated[Settings, Depends(get_settings)]) -> CloudLabStatus:
    service = get_lab_service(request)
    if service is None:
        return CloudLabStatus(
            mode="disabled",
            read_ready=False,
            write_enabled=settings.cloud_write_enabled,
            write_ready=False,
            admin_configured=settings.cloud_admin_configured,
            admin_required=True,
            backup_count=0,
            min_gems=MIN_GEMS,
            max_gems=MAX_GEMS,
            message="El laboratorio de nube no está configurado en el servidor.",
        )
    return CloudLabStatus(**service.status().summary())


@router.get("/save", response_model=CloudLabSave, summary="Descargar la partida auténtica de laboratorio")
def lab_save(service: Annotated[CloudLabService, Depends(get_lab_service)]) -> CloudLabSave:
    if service is None:
        raise EditorError(503, "cloud_lab_not_configured", "El laboratorio de nube no está configurado.")
    loaded = _call(service.load)
    return CloudLabSave(**loaded.summary())


@router.post("/prepare", response_model=CloudLabPrepared, summary="Preparar gemas y crear respaldo")
def lab_prepare(
    payload: CloudLabPrepareInput,
    service: Annotated[CloudLabService, Depends(get_lab_service)],
) -> CloudLabPrepared:
    if service is None:
        raise EditorError(503, "cloud_lab_not_configured", "El laboratorio de nube no está configurado.")
    prepared = _call(service.prepare, payload.new_gems)
    return CloudLabPrepared(**prepared.summary())


@router.post(
    "/confirm",
    response_model=CloudLabWriteResult,
    summary="Confirmar la subida administrativa",
    dependencies=[Depends(require_cloud_admin)],
)
def lab_confirm(
    payload: CloudLabConfirmInput,
    service: Annotated[CloudLabService, Depends(get_lab_service)],
) -> CloudLabWriteResult:
    if service is None:
        raise EditorError(503, "cloud_lab_not_configured", "El laboratorio de nube no está configurado.")
    result = _call(service.confirm, payload.backup_id, payload.expected_sha256)
    return CloudLabWriteResult(**result.summary())


@router.post(
    "/restore",
    response_model=CloudLabWriteResult,
    summary="Restaurar el original de un respaldo",
    dependencies=[Depends(require_cloud_admin)],
)
def lab_restore(
    payload: CloudLabRestoreInput,
    service: Annotated[CloudLabService, Depends(get_lab_service)],
) -> CloudLabWriteResult:
    if service is None:
        raise EditorError(503, "cloud_lab_not_configured", "El laboratorio de nube no está configurado.")
    result = _call(service.restore, payload.backup_id)
    return CloudLabWriteResult(**result.summary())


@router.post("/verify", response_model=CloudLabVerification, summary="Verificar la persistencia de un respaldo")
def lab_verify(
    payload: CloudLabVerifyInput,
    service: Annotated[CloudLabService, Depends(get_lab_service)],
) -> CloudLabVerification:
    if service is None:
        raise EditorError(503, "cloud_lab_not_configured", "El laboratorio de nube no está configurado.")
    result = _call(service.verify, payload.backup_id)
    return CloudLabVerification(**result.summary())


@router.get("/backups", response_model=CloudLabBackups, summary="Listar respaldos privados")
def lab_backups(service: Annotated[CloudLabService, Depends(get_lab_service)]) -> CloudLabBackups:
    if service is None:
        raise EditorError(503, "cloud_lab_not_configured", "El laboratorio de nube no está configurado.")
    records = _call(service.backups)
    return CloudLabBackups(backups=[CloudBackupSummary(**record.summary()) for record in records])

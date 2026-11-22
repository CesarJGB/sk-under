from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, Security

from ..engine import Editor
from ..file_validation import decode_file
from ..models import EditInput, ErrorResponse, Formats, Health, Inspection, InspectInput, Validation
from ..settings import Settings
from .uploads import FileRoute, editor_bearer

router = APIRouter(prefix="/api/v1")
file_router = APIRouter(
    prefix="/files",
    tags=["Archivos"],
    route_class=FileRoute,
    dependencies=[Security(editor_bearer)],
    responses={
        400: {"model": ErrorResponse, "description": "Solicitud malformada"},
        401: {"model": ErrorResponse, "description": "Token inválido o ausente"},
        403: {"model": ErrorResponse, "description": "Acceso desde fuera del modo local"},
        413: {"model": ErrorResponse, "description": "Archivo o solicitud demasiado grande"},
        415: {"model": ErrorResponse, "description": "Tipo de contenido, firma o versión no admitida"},
        422: {"model": ErrorResponse, "description": "Datos o cambios inválidos"},
        503: {"model": ErrorResponse, "description": "Protección del servicio sin configurar"},
    },
)


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_editor(request: Request) -> Editor:
    return request.app.state.editor


type ServiceSettings = Annotated[Settings, Depends(get_settings)]
type EditorService = Annotated[Editor, Depends(get_editor)]


@router.get("/health", tags=["Servicio"], summary="Consultar el estado y límite de archivos")
def health(settings: ServiceSettings) -> Health:
    return Health(access_mode=settings.access_mode, max_file_bytes=settings.max_file_bytes)


@router.get("/formats", tags=["Servicio"], summary="Consultar los formatos reconocidos por el motor")
def formats(editor: EditorService) -> Formats:
    return Formats(formats=editor.formats())


@file_router.post("/inspect", summary="Identificar y leer los campos admitidos")
def inspect_file(payload: InspectInput, settings: ServiceSettings, editor: EditorService) -> Inspection:
    return editor.inspect(decode_file(payload.content_base64, settings.max_file_bytes))


VERIFY_ERROR = {500: {"model": ErrorResponse, "description": "Falló la verificación de lectura"}}


@file_router.post("/validate", summary="Validar los cambios y verificar la copia", responses=VERIFY_ERROR)
def validate_file(payload: EditInput, settings: ServiceSettings, editor: EditorService) -> Validation:
    original = decode_file(payload.content_base64, settings.max_file_bytes)
    return editor.prepare_export(original, payload.changes, settings.max_file_bytes).validation


@file_router.post(
    "/export",
    summary="Volver a validar y descargar una nueva copia",
    response_class=Response,
    responses={
        200: {
            "description": "Copia serializada verificada",
            "content": {"application/octet-stream": {"schema": {"type": "string", "format": "binary"}}},
            "headers": {
                "Content-Disposition": {"schema": {"type": "string"}, "description": "Nombre seguro de la copia"},
            },
        },
        **VERIFY_ERROR,
    },
)
def export_file(payload: EditInput, settings: ServiceSettings, editor: EditorService) -> Response:
    original = decode_file(payload.content_base64, settings.max_file_bytes)
    output = editor.prepare_export(original, payload.changes, settings.max_file_bytes).file
    return Response(
        content=output.data,
        media_type=output.media_type,
        headers={"Content-Disposition": f'attachment; filename="{output.filename}"'},
    )


router.include_router(file_router)

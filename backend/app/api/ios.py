"""API experimental de importación local de copias de iOS (solo lectura)."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from ..cloud.ios import CAPABILITIES, IosSaveError, decode_ios_save
from ..cloud_save import MAX_INPUT_BYTES
from ..errors import PRIVATE_HEADERS, EditorError
from .uploads import BoundedJSONRequest

router = APIRouter(prefix="/api/v1/cloud/ios", tags=["iOS experimental"])

# El documento se envía en claro y el límite es el mismo del agregado de nube.
REQUEST_LIMIT = MAX_INPUT_BYTES + 4096


def _origin(request: Request) -> None:
    allowed = request.app.state.settings.allowed_origins
    origin = request.headers.get("origin")
    if origin is not None and origin not in allowed:
        raise EditorError(403, "origin_denied", "El origen de la solicitud no está autorizado.")
    if request.method not in {"GET", "HEAD"} and origin not in allowed:
        raise EditorError(403, "origin_denied", "El origen de la solicitud no está autorizado.")


@router.get("/capabilities", summary="Matriz de compatibilidad iOS")
def capabilities(request: Request) -> dict[str, object]:
    _origin(request)
    return {
        "platform": "ios",
        "experimental": True,
        "write_enabled": False,
        "authentication": "available_read_only",
        "download": "available_read_only",
        "native_distribution": "ios-global",
        "game_version": "8.8.0.13",
        "import_sources": ["crde-raw", "native-json"],
        "capabilities": list(CAPABILITIES),
    }


@router.post("/inspect", summary="Decodificar e interpretar una copia iOS sin modificarla")
async def inspect(request: Request) -> JSONResponse:
    _origin(request)
    content_type = request.headers.get("content-type", "").partition(";")[0].strip().lower()
    encoding = request.headers.get("content-encoding", "identity").lower()
    if content_type != "application/json" or encoding != "identity":
        raise EditorError(415, "invalid_content_type", "Envía JSON UTF-8 sin compresión.")
    payload = await BoundedJSONRequest(request, REQUEST_LIMIT).body()
    try:
        save = decode_ios_save(payload)
    except IosSaveError as exc:
        status = 413 if exc.code == "size_limit" else 415
        raise EditorError(status, exc.code, str(exc)) from None
    except Exception as exc:  # noqa: BLE001 - el detalle interno no se expone
        code = getattr(exc, "code", "invalid_aggregate")
        raise EditorError(422, str(code), "La copia no tiene una estructura de iOS reconocible.") from None
    body = save.summary()
    body["report"] = save.report()
    return JSONResponse(body, headers=PRIVATE_HEADERS)
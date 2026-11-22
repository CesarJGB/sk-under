from hmac import compare_digest
from ipaddress import ip_address

from fastapi import Request, Response
from fastapi.routing import APIRoute
from fastapi.security import HTTPBearer

from ..errors import PRIVATE_HEADERS, EditorError
from ..file_validation import base64_limit
from ..parsers.json_document import parse_json
from ..settings import Settings

editor_bearer = HTTPBearer(
    scheme_name="EditorBearer",
    description="Token privado del servicio. El modo local explícito admite loopback sin token.",
    auto_error=False,
)


def is_loopback(host: str) -> bool:
    try:
        return ip_address(host).is_loopback
    except ValueError:
        return False


async def require_access(request: Request, settings: Settings) -> None:
    if settings.access_mode == "disabled":
        raise EditorError(503, "access_disabled", "Configura la protección del servicio para habilitar archivos.")
    if settings.access_mode == "local":
        client = request.client
        host = request.url.hostname or ""
        if client and is_loopback(client.host) and (host == "localhost" or is_loopback(host)):
            return
        raise EditorError(403, "local_access_only", "El modo local solo permite conexiones de loopback.")

    credentials = await editor_bearer(request)
    secret = settings.access_token
    if (
        secret
        and credentials
        and credentials.credentials.isascii()
        and compare_digest(credentials.credentials, secret.get_secret_value())
    ):
        return
    raise EditorError(
        401, "access_denied", "El token de acceso falta o no es válido.",
        headers={"WWW-Authenticate": "Bearer"},
    )


class BoundedJSONRequest(Request):
    def __init__(self, request: Request, limit: int) -> None:
        super().__init__(request.scope, request.receive)
        self.limit = limit
        self.buffer: bytes | None = None

    async def body(self) -> bytes:
        if self.buffer is not None:
            return self.buffer

        lengths = self.headers.getlist("content-length")
        if lengths:
            length = lengths[0]
            if len(lengths) != 1 or len(length) > 20 or not (length.isascii() and length.isdigit()):
                raise EditorError(400, "invalid_request", "La longitud de la solicitud es inválida.")
            if int(length) > self.limit:
                raise self.size_error()

        data = bytearray()
        async for chunk in self.stream():
            if len(data) + len(chunk) > self.limit:
                raise self.size_error()
            data.extend(chunk)

        self.buffer = bytes(data)
        return self.buffer

    async def json(self) -> object:
        return parse_json(await self.body())

    @staticmethod
    def size_error() -> EditorError:
        return EditorError(413, "request_too_large", "La solicitud supera el límite permitido.")


class FileRoute(APIRoute):
    def get_route_handler(self):
        handle = super().get_route_handler()

        async def guarded(request: Request) -> Response:
            settings: Settings = request.app.state.settings
            # Protege la ruta antes de leer el cuerpo. Security documenta el mismo esquema en OpenAPI.
            await require_access(request, settings)
            content_type = request.headers.get("content-type", "").partition(";")[0].strip().lower()
            encoding = request.headers.get("content-encoding", "identity").lower()
            if content_type != "application/json" or encoding != "identity":
                raise EditorError(415, "invalid_content_type", "Envía JSON UTF-8 sin compresión.")

            request_limit = base64_limit(settings.max_file_bytes) + 16_384
            response = await handle(BoundedJSONRequest(request, request_limit))
            response.headers.update(PRIVATE_HEADERS)
            return response

        return guarded

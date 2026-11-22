from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from .models import ErrorDetail, ErrorResponse, Issue

PRIVATE_HEADERS = {"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"}


class EditorError(HTTPException):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        issues: list[Issue] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(status_code, headers=headers)
        self.error = ErrorDetail(code=code, message=message, issues=issues or [])


def error_response(exc: EditorError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(error=exc.error).model_dump(mode="json"),
        headers=PRIVATE_HEADERS | (exc.headers or {}),
    )


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(HTTPException)
    async def handle_http_error(_: Request, exc: HTTPException) -> JSONResponse:
        if isinstance(exc, EditorError):
            return error_response(exc)
        return error_response(
            EditorError(
                exc.status_code,
                "invalid_request",
                "La solicitud no se pudo procesar.",
                headers=exc.headers,
            )
        )

    @app.exception_handler(RequestValidationError)
    async def handle_schema_error(_: Request, __: RequestValidationError) -> JSONResponse:
        # Pydantic incluye fragmentos de entrada en sus errores predeterminados.
        return error_response(
            EditorError(422, "invalid_request", "La solicitud no cumple el contrato de la API.")
        )

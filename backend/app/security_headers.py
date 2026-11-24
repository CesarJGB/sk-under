"""Cabeceras de seguridad para la API y el editor.

La API devuelve JSON y no necesita cargar recursos. Se aplica una CSP mínima a
las rutas ``/api/`` para que un error o una respuesta inesperada no pueda
convertirse en un documento activo. La CSP del frontend se genera en Vite con
el origen exacto de la API; esta capa no la sustituye.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from starlette.responses import Response

_API_CSP = "default-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'"
_BASE_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=()",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-site",
}


def install_security_headers(app: FastAPI) -> None:
    settings = app.state.settings

    @app.middleware("http")
    async def security_headers(request: Request, call_next) -> Response:  # noqa: ANN001
        response = await call_next(request)
        for name, value in _BASE_HEADERS.items():
            response.headers.setdefault(name, value)
        if request.url.path.startswith("/api/"):
            response.headers.setdefault("Content-Security-Policy", _API_CSP)
            response.headers.setdefault("Cache-Control", "no-store")
        forwarded_proto = request.headers.get("x-forwarded-proto", "").split(",", 1)[0].strip().lower()
        https = request.url.scheme == "https" or forwarded_proto == "https"
        if settings.env == "production" and https:
            response.headers.setdefault(
                "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
            )
        return response

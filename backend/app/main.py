from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.routes import router
from .engine import Editor
from .errors import install_error_handlers
from .settings import Settings


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    app = FastAPI(
        title="Soul Knight Editor API",
        version="0.2.0",
        description="Inspección y exportación de copias. Compatibilidad inicial limitada a muestras sintéticas.",
    )
    app.state.settings = settings
    app.state.editor = Editor()
    install_error_handlers(app)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type"],
        expose_headers=["Content-Disposition"],
    )
    app.include_router(router)
    return app

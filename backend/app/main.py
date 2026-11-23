from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.cloud_lab import router as cloud_lab_router
from .api.routes import router
from .cloud.lab_service import build_cloud_lab
from .engine import Editor
from .errors import install_error_handlers
from .formats.game_data import GameDataAdapter
from .formats.real_save import RealSaveAdapter
from .formats.registry import ADAPTERS
from .settings import Settings


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    app = FastAPI(
        title="Soul Knight Editor API",
        version="0.3.0",
        description="Inspección y exportación de copias. Formatos disponibles según la configuración.",
    )
    app.state.settings = settings
    cipher = settings.save_cipher
    adapters = (*ADAPTERS, RealSaveAdapter(*cipher), GameDataAdapter()) if cipher is not None else ADAPTERS
    app.state.editor = Editor(adapters)
    app.state.cloud_lab = build_cloud_lab(settings)
    install_error_handlers(app)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type", "X-SK-Cloud-Admin"],
        expose_headers=["Content-Disposition"],
    )
    app.include_router(router)
    app.include_router(cloud_lab_router)
    return app

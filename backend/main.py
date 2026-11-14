"""AGBÉA CLIMAT — application FastAPI.

Lancer :  uvicorn backend.main:app --reload --port 8000
Docs   :  http://localhost:8000/docs
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.router import api_router
from backend.core.config import settings
from backend.core.constants import APP_VERSION
from backend.core.exceptions import register_exception_handlers


def create_app() -> FastAPI:
    app = FastAPI(title="AGBÉA CLIMAT API", version=APP_VERSION)
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins_list,
                       allow_methods=["*"], allow_headers=["*"])
    register_exception_handlers(app)
    app.include_router(api_router)
    return app


app = create_app()

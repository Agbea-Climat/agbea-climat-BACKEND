"""AGBÉA CLIMAT — application FastAPI.

Lancer :  uvicorn backend.main:app --reload --port 8000
Docs   :  http://localhost:8000/docs
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.router import api_router
from backend.core.config import settings
from backend.core.constants import APP_VERSION
from backend.core.exceptions import register_exception_handlers
from backend.repositories import store
from chatbot import memory


@asynccontextmanager
async def lifespan(_: FastAPI):
    store.warm_up()             # données P2 en mémoire (ignoré si absentes)
    await memory.open_saver()   # checkpointer Postgres des fils de chat (repli en RAM)
    yield
    await memory.close_saver()


def create_app() -> FastAPI:
    app = FastAPI(title="AGBÉA CLIMAT API", version=APP_VERSION, lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins_list,
                       allow_methods=["*"], allow_headers=["*"])
    register_exception_handlers(app)
    app.include_router(api_router)
    return app


app = create_app()

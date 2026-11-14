"""Handlers FastAPI : toute erreur sort au format {"error": {...}}."""
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from .errors import ApiError


async def api_error(_: Request, exc: ApiError):
    return JSONResponse(status_code=exc.status_code, content={"error": exc.to_dict()})


async def http_error(_: Request, exc: StarletteHTTPException):
    d = exc.detail if isinstance(exc.detail, dict) else {"code": str(exc.status_code), "message": str(exc.detail)}
    return JSONResponse(status_code=exc.status_code, content={"error": d})


async def validation_error(_: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content={"error": {
        "code": "validation_error", "message": "Paramètres invalides", "details": exc.errors()}})


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ApiError, api_error)
    app.add_exception_handler(StarletteHTTPException, http_error)
    app.add_exception_handler(RequestValidationError, validation_error)

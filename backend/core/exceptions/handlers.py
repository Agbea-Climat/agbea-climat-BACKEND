"""Handlers FastAPI : toute erreur sort dans l'enveloppe commune.

{"status": "error", "message": "<texte lisible>", "response": {"code": "<snake_case>", "details": ...}}
"""
import logging
from typing import Any, Optional

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from .errors import ApiError

log = logging.getLogger(__name__)

# Codes des erreurs HTTP levées par le framework (route inconnue, méthode refusée…)
HTTP_CODES = {400: "bad_request", 401: "unauthorized", 403: "forbidden", 404: "not_found",
              405: "method_not_allowed", 409: "conflict", 429: "too_many_requests"}


def error_response(status_code: int, code: str, message: str, details: Optional[Any] = None) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={
        "status": "error", "message": message,
        "response": {"code": code, "details": jsonable_encoder(details)}})


async def api_error(_: Request, exc: ApiError):
    return error_response(exc.status_code, exc.code, exc.message, exc.details)


async def http_error(_: Request, exc: StarletteHTTPException):
    if isinstance(exc.detail, dict):
        d = exc.detail
        return error_response(exc.status_code, d.get("code", HTTP_CODES.get(exc.status_code, "http_error")),
                              d.get("message", ""), d.get("details"))
    return error_response(exc.status_code, HTTP_CODES.get(exc.status_code, f"http_{exc.status_code}"), str(exc.detail))


async def validation_error(_: Request, exc: RequestValidationError):
    return error_response(422, "validation_error", "Paramètres invalides", exc.errors())


async def unexpected_error(_: Request, exc: Exception):
    log.exception("Erreur non gérée", exc_info=exc)
    return error_response(500, "internal_error", "Erreur interne du serveur")


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ApiError, api_error)
    app.add_exception_handler(StarletteHTTPException, http_error)
    app.add_exception_handler(RequestValidationError, validation_error)
    app.add_exception_handler(Exception, unexpected_error)

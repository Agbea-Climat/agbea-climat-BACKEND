"""Handlers FastAPI : toute erreur sort dans l'enveloppe commune.

{"status": "error", "message": "<texte lisible>", "response": {"code": "<snake_case>", "details": ...}}

Messages en français, y compris pour les erreurs du framework (route inconnue, méthode refusée,
paramètres invalides).
"""
import logging
from http import HTTPStatus
from typing import Any, Optional

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from .errors import ApiError

log = logging.getLogger(__name__)

# Erreurs HTTP levées par le framework (route inconnue, méthode refusée…) : code et message français
HTTP_CODES = {400: ("bad_request", "Requête invalide"),
              401: ("unauthorized", "Authentification requise"),
              403: ("forbidden", "Accès refusé"),
              404: ("not_found", "Ressource introuvable"),
              405: ("method_not_allowed", "Méthode HTTP non autorisée pour cette route"),
              406: ("not_acceptable", "Format de réponse non disponible"),
              409: ("conflict", "Conflit avec l'état actuel de la ressource"),
              413: ("payload_too_large", "Requête trop volumineuse"),
              415: ("unsupported_media_type", "Type de contenu non pris en charge"),
              429: ("too_many_requests", "Trop de requêtes, réessayez plus tard")}

# Erreurs de validation Pydantic les plus courantes, en français ({…} = valeurs de `ctx`)
VALIDATION_MSGS = {
    "missing": "champ obligatoire",
    "less_than_equal": "doit être inférieur ou égal à {le}",
    "less_than": "doit être inférieur à {lt}",
    "greater_than_equal": "doit être supérieur ou égal à {ge}",
    "greater_than": "doit être supérieur à {gt}",
    "finite_number": "doit être un nombre fini (ni nan ni inf)",
    "float_parsing": "doit être un nombre",
    "float_type": "doit être un nombre",
    "int_parsing": "doit être un entier",
    "int_type": "doit être un entier",
    "bool_parsing": "doit être true ou false",
    "string_type": "doit être un texte",
    "string_too_short": "texte trop court (au moins {min_length} caractères)",
    "string_too_long": "texte trop long (au plus {max_length} caractères)",
    "too_short": "liste trop courte (au moins {min_length} éléments)",
    "too_long": "liste trop longue (au plus {max_length} éléments)",
    "literal_error": "valeur non autorisée (attendu : {expected})",
    "enum": "valeur non autorisée (attendu : {expected})",
    "json_invalid": "JSON invalide",
    "model_attributes_type": "doit être un objet JSON",
    "dict_type": "doit être un objet JSON",
    "list_type": "doit être une liste",
    "tuple_type": "doit être une liste",
    "uuid_parsing": "doit être un UUID",
    "extra_forbidden": "champ non autorisé",
}
INPUT_MAX = 100    # caractères de la valeur reçue renvoyés dans `details` (au-delà : tronquée)
MESSAGE_MAX = 300  # caractères d'un message d'erreur (un identifiant reçu de 3 000 caractères est coupé)


def _short(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[:limit] + "…"


def error_response(status_code: int, code: str, message: str, details: Optional[Any] = None,
                   headers: Optional[dict] = None) -> JSONResponse:
    return JSONResponse(status_code=status_code, headers=headers, content={
        "status": "error", "message": message or HTTPStatus(status_code).phrase,
        "response": {"code": code, "details": jsonable_encoder(details)}})


async def api_error(_: Request, exc: ApiError):
    return error_response(exc.status_code, exc.code, _short(exc.message, MESSAGE_MAX), exc.details)


async def http_error(request: Request, exc: StarletteHTTPException):
    code, message = HTTP_CODES.get(exc.status_code, (f"http_{exc.status_code}", "Erreur HTTP"))
    if isinstance(exc.detail, dict):
        d = exc.detail
        return error_response(exc.status_code, d.get("code", code), d.get("message") or message,
                              d.get("details"), exc.headers)
    details = None
    if exc.status_code in (404, 405):
        details = {"path": _short(request.url.path, MESSAGE_MAX), "method": request.method}
    # Texte par défaut de Starlette (« Not Found »…) → message français ; texte explicite → conservé
    detail = str(exc.detail or "")
    if detail and detail != HTTPStatus(exc.status_code).phrase:
        message = _short(detail, MESSAGE_MAX)
    return error_response(exc.status_code, code, message, details, exc.headers)


def _fallback(e: dict) -> str:
    """Type non traduit : texte d'un validateur du projet (ValueError) ou message générique."""
    if e.get("type") == "value_error":
        return _short(str(e.get("msg", "")).removeprefix("Value error, "), MESSAGE_MAX)
    return "valeur invalide"


def _clean_error(e: dict) -> dict:
    """Erreur Pydantic en français, sans `ctx` (textes anglais de Pydantic, déjà repris dans `msg`) ni
    `input` complet (un texte de 2 000 caractères n'est pas renvoyé tel quel)."""
    ctx = e.get("ctx") or {}
    tpl = VALIDATION_MSGS.get(e.get("type", ""))
    try:
        nice = {k: (int(v) if isinstance(v, float) and v.is_integer()
                    else str(v).replace("' or '", "' ou '") if k == "expected" else v) for k, v in ctx.items()}
        msg = tpl.format(**nice) if tpl else _fallback(e)
    except (KeyError, IndexError, ValueError):
        msg = _fallback(e)
    out = {"type": e.get("type"), "loc": list(e.get("loc", ())), "msg": msg}
    value = e.get("input")
    if isinstance(value, str):
        out["input"] = value if len(value) <= INPUT_MAX else value[:INPUT_MAX] + "…"
    elif isinstance(value, (int, float, bool)):
        out["input"] = value
    # objets / listes (corps de requête entier) : non renvoyés
    return out


def _field(issue: dict) -> str:
    if issue["type"] == "json_invalid":
        return "corps de la requête"
    parts = [str(p) for p in issue["loc"] if p not in ("query", "path", "body", "header", "cookie")]
    return ".".join(parts) or "requête"


async def validation_error(_: Request, exc: RequestValidationError):
    errors = [_clean_error(e) for e in exc.errors()]
    summary = " ; ".join(f"{_field(e)} : {e['msg']}" for e in errors[:3])
    if len(errors) > 3:
        summary += f" (+{len(errors) - 3})"
    return error_response(422, "validation_error", f"Paramètres invalides — {summary}" if summary
                          else "Paramètres invalides", errors)


async def unexpected_error(_: Request, exc: Exception):
    log.exception("Erreur non gérée", exc_info=exc)
    return error_response(500, "internal_error", "Erreur interne du serveur")


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ApiError, api_error)
    app.add_exception_handler(StarletteHTTPException, http_error)
    app.add_exception_handler(RequestValidationError, validation_error)
    app.add_exception_handler(Exception, unexpected_error)

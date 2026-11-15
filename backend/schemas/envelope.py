"""Enveloppe commune à toutes les réponses JSON de l'API.

Succès : {"status": "success", "message": "OK", "response": <données>}
Erreur : {"status": "error", "message": "<texte lisible>", "response": {"code": "<snake_case>", "details": ...}}

Exceptions (pas d'enveloppe) : flux SSE `/chat/stream` et fichiers de `/timeseries/export`.
"""
from __future__ import annotations

from typing import Any, Generic, Literal, Optional, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    status: Literal["success"] = "success"
    message: str = "OK"
    response: T


class ValidationIssue(BaseModel):
    """Élément de `details` d'une erreur 422 `validation_error` (construit par
    backend/core/exceptions/handlers.py). `msg` en français pour les types courants ;
    `input` : valeur reçue tronquée à 100 caractères, absente pour un objet ou une liste."""
    type: str
    loc: list[str | int]
    msg: str
    input: Optional[str | float | bool] = None


class ErrorDetail(BaseModel):
    code: str
    details: Optional[Any] = None


class ApiErrorResponse(BaseModel):
    status: Literal["error"] = "error"
    message: str
    response: ErrorDetail


class ValidationErrorDetail(BaseModel):
    code: Literal["validation_error"] = "validation_error"
    details: list[ValidationIssue]


class ApiValidationErrorResponse(BaseModel):
    """Erreur 422 : même enveloppe qu'ApiErrorResponse, `details` typé (documentation OpenAPI)."""
    status: Literal["error"] = "error"
    message: str
    response: ValidationErrorDetail


def ok(data: Any, message: str = "OK") -> dict:
    """À renvoyer par chaque route : `return ok(service.fonction(...))`."""
    return {"status": "success", "message": message, "response": data}

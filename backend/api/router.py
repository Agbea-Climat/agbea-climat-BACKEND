"""Assemble tous les routers sous /api/v1. Toutes les réponses JSON utilisent l'enveloppe
{status, message, response} (voir backend/schemas/envelope.py)."""
from fastapi import APIRouter

from backend.core.constants import API_PREFIX
from backend.schemas import ApiErrorResponse

from . import admin, ai, catalog, meta, observations, profiles, regions, sessions, views, voice

ERRORS = {code: {"model": ApiErrorResponse} for code in (400, 404, 422, 500)}

api_router = APIRouter(prefix=API_PREFIX, responses=ERRORS)
for module in (meta, profiles, sessions, regions, catalog, observations, views, ai, admin, voice):
    api_router.include_router(module.router)

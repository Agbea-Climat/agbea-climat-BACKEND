"""Assemble tous les routers sous /api/v1. Toutes les réponses JSON utilisent l'enveloppe
{status, message, response} (voir backend/schemas/envelope.py)."""
from fastapi import APIRouter

from backend.core.constants import API_PREFIX
from backend.schemas import ApiErrorResponse
from backend.schemas.envelope import ApiValidationErrorResponse

from . import admin, ai, catalog, meta, observations, profiles, regions, sessions, views, voice

# Erreurs documentées sur toutes les routes (OpenAPI)
ERRORS = {
    400: {"model": ApiErrorResponse, "description": "Requête invalide (code métier : `invalid_period`…)"},
    404: {"model": ApiErrorResponse, "description": "Ressource introuvable (`region_not_found`, `not_found`…)"},
    405: {"model": ApiErrorResponse, "description": "Méthode HTTP non autorisée (`method_not_allowed`, en-tête `Allow`)"},
    422: {"model": ApiValidationErrorResponse, "description": "Paramètres invalides (`validation_error`)"},
    500: {"model": ApiErrorResponse, "description": "Erreur interne (`internal_error`)"},
}
# 503 `data_unavailable` : seulement sur les routes qui lisent data/ (regions.geojson, processed/),
# levé quand ces fichiers sont absents ou incomplets (pipeline P2 non lancé)
DATA_UNAVAILABLE = {"model": ApiErrorResponse, "description": "Données indisponibles (`data_unavailable`)"}
DATA_ROUTES = {
    ("GET", "/meta"),
    ("GET", "/regions"), ("GET", "/regions/geojson"), ("GET", "/regions/{region_id}"), ("GET", "/locate"),
    ("PATCH", "/sessions/{session_id}/preferences"),       # vérifie region_id dans regions.geojson
    ("GET", "/regions/{region_id}/summary"), ("GET", "/regions/{region_id}/timeseries"),
    ("GET", "/regions/{region_id}/compare"), ("GET", "/regions/{region_id}/timeseries/export"),
    ("GET", "/layers/{layer_id}/before-after"),
    ("GET", "/dashboard"), ("GET", "/regions/{region_id}/agriculture"),
    ("POST", "/explain"), ("POST", "/chat"), ("POST", "/chat/stream"),
}

api_router = APIRouter(prefix=API_PREFIX, responses=ERRORS)
for module in (meta, profiles, sessions, regions, catalog, observations, views, ai, admin, voice):
    for route in module.router.routes:   # chemins sans préfixe, marqués avant l'inclusion
        if any((m, getattr(route, "path", None)) in DATA_ROUTES for m in getattr(route, "methods", None) or ()):
            route.responses[503] = DATA_UNAVAILABLE
    api_router.include_router(module.router)

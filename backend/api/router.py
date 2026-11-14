"""Assemble tous les routers sous /api/v1."""
from fastapi import APIRouter

from backend.core.constants import API_PREFIX

from . import admin, ai, catalog, meta, observations, profiles, regions, sessions, views, voice

api_router = APIRouter(prefix=API_PREFIX)
for module in (meta, profiles, sessions, regions, catalog, observations, views, ai, admin, voice):
    api_router.include_router(module.router)

"""Méta de l'application."""
from __future__ import annotations

from pydantic import BaseModel

from .common import FeatureStatus


class Feature(BaseModel):
    id: str
    title: str
    status: FeatureStatus


class AppMeta(BaseModel):
    version: str
    regions_count: int
    data_last_updated: str
    features: list[Feature]

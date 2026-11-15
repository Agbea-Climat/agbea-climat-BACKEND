"""Méta de l'application."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel

from .common import FeatureStatus


class Feature(BaseModel):
    id: str
    title: str
    status: FeatureStatus


class AppMeta(BaseModel):
    version: str
    regions_count: int
    data_last_updated: str                                    # YYYY-MM-DD, toutes séries confondues
    # Dernier mois disponible par indicateur ("YYYY-MM") : les séries s'arrêtent à des dates différentes
    data_last_updated_by_indicator: Optional[dict[str, str]] = None
    features: list[Feature]

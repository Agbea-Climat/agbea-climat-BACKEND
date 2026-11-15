"""Catalogue : datasets (provenance), indicateurs, couches de carte, profils."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel

from .common import FeatureStatus, IndicatorId, Mode, ProfileId


# ── Provenance ──
class Dataset(BaseModel):
    id: str
    name: str
    provider: str
    variable: str
    indicator: IndicatorId
    units: str
    spatial_resolution: str
    temporal_resolution: str
    coverage: str
    period_start: str
    period_end: Optional[str] = None
    limitations: list[str] = []
    source_url: str
    citation: Optional[str] = None


# ── Carte ──
class LegendStop(BaseModel):
    value: float
    color: str
    label: Optional[str] = None


class MapLayer(BaseModel):
    id: str
    indicator: IndicatorId
    dataset_id: str
    title: str
    # Provenance exacte des tuiles (produit, résolution, unité), quand elle diffère du dataset_id
    # (le dataset_id reste celui des séries de l'indicateur)
    description: Optional[str] = None
    type: Literal["wmts", "xyz", "geojson"]
    url_template: str
    available_dates: list[str]
    default_date: str
    opacity: float = 0.7
    legend: list[LegendStop]
    modes: list[Mode] = ["public", "scientific"]
    max_zoom: Optional[int] = None  # zoom maximal servi (au-delà, GIBS répond 400)


# ── Indicateurs ──
class Indicator(BaseModel):
    id: IndicatorId
    label: str
    units: str
    dataset_id: str
    description_public: str
    description_scientific: str
    has_timeseries: bool
    layer_id: Optional[str] = None
    status: FeatureStatus = "prototype"


# ── Types d'utilisateurs (slide 11) ──
class Profile(BaseModel):
    id: ProfileId
    title: str
    audience: str
    benefit: str
    icon: str
    default_mode: Mode
    landing_screen: Literal["agriculture", "dashboard", "map", "scientific"]
    featured_indicators: list[IndicatorId]
    ai_tone: str

"""Géographie."""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel


class Region(BaseModel):
    id: str
    name: str
    capital: str
    centroid: tuple[float, float]
    bbox: tuple[float, float, float, float]
    area_km2: Optional[float] = None


# ── GET /regions/geojson ──
class RegionGeometry(BaseModel):
    type: Literal["Polygon", "MultiPolygon"]
    coordinates: list[Any]          # GeoJSON (RFC 7946), positions en [lon, lat]


class RegionFeature(BaseModel):
    type: Literal["Feature"] = "Feature"
    properties: Region
    geometry: RegionGeometry


class RegionFeatureCollection(BaseModel):
    type: Literal["FeatureCollection"] = "FeatureCollection"
    # Attribution des limites officielles (champ racine de data/regions.geojson), à afficher avec la carte
    source: Optional[str] = None
    features: list[RegionFeature]

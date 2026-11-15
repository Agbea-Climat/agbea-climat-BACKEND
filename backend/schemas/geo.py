"""Géographie."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class Region(BaseModel):
    id: str
    name: str
    capital: str
    centroid: tuple[float, float]
    bbox: tuple[float, float, float, float]
    area_km2: Optional[float] = None

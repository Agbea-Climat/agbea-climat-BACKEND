"""Vues métier : tableau de bord, agriculture."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from .common import Statement, Trend
from .observations import RegionSummary


class Dashboard(BaseModel):
    date: str
    regions: list[RegionSummary]
    highlights: list[Statement] = []


class AgriInsight(BaseModel):
    region_id: str
    date: str
    season: Literal["dry", "rainy", "transition"]
    rainfall_status: Trend
    vegetation_status: Trend
    statements: list[Statement]
    disclaimer: str

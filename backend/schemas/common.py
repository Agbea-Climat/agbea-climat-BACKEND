"""Types partagés (énumérations) et briques communes : Source, Statement."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel

Mode = Literal["public", "scientific"]
Lang = Literal["fr", "en", "ee"]
IndicatorId = Literal["precipitation", "ndvi", "lst_day", "elevation", "land_cover"]
Granularity = Literal["month", "year"]
StatementNature = Literal["observed", "interpreted", "predicted"]
FeatureStatus = Literal["prototype", "in_development", "planned"]
Trend = Literal["above_normal", "normal", "below_normal", "unknown"]
ProfileId = Literal["farmer", "community", "researcher", "decision_maker"]


# ── Provenance d'une affirmation ──
class Source(BaseModel):
    id: str
    kind: Literal["dataset", "document", "computed"]
    title: str
    url: Optional[str] = None
    dataset_id: Optional[str] = None
    snippet: Optional[str] = None
    page: Optional[int] = None


class Statement(BaseModel):
    text: str
    nature: StatementNature
    source_ids: list[str] = []

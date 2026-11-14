"""Observations : séries, résumés, comparaisons, avant/après."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel

from .common import Granularity, IndicatorId, Trend
from .geo import Region


class TimePoint(BaseModel):
    date: str
    value: Optional[float]
    baseline: Optional[float] = None
    anomaly_pct: Optional[float] = None


class TimeSeries(BaseModel):
    region_id: str
    indicator: IndicatorId
    units: str
    granularity: Granularity
    baseline_period: tuple[str, str] = ("2001", "2020")
    points: list[TimePoint]
    dataset_id: str
    nature: Literal["observed"] = "observed"


class IndicatorSnapshot(BaseModel):
    indicator: IndicatorId
    label: str
    value: Optional[float]
    units: str
    date: str
    baseline: Optional[float]
    anomaly_pct: Optional[float]
    trend: Trend
    plain_summary: str
    dataset_id: str


class RegionSummary(BaseModel):
    region: Region
    date: str
    indicators: list[IndicatorSnapshot]


class PeriodStats(BaseModel):
    label: str
    start: str
    end: str
    mean: Optional[float]
    min: Optional[float]
    max: Optional[float]


class Comparison(BaseModel):
    region_id: str
    indicator: IndicatorId
    units: str
    period_a: PeriodStats
    period_b: PeriodStats
    delta_abs: Optional[float]
    delta_pct: Optional[float]
    dataset_id: str


class LayerAtDate(BaseModel):
    date: str
    url_template: str


class BeforeAfter(BaseModel):
    layer_id: str
    before: LayerAtDate
    after: LayerAtDate
    comparison: Optional[Comparison] = None

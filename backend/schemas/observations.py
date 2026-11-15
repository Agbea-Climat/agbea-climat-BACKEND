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
    # Part de la région visible (0–1). En granularité `year` : part du mois agrégé le moins couvert.
    valid_frac: Optional[float] = None
    # valid_frac < 0,5 : valeur peu représentative. En `year` : au moins un mois agrégé l'est.
    low_coverage: bool = False
    # Granularité `year` : nombre de mois avec valeur dans l'année (12 = année entière ; moins = année
    # partielle, valeur seulement pour NDVI / température à partir de 10 mois). null en granularité `month`.
    months_count: Optional[int] = None


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
    # Lue sur l'écart affiché : anomalie % à 0,1 (pluie, NDVI) ; température : valeur − normale affichée
    trend: Trend
    plain_summary: str
    dataset_id: str
    valid_frac: Optional[float] = None
    low_coverage: bool = False


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
    # Raison de l'absence de `comparison` quand region_id est fourni (année incomplète, hors données)
    comparison_note: Optional[str] = None

"""AGBÉA CLIMAT — schémas Pydantic (miroir de contract/types.ts)."""
from __future__ import annotations

from typing import Annotated, Literal, Optional, Union

from pydantic import BaseModel, Field

Mode = Literal["public", "scientific"]
Lang = Literal["fr", "en", "ee"]
IndicatorId = Literal["precipitation", "ndvi", "lst_day", "elevation", "land_cover"]
Granularity = Literal["month", "year"]
StatementNature = Literal["observed", "interpreted", "predicted"]
FeatureStatus = Literal["prototype", "in_development", "planned"]
Trend = Literal["above_normal", "normal", "below_normal", "unknown"]
ProfileId = Literal["farmer", "community", "researcher", "decision_maker"]


# ── Géographie ──
class Region(BaseModel):
    id: str
    name: str
    capital: str
    centroid: tuple[float, float]
    bbox: tuple[float, float, float, float]
    area_km2: Optional[float] = None


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
    type: Literal["wmts", "xyz", "geojson"]
    url_template: str
    available_dates: list[str]
    default_date: str
    opacity: float = 0.7
    legend: list[LegendStop]
    modes: list[Mode] = ["public", "scientific"]


# ── Indicateurs ──
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


# ── IA / RAG ──
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


class ExplainRequest(BaseModel):
    profile: Optional[ProfileId] = None
    region_id: str
    indicator: IndicatorId
    date: Optional[str] = None
    mode: Mode = "public"
    lang: Lang = "fr"


class ExplainResponse(BaseModel):
    title: str
    statements: list[Statement]
    sources: list[Source]
    disclaimer: str


class ChatRequest(BaseModel):
    thread_id: Optional[str] = None
    profile: Optional[ProfileId] = None
    message: str = Field(min_length=1, max_length=2000)
    mode: Mode = "public"
    lang: Lang = "fr"
    region_id: Optional[str] = None
    location: Optional[tuple[float, float]] = None


class ChatResponse(BaseModel):
    thread_id: str
    answer: str
    statements: list[Statement] = []
    sources: list[Source] = []
    data: Optional[dict] = None


# Événements SSE (data: <json>)
class EvMeta(BaseModel):
    type: Literal["meta"] = "meta"
    thread_id: str

class EvStatus(BaseModel):
    type: Literal["status"] = "status"
    step: Literal["routing", "fetching_data", "retrieving", "generating"]

class EvToken(BaseModel):
    type: Literal["token"] = "token"
    content: str

class EvData(BaseModel):
    type: Literal["data"] = "data"
    series: Optional[TimeSeries] = None
    snapshot: Optional[IndicatorSnapshot] = None

class EvSources(BaseModel):
    type: Literal["sources"] = "sources"
    sources: list[Source]

class EvDone(BaseModel):
    type: Literal["done"] = "done"
    statements: Optional[list[Statement]] = None

class EvError(BaseModel):
    type: Literal["error"] = "error"
    message: str

ChatEvent = Annotated[
    Union[EvMeta, EvStatus, EvToken, EvData, EvSources, EvDone, EvError],
    Field(discriminator="type"),
]


# ── Ajouts v0.2 ──
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


class Dashboard(BaseModel):
    date: str
    regions: list[RegionSummary]
    highlights: list[Statement] = []


class LayerAtDate(BaseModel):
    date: str
    url_template: str


class BeforeAfter(BaseModel):
    layer_id: str
    before: LayerAtDate
    after: LayerAtDate
    comparison: Optional[Comparison] = None


class AgriInsight(BaseModel):
    region_id: str
    date: str
    season: Literal["dry", "rainy", "transition"]
    rainfall_status: Trend
    vegetation_status: Trend
    statements: list[Statement]
    disclaimer: str


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


# ── Sessions anonymes ──
class Preferences(BaseModel):
    profile: Optional[ProfileId] = None
    region_id: Optional[str] = None
    lang: Optional[Lang] = None
    mode: Optional[Mode] = None


class ThreadSummary(BaseModel):
    thread_id: str
    title: str
    updated_at: str


class Session(BaseModel):
    session_id: str
    preferences: Preferences
    threads: list[ThreadSummary]
    created_at: str
    last_seen_at: str


# ── Divers ──
class Feature(BaseModel):
    id: str
    title: str
    status: FeatureStatus


class AppMeta(BaseModel):
    version: str
    regions_count: int
    data_last_updated: str
    features: list[Feature]

"""AGBÉA CLIMAT — schémas Pydantic (miroir de contract/types.ts).

Toute modification d'un schéma se reporte dans contract/types.ts, dans le même commit.
Importer depuis ce paquet : `from backend.schemas import Region, Dataset, ...`
"""
from .ai import (ChatEvent, ChatRequest, ChatResponse, EvData, EvDone, EvError, EvMeta,
                 EvSources, EvStatus, EvToken, ExplainRequest, ExplainResponse)
from .catalog import Dataset, Indicator, LegendStop, MapLayer, Profile
from .common import (FeatureStatus, Granularity, IndicatorId, Lang, Mode, ProfileId, Source,
                     Statement, StatementNature, Trend)
from .envelope import ApiErrorResponse, ApiResponse, ErrorDetail, ok
from .geo import Region
from .meta import AppMeta, Feature
from .observations import (BeforeAfter, Comparison, IndicatorSnapshot, LayerAtDate, PeriodStats,
                           RegionSummary, TimePoint, TimeSeries)
from .sessions import Preferences, Session, ThreadSummary
from .views import AgriInsight, Dashboard

__all__ = [
    "ApiErrorResponse", "ApiResponse", "ErrorDetail", "ok",
    "AgriInsight", "AppMeta", "BeforeAfter", "ChatEvent", "ChatRequest", "ChatResponse",
    "Comparison", "Dashboard", "Dataset", "EvData", "EvDone", "EvError", "EvMeta", "EvSources",
    "EvStatus", "EvToken", "ExplainRequest", "ExplainResponse", "Feature", "FeatureStatus",
    "Granularity", "Indicator", "IndicatorId", "IndicatorSnapshot", "Lang", "LayerAtDate",
    "LegendStop", "MapLayer", "Mode", "PeriodStats", "Preferences", "Profile", "ProfileId",
    "Region", "RegionSummary", "Session", "Source", "Statement", "StatementNature",
    "ThreadSummary", "TimePoint", "TimeSeries", "Trend",
]

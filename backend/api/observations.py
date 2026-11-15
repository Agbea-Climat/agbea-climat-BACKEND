from typing import Literal, Optional

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from backend.schemas import (ApiResponse, BeforeAfter, Comparison, Granularity, IndicatorId, Mode,
                             RegionSummary, TimeSeries, ok)
from backend.services import indicators

router = APIRouter(tags=["observations"])


@router.get("/regions/{region_id}/summary", response_model=ApiResponse[RegionSummary])
def summary(region_id: str, date: Optional[str] = Query(None, description="YYYY-MM ; absent = dernier mois disponible"),
            mode: Mode = "public"):
    return ok(indicators.summary(region_id, date, mode))


@router.get("/regions/{region_id}/timeseries", response_model=ApiResponse[TimeSeries])
def timeseries(region_id: str, indicator: IndicatorId,
               start: Optional[str] = Query(None, description="YYYY-MM ; absent = 5 ans avant la fin"),
               end: Optional[str] = Query(None, description="YYYY-MM ; absent = dernier mois disponible"),
               granularity: Granularity = "month"):
    return ok(indicators.timeseries(region_id, indicator, start, end, granularity))


@router.get("/regions/{region_id}/compare", response_model=ApiResponse[Comparison])
def compare(region_id: str, indicator: IndicatorId,
            a_start: str = "2001", a_end: str = "2010", b_start: str = "2016", b_end: str = "2025"):
    return ok(indicators.compare(region_id, indicator, a_start, a_end, b_start, b_end))


# Fichier téléchargé : pas d'enveloppe
@router.get("/regions/{region_id}/timeseries/export")
def export_timeseries(region_id: str, indicator: IndicatorId, start: Optional[str] = None,
                      end: Optional[str] = None, format: Literal["csv", "json"] = "csv"):
    content, media_type, fname = indicators.export_timeseries(region_id, indicator, start, end, format)
    headers = {"Content-Disposition": f'attachment; filename="{fname}"'}
    return StreamingResponse(iter([content]), media_type=media_type, headers=headers)


@router.get("/layers/{layer_id}/before-after", response_model=ApiResponse[BeforeAfter])
def before_after(layer_id: str, before: str = "2016-09-13", after: str = "2024-09-13",
                 region_id: Optional[str] = None):
    return ok(indicators.before_after(layer_id, before, after, region_id))

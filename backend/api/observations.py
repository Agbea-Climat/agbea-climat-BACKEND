from typing import Literal, Optional

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from backend.schemas import (BeforeAfter, Comparison, Granularity, IndicatorId, Mode,
                             RegionSummary, TimeSeries)
from backend.services import indicators

router = APIRouter(tags=["observations"])


@router.get("/regions/{region_id}/summary", response_model=RegionSummary)
def summary(region_id: str, date: str = "2026-09", mode: Mode = "public"):
    return indicators.summary(region_id, date, mode)


@router.get("/regions/{region_id}/timeseries", response_model=TimeSeries)
def timeseries(region_id: str, indicator: IndicatorId,
               start: str = Query("2020-01"), end: str = Query("2026-10"),
               granularity: Granularity = "month"):
    return indicators.timeseries(region_id, indicator, start, end, granularity)


@router.get("/regions/{region_id}/compare", response_model=Comparison)
def compare(region_id: str, indicator: IndicatorId,
            a_start: str = "2001", a_end: str = "2010", b_start: str = "2016", b_end: str = "2025"):
    return indicators.compare(region_id, indicator, a_start, a_end, b_start, b_end)


@router.get("/regions/{region_id}/timeseries/export")
def export_timeseries(region_id: str, indicator: IndicatorId, start: str = "2020-01",
                      end: str = "2026-10", format: Literal["csv", "json"] = "csv"):
    content, media_type, fname = indicators.export_timeseries(region_id, indicator, start, end, format)
    headers = {"Content-Disposition": f'attachment; filename="{fname}"'}
    return StreamingResponse(iter([content]), media_type=media_type, headers=headers)


@router.get("/layers/{layer_id}/before-after", response_model=BeforeAfter)
def before_after(layer_id: str, before: str = "2016-09-14", after: str = "2026-09-14",
                 region_id: Optional[str] = None):
    return indicators.before_after(layer_id, before, after, region_id)

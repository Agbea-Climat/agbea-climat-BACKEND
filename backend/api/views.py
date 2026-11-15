from typing import Optional

from fastapi import APIRouter

from backend.schemas import AgriInsight, ApiResponse, Dashboard, ok
from backend.services import indicators

router = APIRouter(tags=["views"])


@router.get("/dashboard", response_model=ApiResponse[Dashboard])
def dashboard(date: Optional[str] = None):
    return ok(indicators.dashboard(date))


@router.get("/regions/{region_id}/agriculture", response_model=ApiResponse[AgriInsight])
def agriculture(region_id: str, date: Optional[str] = None):
    return ok(indicators.agriculture(region_id, date))

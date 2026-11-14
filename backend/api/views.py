from fastapi import APIRouter

from backend.schemas import AgriInsight, Dashboard
from backend.services import indicators

router = APIRouter(tags=["views"])


@router.get("/dashboard", response_model=Dashboard)
def dashboard(date: str = "2026-09"):
    return indicators.dashboard(date)


@router.get("/regions/{region_id}/agriculture", response_model=AgriInsight)
def agriculture(region_id: str, date: str = "2026-09"):
    return indicators.agriculture(region_id, date)

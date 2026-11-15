from fastapi import APIRouter

from backend.schemas import ApiResponse, Region, ok
from backend.services import regions

router = APIRouter(tags=["regions"])


@router.get("/regions", response_model=ApiResponse[list[Region]])
def list_regions():
    return ok(regions.list_regions())


# Doit rester déclarée avant /regions/{region_id}
@router.get("/regions/geojson", response_model=ApiResponse[dict])
def regions_geojson():
    return ok(regions.regions_geojson())


@router.get("/regions/{region_id}", response_model=ApiResponse[Region])
def get_region(region_id: str):
    return ok(regions.get_region(region_id))


@router.get("/locate", response_model=ApiResponse[Region])
def locate(lon: float, lat: float):
    return ok(regions.locate(lon, lat))

from fastapi import APIRouter

from backend.schemas import Region
from backend.services import regions

router = APIRouter(tags=["regions"])


@router.get("/regions", response_model=list[Region])
def list_regions():
    return regions.list_regions()


# Doit rester déclarée avant /regions/{region_id}
@router.get("/regions/geojson")
def regions_geojson():
    return regions.regions_geojson()


@router.get("/regions/{region_id}", response_model=Region)
def get_region(region_id: str):
    return regions.get_region(region_id)


@router.get("/locate", response_model=Region)
def locate(lon: float, lat: float):
    return regions.locate(lon, lat)

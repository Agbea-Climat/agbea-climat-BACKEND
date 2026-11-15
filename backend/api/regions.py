from typing import Annotated

from fastapi import APIRouter, Query

from backend.schemas import ApiResponse, Region, RegionFeatureCollection, ok
from backend.services import regions

router = APIRouter(tags=["regions"])

# Bornes géographiques : hors bornes, nan ou inf → 422 validation_error
Lon = Annotated[float, Query(ge=-180, le=180, allow_inf_nan=False, description="Longitude (degrés, WGS 84)")]
Lat = Annotated[float, Query(ge=-90, le=90, allow_inf_nan=False, description="Latitude (degrés, WGS 84)")]


@router.get("/regions", response_model=ApiResponse[list[Region]])
def list_regions():
    return ok(regions.list_regions())


# Doit rester déclarée avant /regions/{region_id}
@router.get("/regions/geojson", response_model=ApiResponse[RegionFeatureCollection])
def regions_geojson():
    return ok(regions.regions_geojson())


@router.get("/regions/{region_id}", response_model=ApiResponse[Region])
def get_region(region_id: str):
    return ok(regions.get_region(region_id))


@router.get("/locate", response_model=ApiResponse[Region], summary="Région du Togo qui contient un point",
            description=(
                "Point dans polygone sur les limites officielles (data/regions.geojson), coordonnées `lon`, `lat` en "
                "degrés WGS 84 (lon ∈ [-180, 180], lat ∈ [-90, 90], nombres finis, sinon 422 `validation_error`).\n\n"
                "- Point hors des contours nationaux → 404 `outside_togo`. **Aucune tolérance sur les frontières "
                "terrestres** (Ghana, Burkina Faso, Bénin).\n"
                "- Seule tolérance : la côte. Un point **en mer à 100 m ou moins du littoral** est rattaché à "
                "`maritime` (le trait de côte officiel ne suit pas la plage au mètre près).\n"
                "- Si `lat` et `lon` inversés tombent dans le Togo, la 404 le suggère dans `response.details` : "
                "`{hint, suggested: {lon, lat}, region_id}`."))
def locate(lon: Lon, lat: Lat):
    return ok(regions.locate(lon, lat))

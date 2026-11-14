"""Régions du Togo : liste, détail, GeoJSON, localisation d'un point.

TODO M06/M07/M09 (après P2) : contours réels depuis data/regions.geojson (shapely),
centroid/bbox/area_km2 calculés, point dans polygone. D'ici là : rectangles mock.
"""
from backend.core.exceptions import NotFound
from backend.schemas import Region

# Ordre : du sud au nord
REGIONS: dict[str, Region] = {
    r.id: r for r in [
        Region(id="maritime", name="Maritime", capital="Lomé", centroid=(1.35, 6.35), bbox=(0.9, 6.1, 1.8, 6.7)),
        Region(id="plateaux", name="Plateaux", capital="Atakpamé", centroid=(1.0, 7.4), bbox=(0.5, 6.6, 1.7, 8.3)),
        Region(id="centrale", name="Centrale", capital="Sokodé", centroid=(1.1, 8.7), bbox=(0.4, 8.2, 1.7, 9.3)),
        Region(id="kara", name="Kara", capital="Kara", centroid=(1.0, 9.7), bbox=(0.3, 9.2, 1.6, 10.2)),
        Region(id="savanes", name="Savanes", capital="Dapaong", centroid=(0.4, 10.6), bbox=(-0.2, 10.1, 1.0, 11.2)),
    ]
}


def list_regions() -> list[Region]:
    return list(REGIONS.values())


def get_region(region_id: str) -> Region:
    if region_id not in REGIONS:
        raise NotFound("region_not_found", f"Région introuvable : {region_id}")
    return REGIONS[region_id]


def regions_geojson() -> dict:
    feats = []
    for r in REGIONS.values():
        x0, y0, x1, y1 = r.bbox
        feats.append({"type": "Feature", "properties": r.model_dump(),
                      "geometry": {"type": "Polygon", "coordinates": [[[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]]}})
    return {"type": "FeatureCollection", "features": feats}


def locate(lon: float, lat: float) -> Region:
    for r in REGIONS.values():
        x0, y0, x1, y1 = r.bbox
        if x0 <= lon <= x1 and y0 <= lat <= y1:
            return r
    raise NotFound("outside_togo", "Point hors du Togo")

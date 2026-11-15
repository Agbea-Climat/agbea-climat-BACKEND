"""Régions du Togo : liste, détail, GeoJSON, localisation d'un point (M06–M09).

Source : data/regions.geojson (livrable P2 : limites officielles, `properties` déjà calculées
par le pipeline — centroid, bbox, area_km2 en UTM 31N). Coordonnées en [lon, lat].
"""
from functools import lru_cache

from shapely.geometry import Point, shape
from shapely.prepared import prep

from backend.core.exceptions import NotFound
from backend.repositories import store
from backend.schemas import Region

# Ordre de l'API : du sud au nord
REGION_IDS = ("maritime", "plateaux", "centrale", "kara", "savanes")
SOUTH = ("maritime", "plateaux")
NORTH = ("centrale", "kara", "savanes")
# Tolérance de /locate pour un point juste sur la frontière simplifiée (~1 km)
LOCATE_TOLERANCE_DEG = 0.01


@lru_cache
def _features() -> dict[str, dict]:
    feats = {f["properties"]["id"]: f for f in store.regions_geojson()["features"]}
    missing = set(REGION_IDS) - set(feats)
    if missing:
        raise store.DataUnavailable("data_unavailable", f"Régions absentes de regions.geojson : {sorted(missing)}")
    return feats


@lru_cache
def _regions() -> dict[str, Region]:
    fields = Region.model_fields
    return {rid: Region(**{k: v for k, v in _features()[rid]["properties"].items() if k in fields})
            for rid in REGION_IDS}


@lru_cache
def _geometries():
    return {rid: shape(_features()[rid]["geometry"]) for rid in REGION_IDS}


@lru_cache
def _prepared():
    return {rid: prep(g) for rid, g in _geometries().items()}


def list_regions() -> list[Region]:
    return list(_regions().values())


def get_region(region_id: str) -> Region:
    region = _regions().get(region_id)
    if region is None:
        raise NotFound("region_not_found", f"Région introuvable : {region_id}")
    return region


def regions_geojson() -> dict:
    """FeatureCollection : `properties` = l'objet Region, géométries réelles."""
    regions = _regions()
    return {"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": regions[rid].model_dump(), "geometry": _features()[rid]["geometry"]}
        for rid in REGION_IDS]}


def locate(lon: float, lat: float) -> Region:
    pt = Point(lon, lat)
    for rid, geom in _prepared().items():
        if geom.contains(pt):
            return _regions()[rid]
    # Point sur la frontière simplifiée (côte, limites) : région la plus proche si très proche
    rid, dist = min(((rid, g.distance(pt)) for rid, g in _geometries().items()), key=lambda x: x[1])
    if dist <= LOCATE_TOLERANCE_DEG:
        return _regions()[rid]
    raise NotFound("outside_togo", "Point hors du Togo")

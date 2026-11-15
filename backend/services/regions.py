"""Régions du Togo : liste, détail, GeoJSON, localisation d'un point (M06–M09).

Source : data/regions.geojson (livrable P2 : limites officielles, `properties` déjà calculées
par le pipeline — centroid, bbox, area_km2 en UTM 31N). Coordonnées en [lon, lat].
"""
from functools import lru_cache
from typing import Optional

from shapely.geometry import LineString, Point, Polygon, shape
from shapely.ops import unary_union
from shapely.prepared import prep

from backend.core.exceptions import NotFound
from backend.repositories import store
from backend.schemas import Region

# Ordre de l'API : du sud au nord
REGION_IDS = ("maritime", "plateaux", "centrale", "kara", "savanes")
SOUTH = ("maritime", "plateaux")
NORTH = ("centrale", "kara", "savanes")
# /locate (M09) — un point hors des contours nationaux est refusé (404 `outside_togo`).
# Seule tolérance : la côte. Un clic en mer à moins de COAST_TOLERANCE_DEG (0,0009° ≈ 100 m à 6° N)
# du littoral est rattaché à la région la plus proche (Maritime) : le trait de côte des limites
# officielles ne suit pas la plage au mètre près. Aucune tolérance sur les frontières terrestres
# (Ghana, Burkina Faso, Bénin).
COAST_TOLERANCE_DEG = 0.0009
# Extrémités du littoral togolais sur le contour national [lon, lat] : frontière du Ghana (Lomé / Aflao)
# et frontière du Bénin (Sanvee Condji / Hilla-Condji). Le littoral = la partie du contour entre ces deux
# sommets, côté sud. Sommets les plus proches recherchés dans data/regions.geojson au chargement.
COAST_ENDS = ((1.1982, 6.1118), (1.6368, 6.2363))


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


@lru_cache
def _national():
    """Contour national (union des régions, petits vides entre régions bouchés), littoral et
    frontières terrestres, en lignes."""
    union = unary_union(list(_geometries().values()))
    main = max(getattr(union, "geoms", [union]), key=lambda p: p.area)
    ring = list(main.exterior.coords)[:-1]
    i, j = sorted(min(range(len(ring)), key=lambda k: Point(ring[k]).distance(Point(end)))
                  for end in COAST_ENDS)
    path_a = ring[i:j + 1]                    # de i à j dans le sens du contour
    path_b = ring[j:] + ring[:i + 1]          # l'autre côté
    # Le littoral est le chemin le plus au sud (latitude moyenne la plus basse)
    coast, land = sorted((path_a, path_b), key=lambda p: sum(c[1] for c in p) / len(p))
    filled = unary_union([Polygon(p.exterior) for p in getattr(union, "geoms", [union])])
    return prep(filled), LineString(coast), LineString(land)


def _find(lon: float, lat: float) -> Optional[str]:
    """Région qui contient le point, ou None s'il est hors du Togo (tolérance : côte seulement)."""
    pt = Point(lon, lat)
    for rid, geom in _prepared().items():
        if geom.covers(pt):                   # intérieur ou limite
            return rid
    filled, coast, land = _national()
    if filled.covers(pt):                     # vide de quelques m² entre deux régions
        return _nearest(pt)
    d_coast = coast.distance(pt)
    if d_coast <= COAST_TOLERANCE_DEG and d_coast < land.distance(pt):
        return _nearest(pt)                   # en mer, tout près de la plage
    return None


def _nearest(pt: Point) -> str:
    return min(_geometries().items(), key=lambda kv: kv[1].distance(pt))[0]


def list_regions() -> list[Region]:
    return list(_regions().values())


def get_region(region_id: str) -> Region:
    region = _regions().get(region_id)
    if region is None:
        raise NotFound("region_not_found", f"Région introuvable : {region_id}")
    return region


def regions_geojson() -> dict:
    """FeatureCollection : `properties` = l'objet Region, géométries réelles, `source` = attribution
    des limites officielles (champ racine de data/regions.geojson)."""
    regions = _regions()
    return {"type": "FeatureCollection", "source": store.regions_geojson().get("source"), "features": [
        {"type": "Feature", "properties": regions[rid].model_dump(), "geometry": _features()[rid]["geometry"]}
        for rid in REGION_IDS]}


def locate(lon: float, lat: float) -> Region:
    """Région du point [lon, lat]. Hors du Togo → 404 `outside_togo` ; si le point inversé
    (lat, lon) tombe dans le Togo, `details` le signale."""
    rid = _find(lon, lat)
    if rid is not None:
        return _regions()[rid]
    details = None
    if -180 <= lat <= 180 and -90 <= lon <= 90:
        swapped = _find(lat, lon)
        if swapped is not None:
            details = {"hint": "lon et lat semblent inversés : l'ordre attendu est lon (longitude), puis lat (latitude)",
                       "suggested": {"lon": lat, "lat": lon}, "region_id": swapped}
    raise NotFound("outside_togo", "Point hors du Togo", details)

"""Unités spatiales d'analyse : pays, régions, préfectures, cantons et sites pilotes.

Deux sources possibles pour pays / régions / préfectures (`settings.yaml → boundaries.admin_source`) :
  map_togo  limites officielles PRISE (geodata.gouv.tg), noms rattachés par le projet MAP TOGO
            → data/reference/map_togo/{country,regions,prefectures}.geojson   (par défaut)
  hdx       COD-AB OCHA 2021 → data/reference/hdx/
Les cantons viennent toujours de HDX ; leur parent est la préfecture qui les recouvre le plus.

Sortie : data/processed/units.gpkg (couche `units`), une ligne par unité avec
  unit_id    identifiant stable : « TG-A » / « TG-A01 » (map_togo), P-code OCHA (hdx), slug pour les sites
  level      country | region | prefecture | canton | site
  name       nom affiché
  parent_id  unité englobante
  hdx_pcode  P-code OCHA équivalent (recouvrement maximal) pour croiser avec d'autres jeux de données
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

from . import config

HDX_FILES = ["tgo_admin0_em.geojson", "tgo_admin1_em.geojson",
             "tgo_admin2_em.geojson", "tgo_admin3_em.geojson"]
UTM = "EPSG:32631"  # UTM 31N, couvre tout le Togo : sert aux tampons et aux surfaces
UNITS_PATH = config.PROCESSED / "units.gpkg"
HDX_DIR = config.DATA / "reference" / "hdx"            # versionné (CC BY-IGO)
MAP_TOGO_DIR = config.DATA / "reference" / "map_togo"  # versionné, voir son README (conditions geodata.gouv.tg)
MAP_TOGO_ATTRIBUTION = "Contenu provenant de la Plateforme Géodata (geodata.gouv.tg) en date du 2026-10-23"


# ----------------------------------------------------------------------------- imports

def import_hdx(source_dir: Path) -> None:
    """Remplace les COD-AB versionnés par ceux d'un autre dossier (ex. nouvelle version HDX)."""
    HDX_DIR.mkdir(parents=True, exist_ok=True)
    for f in HDX_FILES:
        shutil.copy2(source_dir / f, HDX_DIR / f)
    print(f"COD-AB copiés dans {HDX_DIR}")


def import_map_togo(source_dir: Path) -> None:
    """Copie régions et préfectures de MAP TOGO (web/data), ajoute unit_id, et dérive le contour du pays."""
    MAP_TOGO_DIR.mkdir(parents=True, exist_ok=True)
    reg = gpd.read_file(source_dir / "regions.geojson").to_crs(4326)
    pref = gpd.read_file(source_dir / "prefectures.geojson").to_crs(4326)
    reg_code = dict(zip(reg.nom, reg.code))
    reg = reg.assign(unit_id="TG-" + reg.code, parent_id="TG")
    pref = pref.assign(unit_id="TG-" + pref.code, parent_id="TG-" + pref.region.map(reg_code))
    if pref.parent_id.isna().any():
        raise ValueError(f"Préfectures sans région : {pref[pref.parent_id.isna()].nom.tolist()}")
    country = gpd.GeoDataFrame({"unit_id": ["TG"], "nom": ["Togo"], "parent_id": [None]},
                               geometry=[reg.geometry.union_all()], crs=4326)
    for name, g in (("country", country), ("regions", reg), ("prefectures", pref)):
        cols = ["unit_id", "code", "nom", "region", "parent_id", "superficie_km2", "geometry"]
        g[[c for c in cols if c in g.columns]].to_file(MAP_TOGO_DIR / f"{name}.geojson", driver="GeoJSON")
    meta = {"source": MAP_TOGO_ATTRIBUTION, "via": "projet MAP TOGO (noms rattachés aux polygones PRISE)",
            "importe_depuis": str(source_dir), "regions": len(reg), "prefectures": len(pref)}
    (MAP_TOGO_DIR / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"MAP TOGO : {len(reg)} régions, {len(pref)} préfectures + contour du pays → {MAP_TOGO_DIR}")


# ----------------------------------------------------------------------------- lecture

def _read(path: Path, hint: str) -> gpd.GeoDataFrame:
    if not path.exists():
        raise FileNotFoundError(f"{path} manquant. {hint}")
    g = gpd.read_file(path)
    if g.crs is None or g.crs.to_epsg() != 4326:
        g = g.to_crs(4326)
    g["geometry"] = g.geometry.make_valid()
    return g


def _hdx(level: int) -> gpd.GeoDataFrame:
    return _read(HDX_DIR / HDX_FILES[level],
                 "Pour le remplacer : python -m pipeline boundaries --hdx-dir <dossier COD-AB>")


def _map_togo(name: str) -> gpd.GeoDataFrame:
    return _read(MAP_TOGO_DIR / f"{name}.geojson",
                 'Importer : python -m pipeline boundaries --map-togo-dir "D:\\Projects\\MAP TOGO\\web\\data"')


def _best_overlap(units: gpd.GeoDataFrame, ref: gpd.GeoDataFrame, ref_col: str) -> pd.Series:
    """Pour chaque unité, valeur `ref_col` de l'élément de `ref` qui la recouvre le plus."""
    a = units[["geometry"]].to_crs(UTM).reset_index(names="_i")
    b = ref[[ref_col, "geometry"]].to_crs(UTM)
    inter = gpd.overlay(a, b, how="intersection", keep_geom_type=True)
    inter["_a"] = inter.area
    best = inter.sort_values("_a").groupby("_i").tail(1).set_index("_i")[ref_col]
    return best.reindex(range(len(units))).set_axis(units.index)


def _admin_units() -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame, gpd.GeoDataFrame]:
    """(pays, régions, préfectures) avec colonnes unit_id, name, parent_id, hdx_pcode, geometry."""
    src = config.settings().get("boundaries", {}).get("admin_source", "map_togo")
    adm1, adm2 = _hdx(1), _hdx(2)
    if src == "hdx":
        country = gpd.GeoDataFrame({"unit_id": ["TG"], "name": ["Togo"], "parent_id": [None], "hdx_pcode": ["TG"]},
                                   geometry=[_hdx(0).geometry.union_all()], crs=4326)
        reg = gpd.GeoDataFrame({"unit_id": adm1.adm1_pcode, "name": adm1.adm1_name, "parent_id": "TG",
                                "hdx_pcode": adm1.adm1_pcode}, geometry=adm1.geometry, crs=4326)
        pref = gpd.GeoDataFrame({"unit_id": adm2.adm2_pcode, "name": adm2.adm2_name, "parent_id": adm2.adm1_pcode,
                                 "hdx_pcode": adm2.adm2_pcode}, geometry=adm2.geometry, crs=4326)
        return country, reg, pref
    if src != "map_togo":
        raise ValueError(f"boundaries.admin_source inconnu : {src!r} (map_togo | hdx)")
    c, r, p = _map_togo("country"), _map_togo("regions"), _map_togo("prefectures")
    country = gpd.GeoDataFrame({"unit_id": ["TG"], "name": ["Togo"], "parent_id": [None], "hdx_pcode": ["TG"]},
                               geometry=[c.geometry.union_all()], crs=4326)
    reg = gpd.GeoDataFrame({"unit_id": r.unit_id, "name": r.nom, "parent_id": "TG"}, geometry=r.geometry, crs=4326)
    reg["hdx_pcode"] = _best_overlap(reg, adm1, "adm1_pcode")
    pref = gpd.GeoDataFrame({"unit_id": p.unit_id, "name": p.nom, "parent_id": p.parent_id},
                            geometry=p.geometry, crs=4326)
    pref["hdx_pcode"] = _best_overlap(pref, adm2, "adm2_pcode")
    return country, reg, pref


# ----------------------------------------------------------------------------- construction

def build_units() -> gpd.GeoDataFrame:
    country, reg, pref = _admin_units()
    adm3 = _hdx(3)
    cant = gpd.GeoDataFrame({"unit_id": adm3.adm3_pcode, "name": adm3.adm3_name, "hdx_pcode": adm3.adm3_pcode},
                            geometry=adm3.geometry, crs=4326)
    cant["parent_id"] = _best_overlap(cant, pref, "unit_id")
    rows = [country.assign(level="country"), reg.assign(level="region"),
            pref.assign(level="prefecture"), cant.assign(level="canton"), _site_units(country, reg, pref)]
    units = gpd.GeoDataFrame(pd.concat(rows, ignore_index=True), crs=4326)
    units = units[["unit_id", "level", "name", "parent_id", "hdx_pcode", "geometry"]]
    metric = units.to_crs(UTM)
    units["area_km2"] = (metric.area / 1e6).round(2)
    c = metric.centroid.to_crs(4326)
    units["centroid_lon"] = c.x.round(5)
    units["centroid_lat"] = c.y.round(5)
    if units.unit_id.duplicated().any():
        raise ValueError(f"unit_id en double : {units.unit_id[units.unit_id.duplicated()].tolist()}")
    UNITS_PATH.parent.mkdir(parents=True, exist_ok=True)
    units.to_file(UNITS_PATH, layer="units", driver="GPKG")
    src = config.settings().get("boundaries", {}).get("admin_source", "map_togo")
    print(f"{len(units)} unités (limites admin : {src}) → {UNITS_PATH}")
    print(units.groupby("level").size().to_string())
    return units


def _site_units(country, reg, pref) -> gpd.GeoDataFrame:
    cfg = config.sites()
    radius_default = float(cfg.get("default_radius_km", 10))
    togo = country.to_crs(UTM).geometry.union_all()
    recs, geoms = [], []
    for s in cfg["sites"]:
        pt = Point(s["lon"], s["lat"])
        # Préfecture contenant le point → parent. Repli sur la région déclarée.
        hit = pref[pref.contains(pt)]
        parent = hit.unit_id.iloc[0] if len(hit) else None
        if parent is None:
            r = reg[reg.name.str.lower() == str(s["region"]).lower()]
            parent = r.unit_id.iloc[0] if len(r) else "TG"
        r_km = float(s.get("radius_km", radius_default))
        disk = gpd.GeoSeries([pt], crs=4326).to_crs(UTM).buffer(r_km * 1000, resolution=32).iloc[0]
        area = disk.intersection(togo)  # retire la mer et les pays voisins
        geoms.append(gpd.GeoSeries([area], crs=UTM).to_crs(4326).iloc[0])
        recs.append({"unit_id": s["id"], "level": "site", "name": s["name"], "parent_id": parent, "hdx_pcode": None})
    return gpd.GeoDataFrame(recs, geometry=geoms, crs=4326)


def load_units(levels: list[str] | None = None) -> gpd.GeoDataFrame:
    if not UNITS_PATH.exists():
        raise FileNotFoundError(f"{UNITS_PATH} manquant. Lancer : python -m pipeline boundaries")
    u = gpd.read_file(UNITS_PATH, layer="units")
    if levels:
        u = u[u.level.isin(levels)].reset_index(drop=True)
    return u

"""Livrable P2 pour le backend (voir MISSIONS.md → P2 et docs/data/contrat-donnees.md).

  data/regions.geojson            5 régions officielles ; properties.id ∈ maritime, plateaux, centrale, kara, savanes
  data/processed/monthly.parquet  region_id, indicator, date (YYYY-MM), value  (+ valid_frac, dataset_id)
  data/processed/static.json      altitude par région (NASADEM)

Correspondance des noms : notre `rainfall` = `precipitation` côté backend ; `ndvi` et `lst_day` identiques.
Les valeurs viennent telles quelles de data/interim/work/tables/monthly.parquet (même moyenne zonale
pondérée, même masque « moins de 50 % de la zone visible → null »).
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

import geopandas as gpd
import pandas as pd

from . import config
from .analysis import TABLES
from .boundaries import UTM, load_units

# unit_id officiel (MAP TOGO) → identifiant du backend, du sud au nord
REGION_SLUGS = {"TG-A": "maritime", "TG-B": "plateaux", "TG-C": "centrale", "TG-D": "kara", "TG-E": "savanes"}
# repli si boundaries.admin_source = hdx
HDX_SLUGS = {"TG03": "maritime", "TG04": "plateaux", "TG01": "centrale", "TG02": "kara", "TG05": "savanes"}
CAPITALS = {"maritime": "Lomé", "plateaux": "Atakpamé", "centrale": "Sokodé", "kara": "Kara", "savanes": "Dapaong"}
ORDER = ["maritime", "plateaux", "centrale", "kara", "savanes"]

INDICATORS = {"rainfall": "precipitation", "ndvi": "ndvi", "lst_day": "lst_day"}
# identifiants de jeux de données de backend/services/catalog.py
DATASET_IDS = {"precipitation": "gpm_imerg", "ndvi": "modis_ndvi", "lst_day": "modis_lst", "elevation": "srtm"}
ROUND = {"precipitation": 1, "ndvi": 3, "lst_day": 1}   # arrondis de MISSIONS.md (bloc 4)
SIMPLIFY_DEG = 0.0005                                    # ~50 m : fichier léger, contours fidèles


def _regions() -> gpd.GeoDataFrame:
    u = load_units(["region"])
    slugs = {**REGION_SLUGS, **HDX_SLUGS}
    u["id"] = u.unit_id.map(slugs)
    if u.id.isna().any() or set(u.id) != set(ORDER):
        raise ValueError(f"Régions non reconnues : {u[u.id.isna()].unit_id.tolist()}")
    return u.set_index("id").loc[ORDER].reset_index()


def write_regions_geojson(regions: gpd.GeoDataFrame) -> None:
    metric = regions.to_crs(UTM)
    cen = metric.centroid.to_crs(4326)
    g = regions.copy()
    g["geometry"] = g.geometry.simplify(SIMPLIFY_DEG, preserve_topology=True)
    feats = []
    for i, r in g.iterrows():
        minx, miny, maxx, maxy = regions.geometry.iloc[i].bounds
        props = {
            "id": r.id, "name": r["name"], "capital": CAPITALS[r.id],
            "centroid": [round(cen.iloc[i].x, 5), round(cen.iloc[i].y, 5)],
            "bbox": [round(minx, 5), round(miny, 5), round(maxx, 5), round(maxy, 5)],
            "area_km2": round(float(metric.area.iloc[i] / 1e6), 1),
            # traçabilité (ignorées par le schéma Region du backend)
            "unit_id": r.unit_id, "hdx_pcode": r.hdx_pcode,
        }
        feats.append({"type": "Feature", "properties": props, "geometry": r.geometry.__geo_interface__})
    src = config.settings().get("boundaries", {}).get("admin_source", "map_togo")
    fc = {"type": "FeatureCollection",
          "source": ("Contenu provenant de la Plateforme Géodata (geodata.gouv.tg) en date du 2026-10-23, via MAP TOGO"
                     if src == "map_togo" else "OCHA COD-AB Togo (HDX), 2021"),
          "features": feats}
    txt = json.dumps(fc, ensure_ascii=False, separators=(",", ":"))
    # coordonnées à 5 décimales (~1 m) : fichier compact
    import re
    txt = re.sub(r"(-?\d+\.\d{5})\d+", r"\1", txt)
    config.BACKEND_REGIONS.write_text(txt, encoding="utf-8")


def write_monthly(regions: gpd.GeoDataFrame) -> pd.DataFrame:
    m = pd.read_parquet(TABLES / "monthly.parquet")
    to_slug = dict(zip(regions.unit_id, regions.id))
    m = m[m.unit_id.isin(to_slug) & m.indicator.isin(INDICATORS)].copy()
    # value = moyenne des pixels visibles quelle que soit la couverture (value_raw) : le backend a besoin
    # d'une valeur chaque mois (ex. Kara, août : 14 % visible). La faible couverture reste signalée :
    # low_coverage = valid_frac < seuil (0,5) → l'interface doit afficher un avertissement.
    thr = config.settings()["completeness"]["min_valid_fraction_month"]
    out = pd.DataFrame({
        "region_id": m.unit_id.map(to_slug),
        "indicator": m.indicator.map(INDICATORS),
        "date": m.date,
        "value": m.value_raw,
        "valid_frac": m.valid_frac,
        "low_coverage": m.valid_frac < thr,
    })
    out["value"] = [round(v, ROUND[i]) if pd.notna(v) else None for v, i in zip(out.value, out.indicator)]
    out["value"] = out["value"].astype("float64")
    out["dataset_id"] = out.indicator.map(DATASET_IDS)
    out["region_id"] = pd.Categorical(out.region_id, ORDER)
    out = out.sort_values(["region_id", "indicator", "date"]).reset_index(drop=True)
    out["region_id"] = out.region_id.astype(str)
    out.to_parquet(config.BACKEND_PROCESSED / "monthly.parquet", index=False)
    return out


def write_static(regions: gpd.GeoDataFrame) -> dict:
    path = config.API / "tables" / "elevation.parquet"
    if path.exists():
        e = pd.read_parquet(path)
    else:
        from .export import elevation_stats
        e = elevation_stats()
    e = e.set_index("unit_id")
    doc = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "dataset_id": DATASET_IDS["elevation"],
        "units": "m",
        "regions": {},
    }
    for uid, slug in zip(regions.unit_id, regions.id):
        r = e.loc[uid]
        doc["regions"][slug] = {"elevation": {
            "mean": round(float(r["mean"]), 1), "min": round(float(r["min"]), 1), "max": round(float(r["max"]), 1),
            "p10": round(float(r["p10"]), 1), "median": round(float(r["median"]), 1), "p90": round(float(r["p90"]), 1),
            "pct_below_10m": round(float(r["pct_below_10m"]), 2)}}
    (config.BACKEND_PROCESSED / "static.json").write_text(
        json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    return doc


def run() -> None:
    config.BACKEND_PROCESSED.mkdir(parents=True, exist_ok=True)
    regions = _regions()
    write_regions_geojson(regions)
    monthly = write_monthly(regions)
    static = write_static(regions)
    span = monthly.dropna(subset=["value"]).groupby("indicator").date.agg(["min", "max", "count"])
    print(f"P2 → {config.BACKEND_REGIONS.relative_to(config.ROOT)} (5 régions)")
    print(f"P2 → data/processed/monthly.parquet : {len(monthly)} lignes, {monthly.value.isna().sum()} nulles "
          f"(aucun pixel visible), {int(monthly.low_coverage.sum())} en faible couverture (low_coverage)")
    print(span.to_string())
    print(f"P2 → data/processed/static.json : altitude moyenne "
          + ", ".join(f"{k} {v['elevation']['mean']:.0f} m" for k, v in static["regions"].items()))

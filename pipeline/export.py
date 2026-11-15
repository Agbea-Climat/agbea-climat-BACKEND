"""Publication des sorties consommées par le backend : data/api/.

data/api/
  catalog.json                 provenance (jeux de données, indicateurs, référence, couverture réelle)
  units/<niveau>.geojson       géométries simplifiées : country, region, prefecture, canton, site
  tables/*.parquet|csv         monthly, seasonal, climatology, trends, elevation
  summaries/<unit_id>.json     fiche prête à afficher (pays, régions, préfectures, sites)
  layers/<indicateur>/         GeoTIFF : <année>.tif (agrégat annuel), baseline.tif, anomaly_<année>.tif
"""
from __future__ import annotations

import json
import re
import shutil
import warnings
from datetime import date, datetime, timedelta, timezone

import numpy as np
import pandas as pd
from rasterio import features
from rasterio.transform import from_origin

from . import config
from .analysis import CUBES, TABLES, publication_cutoff
from .boundaries import load_units
from .grid import get_grid, read_tif, write_tif
from .zonal import build_weights, zonal_mean

API = config.API
SUMMARY_LEVELS = ("country", "region", "prefecture", "site")
SIMPLIFY = {"country": 0.001, "region": 0.001, "prefecture": 0.0007, "canton": 0.0005, "site": 0.0003}


def _json_default(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return None if np.isnan(o) else float(o)
    if isinstance(o, (date, datetime)):
        return o.isoformat()
    raise TypeError(type(o))


def _clean(v):
    """NaN → None pour un JSON valide."""
    if isinstance(v, float) and np.isnan(v):
        return None
    return v


def _records(df: pd.DataFrame, cols: list[str]) -> list[dict]:
    return [{c: _clean(r[c]) for c in cols} for r in df[cols].to_dict("records")]


def _write_json(path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=1, default=_json_default), encoding="utf-8")


# ----------------------------------------------------------------------------- altitude

def elevation_stats() -> pd.DataFrame:
    path = config.INTERIM / "static" / "elevation.tif"
    if not path.exists():
        return pd.DataFrame()
    g = get_grid("dem")
    dem = read_tif(path)
    units = load_units()
    recs = []
    for uid, geom in zip(units.unit_id, units.geometry):
        minx, miny, maxx, maxy = geom.bounds
        c0 = max(int((minx - g.west) / g.res) - 1, 0)
        c1 = min(int((maxx - g.west) / g.res) + 2, g.width)
        r0 = max(int((g.north - maxy) / g.res) - 1, 0)
        r1 = min(int((g.north - miny) / g.res) + 2, g.height)
        t = from_origin(g.west + c0 * g.res, g.north - r0 * g.res, g.res, g.res)
        # centre du pixel dans l'unité : évite de compter les pixels de mer le long de la côte
        inside = features.geometry_mask([geom], out_shape=(r1 - r0, c1 - c0), transform=t,
                                        invert=True, all_touched=False)
        v = dem[r0:r1, c0:c1][inside]
        v = v[np.isfinite(v)]
        if v.size == 0:
            continue
        recs.append({"unit_id": uid, "mean": round(float(v.mean()), 1), "min": round(float(v.min()), 1),
                     "p10": round(float(np.percentile(v, 10)), 1), "median": round(float(np.median(v)), 1),
                     "p90": round(float(np.percentile(v, 90)), 1), "max": round(float(v.max()), 1),
                     "pct_below_5m": round(float((v < 5).mean() * 100), 2),
                     "pct_below_10m": round(float((v < 10).mean() * 100), 2)})
    return pd.DataFrame(recs)


# ----------------------------------------------------------------------------- pluie 30 jours

def rainfall_30d(clim: pd.DataFrame) -> pd.DataFrame:
    from .sources.imerg import daily_late_stack

    days, stack = daily_late_stack()
    if len(days) < 30:
        return pd.DataFrame()
    days, stack = days[-30:], stack[-30:]
    if (days[-1] - days[0]).days != 29:
        print("  pluie 30 j : jours manquants dans la fenêtre, indicateur non publié")
        return pd.DataFrame()
    total = np.where(np.isfinite(stack).all(axis=0), stack.sum(axis=0), np.nan)
    df = zonal_mean(total, build_weights(get_grid("imerg")))
    # normale : climatologie mensuelle IMERG Final ramenée au jour, sommée sur les 30 jours
    import calendar
    c = clim[clim.indicator == "rainfall"].set_index(["unit_id", "month"]).clim_mean
    normals = []
    for uid in df.unit_id:
        tot = 0.0
        for d in days:
            v = c.get((uid, d.month), np.nan)
            tot += v / calendar.monthrange(d.year, d.month)[1]
        normals.append(tot)
    df["normal_mm"] = np.round(normals, 1)
    df["value"] = df.value.round(1)
    df["anomaly_pct"] = np.where(df.normal_mm > 1, (df.value / df.normal_mm - 1) * 100, np.nan).round(1)
    df["start"], df["end"] = days[0].isoformat(), days[-1].isoformat()
    return df


# ----------------------------------------------------------------------------- couches raster

def build_layers() -> None:
    s = config.settings()
    comp, b = s["completeness"], s["baseline"]
    today = date.today()
    for ind, gname in CUBES.items():
        files = sorted((config.INTERIM / "cubes" / ind).glob("[0-9][0-9][0-9][0-9]-[0-9][0-9].tif"))
        if not files:
            continue
        g = get_grid(gname)
        how = config.datasets()["indicators"][ind]["annual_agg"]
        cutoff = publication_cutoff(ind)
        if cutoff:  # D30 : mois non publiés exclus des couches
            files = [f for f in files if f.stem[:7] <= cutoff]
        need = comp["min_months_annual_sum"] if how == "sum" else comp["min_months_annual_mean"]
        by_year: dict[int, list] = {}
        for f in files:
            y, m = map(int, re.match(r"(\d{4})-(\d{2})", f.stem).groups())
            by_year.setdefault(y, []).append(f)
        out_dir = API / "layers" / ind
        # couches annuelles et anomalies régénérées : on retire les anciennes (années dépubliées)
        for old in list(out_dir.glob("[0-9][0-9][0-9][0-9].tif")) + list(out_dir.glob("anomaly_*.tif")):
            old.unlink()
        annual = {}
        for y, fl in sorted(by_year.items()):
            if y >= today.year or len(fl) < 12:
                continue  # année en cours, ou pas encore entièrement traitée
            st = np.stack([read_tif(f) for f in fl])
            n = np.isfinite(st).sum(axis=0)
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning)
                agg = np.nansum(st, axis=0) if how == "sum" else np.nanmean(st, axis=0)
            agg = np.where(n >= need, agg, np.nan).astype("float32")
            annual[y] = agg
            write_tif(out_dir / f"{y}.tif", g, agg, descriptions=[f"{ind}_{how}_annuel"],
                      tags={"indicator": ind, "year": y, "aggregation": how, "min_months": need})
        base_years = [y for y in annual if b["start_year"] <= y <= b["end_year"]]
        if not base_years:
            continue
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            base = np.nanmean(np.stack([annual[y] for y in base_years]), axis=0).astype("float32")
        write_tif(out_dir / "baseline.tif", g, base, descriptions=[f"{ind}_reference"],
                  tags={"indicator": ind, "baseline": f"{b['start_year']}-{b['end_year']}"})
        last = max(annual)
        anom = (annual[last] - base).astype("float32")
        write_tif(out_dir / f"anomaly_{last}.tif", g, anom, descriptions=[f"{ind}_anomalie_{last}"],
                  tags={"indicator": ind, "year": last, "baseline": f"{b['start_year']}-{b['end_year']}"})
        print(f"  couches {ind} : {len(annual)} années, anomalie {last}")
    dem = config.INTERIM / "static" / "elevation.tif"
    if dem.exists():
        # publié en int16 (mètre près) : ~3× plus léger que le float32 intermédiaire
        a = read_tif(dem)
        a16 = np.where(np.isfinite(a), np.rint(a), -32768).astype("int16")
        write_tif(API / "layers" / "elevation" / "elevation.tif", get_grid("dem"), a16,
                  descriptions=["elevation_m"], nodata=-32768,
                  tags={"source": "NASADEM_HGT v001", "units": "m"})


# ----------------------------------------------------------------------------- catalogue

def build_catalog(monthly: pd.DataFrame) -> dict:
    ds = config.datasets()
    s = config.settings()
    coverage = {}
    for ind, g in monthly.dropna(subset=["value"]).groupby("indicator"):
        coverage[ind] = {"first_month": g.date.min(), "last_month": g.date.max(),
                         "n_months": int(g.date.nunique())}
    cat = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "pipeline_version": config.PIPELINE_VERSION,
        "baseline": f"{s['baseline']['start_year']}-{s['baseline']['end_year']}",
        "seasons": s["seasons"],
        "completeness": s["completeness"],
        "trend_test": {"method": "Mann-Kendall (tau de Kendall) + pente de Theil-Sen", "alpha": s["trend"]["alpha"]},
        "nature_legend": {
            "observed": "Mesuré par un satellite (après contrôle qualité et agrégation).",
            "derived": "Calculé à partir de mesures ou issu d'une réanalyse (modèle + observations).",
            "interpreted": "Ce qu'on en déduit : produit par le backend / l'IA, jamais par ce pipeline.",
            "predicted": "Prévision : hors périmètre, toujours séparé.",
        },
        "datasets": ds["datasets"],
        "indicators": ds["indicators"],
        "coverage": coverage,
    }
    _write_json(API / "catalog.json", cat)
    return cat


# ----------------------------------------------------------------------------- fiches

def _latest(monthly: pd.DataFrame, uid: str, ind: str) -> dict | None:
    g = monthly[(monthly.unit_id == uid) & (monthly.indicator == ind)].dropna(subset=["value"])
    if g.empty:
        return None
    r = g.iloc[-1]
    return {"date": r.date, "value": _clean(r.value), "clim_mean": _clean(r.clim_mean),
            "anomaly": _clean(r.anomaly), "anomaly_pct": _clean(r.anomaly_pct),
            "valid_frac": _clean(r.valid_frac)}


def build_summaries(monthly, season, trends, elev, r30) -> None:
    units = load_units([lvl for lvl in SUMMARY_LEVELS])
    ind_meta = config.datasets()["indicators"]
    out_dir = API / "summaries"
    if out_dir.exists():
        shutil.rmtree(out_dir)
    index = []
    for u in units.itertuples():
        uid = u.unit_id
        latest = {}
        for ind in ("rainfall", "ndvi", "lst_day", "lst_night", "air_temp"):
            v = _latest(monthly, uid, ind)
            if v:
                v.update(unit=ind_meta[ind]["unit"], dataset=ind_meta[ind]["dataset"],
                         nature=ind_meta[ind]["nature"])
                latest[ind] = v
        if len(r30):
            row = r30[r30.unit_id == uid]
            if len(row):
                row = row.iloc[0]
                latest["rainfall_30d"] = {"start": row.start, "end": row.end, "value": _clean(row.value),
                                          "normal": _clean(row.normal_mm), "anomaly_pct": _clean(row.anomaly_pct),
                                          "valid_frac": round(float(row.valid_frac), 3), "unit": "mm",
                                          "dataset": "imerg_daily_late", "nature": "observed",
                                          "normal_note": "normale = climatologie mensuelle IMERG Final ramenée au jour"}
        annual = {}
        for ind, g in season[(season.unit_id == uid) & (season.season == "annual")].groupby("indicator"):
            annual[ind] = _records(g, ["year", "value", "anomaly", "anomaly_pct", "n_months"])
        tr = {}
        for r in trends[trends.unit_id == uid].to_dict("records"):
            tr.setdefault(r["indicator"], {})[r["season"]] = {
                k: _clean(r[k]) for k in ("n_years", "first_year", "last_year", "period_mean",
                                          "sen_slope_per_decade", "sen_ci95_low_per_decade",
                                          "sen_ci95_high_per_decade", "sen_slope_pct_per_decade",
                                          "p_value", "significant", "direction")}
        recent = {}
        for ind, g in monthly[monthly.unit_id == uid].groupby("indicator"):
            recent[ind] = _records(g.tail(24), ["date", "value", "clim_mean", "anomaly", "valid_frac"])
        e = elev[elev.unit_id == uid].drop(columns="unit_id").to_dict("records") if len(elev) else []
        doc = {
            "unit": {"id": uid, "level": u.level, "name": u.name, "parent_id": _clean(u.parent_id),
                     "area_km2": u.area_km2, "centroid": [u.centroid_lon, u.centroid_lat]},
            "elevation_m": e[0] if e else None,
            "latest": latest,
            "annual": annual,
            "trends": tr,
            "recent_monthly": recent,
        }
        _write_json(out_dir / f"{uid}.json", doc)
        index.append({"id": uid, "level": u.level, "name": u.name, "parent_id": _clean(u.parent_id)})
    _write_json(out_dir / "index.json", index)
    print(f"  {len(index)} fiches → {out_dir}")


def build_units_geojson() -> None:
    units = load_units()
    d = API / "units"
    d.mkdir(parents=True, exist_ok=True)
    for lvl, g in units.groupby("level"):
        g = g.copy()
        g["geometry"] = g.geometry.simplify(SIMPLIFY.get(lvl, 0.0005), preserve_topology=True)
        g.to_file(d / f"{lvl}.geojson", driver="GeoJSON", COORDINATE_PRECISION=5)
    print(f"  géométries → {d}")


def run() -> None:
    API.mkdir(parents=True, exist_ok=True)
    t = {n: pd.read_parquet(TABLES / f"{n}.parquet") for n in ("monthly", "seasonal", "climatology", "trends")}
    print("Export backend…")
    elev = elevation_stats()
    r30 = rainfall_30d(t["climatology"])
    tdir = API / "tables"
    tdir.mkdir(parents=True, exist_ok=True)
    extra = {"elevation": elev}
    if len(r30):
        extra["rainfall_30d"] = r30
    for name, df in {**t, **extra}.items():
        df.to_parquet(tdir / f"{name}.parquet", index=False)
        df.to_csv(tdir / f"{name}.csv", index=False, encoding="utf-8")
    build_units_geojson()
    build_catalog(t["monthly"])
    build_summaries(t["monthly"], t["seasonal"], t["trends"], elev, r30)
    build_layers()
    print("Contrôles :")
    from . import validate
    validate.run(t["monthly"], t["seasonal"], t["trends"])
    print(f"Terminé → {API}")

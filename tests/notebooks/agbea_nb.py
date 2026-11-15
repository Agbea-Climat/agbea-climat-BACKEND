"""Outils communs aux notebooks d'exploration des données AGBÉA CLIMAT.

Lecture seule : les notebooks lisent ce que le pipeline a publié (data/api, data/processed,
data/regions.geojson, data/interim/work/controls). Ils ne calculent aucune donnée nouvelle :
ils filtrent, mettent en forme et affichent.
"""
from __future__ import annotations

import json
import math
import os
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd


# ----------------------------------------------------------------------------- chemins

def _find_data() -> Path:
    env = os.environ.get("AGBEA_DATA_DIR")
    if env:
        return Path(env)
    here = Path.cwd().resolve()
    for p in (here, *here.parents):
        if (p / "data" / "api").is_dir():
            return p / "data"
    raise FileNotFoundError("Dossier data/api introuvable. Lancer d'abord : docker compose run --rm pipeline export "
                            "(ou définir AGBEA_DATA_DIR).")


DATA = _find_data()
API = DATA / "api"
LEVELS = ["country", "region", "prefecture", "canton", "site"]
LEVEL_FR = {"country": "Pays", "region": "Région", "prefecture": "Préfecture", "canton": "Canton", "site": "Site pilote"}
SEASON_FR = {"annual": "Année", "jfm": "Janv.-mars (saison sèche)", "mjjaso": "Mai-oct. (saison des pluies)"}
TOGO_CENTER = {"lat": 8.6, "lon": 0.95}

# Échelles de couleur : valeur absolue / écart (centré sur 0)
SCALES = {
    "rainfall": ("Blues", "BrBG"), "rainfall_merra2": ("Blues", "BrBG"),
    "ndvi": ("Greens", "BrBG"),
    "lst_day": ("YlOrRd", "RdBu_r"), "lst_night": ("YlOrRd", "RdBu_r"), "air_temp": ("YlOrRd", "RdBu_r"),
    "elevation": ("Earth", "RdBu_r"),
}


# ----------------------------------------------------------------------------- lecture

@lru_cache(maxsize=None)
def catalog() -> dict:
    return json.loads((API / "catalog.json").read_text(encoding="utf-8"))


@lru_cache(maxsize=None)
def table(name: str) -> pd.DataFrame:
    """Tables complètes de data/api/tables : monthly, seasonal, trends, climatology, elevation, rainfall_30d."""
    return pd.read_parquet(API / "tables" / f"{name}.parquet")


@lru_cache(maxsize=None)
def geojson(level: str) -> dict:
    return json.loads((API / "units" / f"{level}.geojson").read_text(encoding="utf-8"))


@lru_cache(maxsize=None)
def units() -> pd.DataFrame:
    """Une ligne par unité : unit_id, level, name, parent_id, area_km2, centroïde."""
    rows = []
    for lvl in LEVELS:
        p = API / "units" / f"{lvl}.geojson"
        if p.exists():
            rows += [f["properties"] for f in geojson(lvl)["features"]]
    df = pd.DataFrame(rows)
    df["level"] = pd.Categorical(df.level, LEVELS, ordered=True)
    return df.sort_values(["level", "name"]).reset_index(drop=True)


def summary(unit_id: str) -> dict:
    return json.loads((API / "summaries" / f"{unit_id}.json").read_text(encoding="utf-8"))


def summary_or_none(unit_id: str) -> dict | None:
    """Fiche JSON publiée, ou None (le pipeline n'en publie pas pour les cantons)."""
    p = API / "summaries" / f"{unit_id}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def summary_from_tables(unit_id: str) -> dict:
    """Équivalent minimal d'une fiche, lu dans les tables (unités sans fiche JSON)."""
    u = units().set_index("unit_id").loc[unit_id]
    e = table("elevation").set_index("unit_id")
    m = table("monthly")
    m = m[(m.unit_id == unit_id) & m.value.notna()].sort_values("date")
    latest = {}
    for ind, g in m.groupby("indicator"):
        r = g.iloc[-1]
        meta = catalog()["indicators"].get(ind, {})
        latest[ind] = {"date": r.date, "value": r.value, "clim_mean": r.clim_mean, "anomaly": r.anomaly,
                       "anomaly_pct": clean(r.anomaly_pct), "valid_frac": r.valid_frac,
                       "dataset": meta.get("dataset"), "nature": meta.get("nature")}
    return {"unit": {"id": unit_id, "level": u.level, "name": u["name"], "parent_id": clean(u.parent_id),
                     "area_km2": u.area_km2, "centroid": [u.centroid_lon, u.centroid_lat]},
            "elevation_m": e.loc[unit_id].to_dict() if unit_id in e.index else None,
            "latest": latest}


def label(ind: str) -> str:
    meta = catalog()["indicators"].get(ind, {})
    return f"{meta.get('label', ind)} ({meta.get('unit', '')})" if meta.get("unit") else meta.get("label", ind)


def unit_label(unit_id: str) -> str:
    u = units().set_index("unit_id").loc[unit_id]
    return f"{u['name']} ({LEVEL_FR[u.level]})"


def unit_options(levels=("country", "region", "prefecture", "site", "canton")) -> list[tuple[str, str]]:
    """Options (libellé, id) pour un menu déroulant ipywidgets."""
    u = units()
    u = u[u.level.isin(levels)]
    return [(f"{LEVEL_FR[r.level]} — {r['name']}", r.unit_id) for _, r in u.iterrows()]


def clean(v):
    """None pour NaN (affichage)."""
    return None if v is None or (isinstance(v, float) and math.isnan(v)) else v


# ----------------------------------------------------------------------------- calculs d'affichage

def last_complete_year(ind: str, season: str = "annual", level: str | None = None) -> int | None:
    """Dernière année où au moins 90 % des unités (du niveau) ont une valeur pour cette saison."""
    s = table("seasonal")
    s = s[(s.indicator == ind) & (s.season == season)]
    if level:
        s = s[s.unit_id.isin(units().query("level == @level").unit_id)]
    if s.empty:
        return None
    share = s.groupby("year").value.apply(lambda v: v.notna().mean())
    ok = share[share >= 0.9]
    return int(ok.index.max()) if len(ok) else None


def sen_line(years: np.ndarray, values: np.ndarray, slope_per_year: float) -> np.ndarray:
    """Droite de Theil-Sen pour l'affichage : pente du tableau des tendances, ordonnée = médiane des résidus."""
    ok = np.isfinite(values)
    intercept = np.median(values[ok] - slope_per_year * years[ok])
    return intercept + slope_per_year * years


def boundary_lines(level: str) -> tuple[list, list]:
    """Contours d'un niveau en (lon, lat) séparés par None, pour un tracé plotly."""
    xs, ys = [], []
    for f in geojson(level)["features"]:
        g = f["geometry"]
        polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
        for poly in polys:
            for ring in poly:
                xs += [c[0] for c in ring] + [None]
                ys += [c[1] for c in ring] + [None]
    return xs, ys


def human_size(n: int) -> str:
    for unit in ("o", "Ko", "Mo", "Go"):
        if n < 1024:
            return f"{n:.0f} {unit}"
        n /= 1024
    return f"{n:.1f} To"

"""Atlas statique pour le front (étape `export-front`, D32) : ce qu'affichent les notebooks 01 et 02.

Écrit dans <dossier>/atlas/ (par défaut data/api/front/atlas/, ou --front-dir <dépôt front>/public) :
  units/<niveau>.geojson   contours des régions, préfectures, cantons, sites (copie de data/api/units)
  values.json              par zone × indicateur × saison : normale 2001-2020, dernière année complète,
                           écart à la normale, tendance testée (Mann-Kendall + pente de Sen)
  series/<unit_id>.json    séries annuelles et saisonnières d'une zone (graphique de la fiche)
  summaries/<id>.json      fiches existantes (pays, régions, préfectures, sites) : dernières observations
Tous les chiffres viennent de data/api/ (tables seasonal, trends, elevation) : rien n'est recalculé ici,
sauf le choix de la dernière année complète. Indicateurs de contrôle (air_temp, rainfall_merra2) exclus.
"""
from __future__ import annotations

import json
import math
import shutil
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from . import config

INDICATORS = {
    "rainfall": {"label_fr": "Pluie", "label_en": "Rainfall", "unit": "mm", "decimals": 0, "agg": "sum",
                 "dataset": "gpm_imerg"},
    "ndvi": {"label_fr": "Végétation (NDVI)", "label_en": "Vegetation (NDVI)", "unit": "", "decimals": 3,
             "agg": "mean", "dataset": "modis_ndvi"},
    "lst_day": {"label_fr": "Température du sol le jour", "label_en": "Daytime land surface temperature",
                "unit": "°C", "decimals": 1, "agg": "mean", "dataset": "modis_lst"},
    "lst_night": {"label_fr": "Température du sol la nuit", "label_en": "Night-time land surface temperature",
                  "unit": "°C", "decimals": 1, "agg": "mean", "dataset": "modis_lst"},
}
SEASONS = {"annual": {"label_fr": "Année", "label_en": "Year"},
           "jfm": {"label_fr": "Saison sèche (janvier-mars)", "label_en": "Dry season (January-March)"},
           "mjjaso": {"label_fr": "Saison des pluies (mai-octobre)", "label_en": "Rainy season (May-October)"}}
LEVELS = ["country", "region", "prefecture", "canton", "site"]


def _r(x, nd: int):
    """Arrondi JSON (None pour NaN)."""
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return None
    return round(float(x), nd)


def run(front_dir: Path | None = None) -> None:
    api = config.API
    out = (Path(front_dir) if front_dir else api / "front") / "atlas"
    if out.exists():
        shutil.rmtree(out)
    (out / "units").mkdir(parents=True)
    (out / "series").mkdir()
    (out / "summaries").mkdir()

    units: dict[str, dict] = {}
    for lvl in LEVELS:
        src = api / "units" / f"{lvl}.geojson"
        if not src.exists():
            continue
        g = json.loads(src.read_text(encoding="utf-8"))
        for f in g["features"]:
            p = f["properties"]
            units[p["unit_id"]] = {"name": p["name"], "level": p["level"], "parent": p.get("parent_id"),
                                   "area_km2": _r(p.get("area_km2"), 1)}
            f["properties"] = {"id": p["unit_id"], "name": p["name"], "level": p["level"],
                               "parent": p.get("parent_id")}
        (out / "units" / f"{lvl}.geojson").write_text(json.dumps(g, ensure_ascii=False, separators=(",", ":")),
                                                      encoding="utf-8")

    elev = pd.read_parquet(api / "tables" / "elevation.parquet").set_index("unit_id")
    for uid, u in units.items():
        if uid in elev.index:
            e = elev.loc[uid]
            u["elevation"] = {"mean": _r(e["mean"], 0), "min": _r(e["min"], 0), "max": _r(e["max"], 0),
                              "pct_below_10m": _r(e["pct_below_10m"], 1)}

    seas = pd.read_parquet(api / "tables" / "seasonal.parquet")
    seas = seas[seas.indicator.isin(INDICATORS) & seas.unit_id.isin(units)]
    trends = pd.read_parquet(api / "tables" / "trends.parquet")
    trends = trends[trends.indicator.isin(INDICATORS) & trends.unit_id.isin(units)].set_index(
        ["unit_id", "indicator", "season"])

    data: dict[str, dict] = {}
    for (uid, ind, season), g in seas.groupby(["unit_id", "indicator", "season"]):
        nd = INDICATORS[ind]["decimals"] + 1
        g = g.sort_values("year")
        valid = g[g.value.notna()]
        entry = {"base": _r(g.baseline_mean.dropna().iloc[0], nd) if g.baseline_mean.notna().any() else None}
        if not valid.empty:
            last = valid.iloc[-1]
            entry.update({"year": int(last.year), "value": _r(last.value, nd), "anom": _r(last.anomaly, nd),
                          "anom_pct": _r(last.anomaly_pct, 1)})
        if (uid, ind, season) in trends.index:
            t = trends.loc[(uid, ind, season)]
            entry["trend"] = {"slope": _r(t.sen_slope_per_decade, nd + 1), "lo": _r(t.sen_ci95_low_per_decade, nd + 1),
                              "hi": _r(t.sen_ci95_high_per_decade, nd + 1),
                              "pct": _r(t.sen_slope_pct_per_decade, 1), "p": _r(t.p_value, 4),
                              "sig": bool(t.significant), "first": int(t.first_year), "last": int(t.last_year)}
        data.setdefault(uid, {}).setdefault(ind, {})[season] = entry
        # série de la fiche : [année, valeur, écart en %] (valeur nulle = année incomplète)
        series = [[int(y), _r(v, nd), _r(a, 1)] for y, v, a in zip(g.year, g.value, g.anomaly_pct)]
        path = out / "series" / f"{uid}.json"
        cur = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        cur.setdefault(ind, {})[season] = series
        path.write_text(json.dumps(cur, separators=(",", ":")), encoding="utf-8")

    for f in (api / "summaries").glob("*.json"):
        shutil.copy2(f, out / "summaries" / f.name)

    doc = {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "baseline": "2001-2020", "alpha": 0.05,
           "notes_fr": ["Moyennes sur chaque zone, estimées par satellite (NASA).",
                        "Tendances : test de Mann-Kendall au seuil de 5 %, pente de Sen par décennie ; "
                        "en gris si le test n'est pas significatif.",
                        "Température du sol : valeurs jusqu'en décembre 2022, tendances jusqu'en 2020 "
                        "(dérive d'orbite du satellite Terra).",
                        "Cantons : des centaines de tendances sont testées, environ 1 sur 20 peut paraître "
                        "significative par hasard."],
           "indicators": INDICATORS, "seasons": SEASONS, "levels": LEVELS, "units": units, "data": data}
    (out / "values.json").write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    size = sum(p.stat().st_size for p in out.rglob("*") if p.is_file())
    print(f"Atlas front → {out} : {len(units)} zones, {len(data)} avec valeurs, {size / 1e6:.1f} Mo")

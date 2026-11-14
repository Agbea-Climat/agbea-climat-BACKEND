"""Des cubes mensuels aux tables prêtes pour le backend.

Tables produites (format long, une ligne par unité × indicateur × pas de temps) :
  monthly      valeur mensuelle + part valide + anomalie vs climatologie
  seasonal     agrégats annuels / saisonniers (règles de complétude de settings.yaml)
  climatology  moyenne / écart-type / n par mois calendaire sur la période de référence
  trends       Mann-Kendall + pente de Sen sur les agrégats saisonniers
"""
from __future__ import annotations

import re

import numpy as np
import pandas as pd
from scipy import stats as sps

from . import config
from .grid import get_grid, read_tif
from .zonal import build_weights, zonal_mean

# indicateur → grille du cube
CUBES = {"rainfall": "imerg", "ndvi": "ndvi", "lst_day": "lst", "lst_night": "lst"}
TABLES = config.PROCESSED / "tables"


def _indicator_meta(ind: str) -> dict:
    return config.datasets()["indicators"][ind]


# ----------------------------------------------------------------------------- mensuel

def monthly_from_cubes(indicators: list[str] | None = None) -> pd.DataFrame:
    frames = []
    for ind in indicators or CUBES:
        d = config.INTERIM / "cubes" / ind
        files = sorted(d.glob("[0-9][0-9][0-9][0-9]-[0-9][0-9].tif"))
        if not files:
            continue
        w = build_weights(get_grid(CUBES[ind]))
        for f in files:
            y, m = map(int, re.match(r"(\d{4})-(\d{2})", f.stem).groups())
            df = zonal_mean(read_tif(f, 1), w)
            df["indicator"], df["year"], df["month"] = ind, y, m
            frames.append(df)
        print(f"  {ind} : {len(files)} mois agrégés")
    if not frames:
        return pd.DataFrame(columns=["unit_id", "indicator", "year", "month", "value", "valid_frac"])
    return pd.concat(frames, ignore_index=True)


def finalize_monthly(df: pd.DataFrame) -> pd.DataFrame:
    """Masque les mois trop incomplets et ajoute climatologie + anomalies."""
    s = config.settings()
    thr = s["completeness"]["min_valid_fraction_month"]
    df = df.copy()
    # value_raw : moyenne des pixels visibles, quelle que soit la couverture (null seulement si aucun pixel).
    # Sert au livrable P2 du backend, qui signale lui-même la faible couverture (valid_frac).
    df["value_raw"] = df["value"].round(4)
    df.loc[df.valid_frac < thr, "value"] = np.nan
    df["value"] = df["value"].round(4)
    clim = climatology(df)
    df = df.merge(clim[["unit_id", "indicator", "month", "clim_mean", "clim_std"]],
                  on=["unit_id", "indicator", "month"], how="left")
    df["anomaly"] = (df.value - df.clim_mean).round(4)
    rel = df.indicator.isin(["rainfall", "rainfall_merra2"]) & (df.clim_mean > 1)
    df["anomaly_pct"] = np.where(rel, (df.value / df.clim_mean - 1) * 100, np.nan).round(1)
    df["date"] = pd.to_datetime(dict(year=df.year, month=df.month, day=1)).dt.strftime("%Y-%m")
    cols = ["unit_id", "indicator", "date", "year", "month", "value", "value_raw", "valid_frac",
            "clim_mean", "anomaly", "anomaly_pct"]
    df["valid_frac"] = df.valid_frac.round(3)
    return df[cols].sort_values(["indicator", "unit_id", "date"]).reset_index(drop=True)


def climatology(df: pd.DataFrame) -> pd.DataFrame:
    b = config.settings()["baseline"]
    base = df[(df.year >= b["start_year"]) & (df.year <= b["end_year"]) & df.value.notna()]
    g = base.groupby(["unit_id", "indicator", "month"]).value
    clim = g.agg(clim_mean="mean", clim_std="std", n="count").reset_index()
    clim["clim_mean"] = clim.clim_mean.round(4)
    clim["clim_std"] = clim.clim_std.round(4)
    clim["baseline"] = f"{b['start_year']}-{b['end_year']}"
    return clim


# ----------------------------------------------------------------------------- saisons

def _months_needed(how: str, season: str, months: list[int], comp: dict) -> int:
    """Cumul (pluie) : tous les mois. Moyenne : seuil annuel configurable, sinon 1 mois manquant toléré
    pour les saisons de plus de 3 mois (trous nuageux de saison des pluies)."""
    if how == "sum":
        return comp["min_months_annual_sum"] if season == "annual" else len(months)
    if season == "annual":
        return comp["min_months_annual_mean"]
    return len(months) - 1 if len(months) > 3 else len(months)


def _season_over(year: int, months: list[int]) -> bool:
    """Vrai si le dernier mois de la saison est terminé (exclut l'année en cours incomplète)."""
    import datetime as _dt
    today = _dt.date.today()
    return (year, max(months)) < (today.year, today.month)


def seasonal(monthly: pd.DataFrame) -> pd.DataFrame:
    s = config.settings()
    comp = s["completeness"]
    recs = []
    for (uid, ind), g in monthly.groupby(["unit_id", "indicator"]):
        meta = _indicator_meta(ind)
        how = meta.get("annual_agg", "mean")
        by_year = g.set_index(["year", "month"]).value
        for season, months in s["seasons"].items():
            need = _months_needed(how, season, months, comp)
            for y in sorted(g.year.unique()):
                vals = [by_year.get((y, m), np.nan) for m in months]
                vals = np.array(vals, dtype=float)
                n_ok = int(np.isfinite(vals).sum())
                if n_ok < need or not _season_over(int(y), months):
                    v = np.nan
                elif how == "sum":
                    v = float(np.nansum(vals))
                else:
                    v = float(np.nanmean(vals))
                recs.append((uid, ind, season, int(y), v, n_ok, len(months)))
    out = pd.DataFrame(recs, columns=["unit_id", "indicator", "season", "year", "value",
                                      "n_months", "n_months_expected"])
    # anomalie vs moyenne de référence de la même saison
    b = s["baseline"]
    base = out[(out.year >= b["start_year"]) & (out.year <= b["end_year"])]
    ref = base.groupby(["unit_id", "indicator", "season"]).value.mean().rename("baseline_mean")
    out = out.join(ref, on=["unit_id", "indicator", "season"])
    out["anomaly"] = out.value - out.baseline_mean
    rel = out.indicator.isin(["rainfall", "rainfall_merra2"]) & (out.baseline_mean > 1)
    out["anomaly_pct"] = np.where(rel, (out.value / out.baseline_mean - 1) * 100, np.nan)
    for c in ("value", "baseline_mean", "anomaly"):
        out[c] = out[c].round(4)
    out["anomaly_pct"] = out.anomaly_pct.round(1)
    return out.sort_values(["indicator", "unit_id", "season", "year"]).reset_index(drop=True)


# ----------------------------------------------------------------------------- tendances

def mann_kendall_sen(years: np.ndarray, values: np.ndarray, alpha: float) -> dict:
    """Test de Mann-Kendall (via tau de Kendall, correction des ex æquo) + pente de Sen et IC 95 %."""
    ok = np.isfinite(values)
    x, y = years[ok].astype(float), values[ok].astype(float)
    n = int(ok.sum())
    tau, p = sps.kendalltau(x, y)
    slope, intercept, lo, hi = sps.theilslopes(y, x, alpha=0.95)
    return {
        "n_years": n,
        "first_year": int(x.min()), "last_year": int(x.max()),
        "sen_slope_per_year": round(float(slope), 6),
        "sen_slope_per_decade": round(float(slope) * 10, 5),
        "sen_ci95_low_per_decade": round(float(lo) * 10, 5),
        "sen_ci95_high_per_decade": round(float(hi) * 10, 5),
        "kendall_tau": round(float(tau), 4),
        "p_value": round(float(p), 5),
        "significant": bool(p < alpha),
        "direction": "hausse" if (p < alpha and slope > 0) else "baisse" if (p < alpha and slope < 0) else "pas de tendance significative",
    }


def trends(season_df: pd.DataFrame) -> pd.DataFrame:
    s = config.settings()
    min_n, alpha = s["completeness"]["min_years_trend"], s["trend"]["alpha"]
    recs = []
    for (uid, ind, season), g in season_df.groupby(["unit_id", "indicator", "season"]):
        g = g.dropna(subset=["value"])
        if len(g) < min_n:
            continue
        r = mann_kendall_sen(g.year.to_numpy(), g.value.to_numpy(), alpha)
        mean = g.value.mean()
        r.update(unit_id=uid, indicator=ind, season=season,
                 period_mean=round(float(mean), 4),
                 sen_slope_pct_per_decade=round(r["sen_slope_per_decade"] / mean * 100, 2)
                 if ind in ("rainfall", "rainfall_merra2") and mean > 0 else None,
                 method="Mann-Kendall (tau de Kendall) + pente de Theil-Sen",
                 alpha=alpha)
        recs.append(r)
    cols = ["unit_id", "indicator", "season", "n_years", "first_year", "last_year", "period_mean",
            "sen_slope_per_year", "sen_slope_per_decade", "sen_ci95_low_per_decade",
            "sen_ci95_high_per_decade", "sen_slope_pct_per_decade", "kendall_tau", "p_value",
            "significant", "direction", "method", "alpha"]
    return pd.DataFrame(recs, columns=cols)


# ----------------------------------------------------------------------------- orchestration

def run(include_power: bool = True) -> dict[str, pd.DataFrame]:
    from .sources import power  # import local : évite une dépendance réseau au chargement

    print("Agrégation zonale des cubes…")
    raw = monthly_from_cubes()
    if include_power:
        p = power.to_monthly()
        if len(p):
            raw = pd.concat([raw, p], ignore_index=True)
    monthly = finalize_monthly(raw)
    season = seasonal(monthly)
    clim = climatology(monthly)
    tr = trends(season)
    TABLES.mkdir(parents=True, exist_ok=True)
    out = {"monthly": monthly, "seasonal": season, "climatology": clim, "trends": tr}
    for name, df in out.items():
        df.to_parquet(TABLES / f"{name}.parquet", index=False)
    print({k: len(v) for k, v in out.items()})
    return out

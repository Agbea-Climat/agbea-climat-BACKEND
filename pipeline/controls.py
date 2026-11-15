"""Contrôles scientifiques hors livrable : rien de ce module n'est publié dans data/api ni data/processed.

lst_terra_aqua  Les tendances de température de surface (LST) de MODIS Terra sont-elles réelles,
                ou un effet de la dérive d'orbite de Terra ?

Méthode (décision D25) :
1. Terra (MOD11A2) et Aqua (MYD11A2) sont agrégés sur les mêmes unités, puis comparés sur le
   **même échantillon** : un mois n'est gardé que s'il est valide (≥ 50 % visible) chez les deux.
2. Tendances (Mann-Kendall + Sen) de chaque satellite sur deux périodes :
   - 2003-2020 : **période de décision**. Avant la dérive de Terra (dernière manœuvre d'inclinaison
     le 27/02/2020) et celle d'Aqua (dernières manœuvres au printemps 2021). Une tendance y est
     **robuste** si Terra et Aqua la trouvent significative et de même signe.
   - 2003-2025 : diagnostic seulement (`robust` vide). Les deux satellites dérivent : Terra passe plus
     tôt, Aqua plus tard. Le jour, les deux biais refroidissent (une fausse baisse pourrait sortir
     « robuste ») ; la nuit, ils sont de signes opposés.
3. Test direct d'une dérive : tendance de l'écart des anomalies mensuelles Terra − Aqua, moyenné par
   année. Sans dérive, cet écart n'a pas de tendance.

Limite : Aqua ne contrôle pas les erreurs communes aux deux capteurs (même algorithme MODIS C6.1,
émissivité, masque nuageux, biais « ciel clair »).

Prérequis : python -m pipeline lst (Terra) et python -m pipeline lst-aqua (Aqua).
Sorties : data/interim/work/controls/lst_terra_aqua.{parquet,csv} (tendances par satellite)
          et lst_terra_aqua_ecart.{parquet,csv} (tendance de l'écart Terra − Aqua).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import config
from .analysis import finalize_monthly, mann_kendall_sen, monthly_from_cubes, seasonal, trends
from .boundaries import load_units

OUT = config.PROCESSED / "controls"
PAIRS = {"lst_day": "lst_day_aqua", "lst_night": "lst_night_aqua"}
DECISION = (2003, 2020)     # première année complète d'Aqua → dernière année sans dérive
DIAGNOSTIC = (2003, 2025)


def _common_sample(monthly: pd.DataFrame) -> pd.DataFrame:
    """Met à NaN chaque (unité, mois) qui n'est pas valide chez les deux satellites."""
    out = monthly.copy()
    for terra, aqua in PAIRS.items():
        t = out[out.indicator == terra].set_index(["unit_id", "date"]).value
        a = out[out.indicator == aqua].set_index(["unit_id", "date"]).value
        both = t.notna() & a.reindex(t.index).notna()
        ok = set(both[both].index)
        for ind in (terra, aqua):
            sel = out.indicator == ind
            keys = list(zip(out.loc[sel, "unit_id"], out.loc[sel, "date"]))
            out.loc[sel, "value"] = np.where([k in ok for k in keys], out.loc[sel, "value"], np.nan)
    return out


def _trends_on(season: pd.DataFrame, period: tuple[int, int]) -> pd.DataFrame:
    y0, y1 = period
    t = trends(season[(season.year >= y0) & (season.year <= y1)], apply_last_year=False)
    t["period"] = f"{y0}-{y1}"
    return t


def _gap_trend(monthly: pd.DataFrame) -> pd.DataFrame:
    """Tendance de l'écart annuel moyen des anomalies Terra − Aqua (mêmes mois)."""
    s = config.settings()
    alpha, min_months = s["trend"]["alpha"], s["completeness"]["min_months_annual_mean"]
    recs = []
    for terra, aqua in PAIRS.items():
        t = monthly[monthly.indicator == terra].set_index(["unit_id", "year", "month"]).anomaly
        a = monthly[monthly.indicator == aqua].set_index(["unit_id", "year", "month"]).anomaly
        d = (t - a.reindex(t.index)).dropna().reset_index(name="gap")
        ann = d.groupby(["unit_id", "year"]).gap.agg(["mean", "count"])
        ann = ann[ann["count"] >= min_months]["mean"].reset_index()
        for (y0, y1) in (DECISION, DIAGNOSTIC):
            sub = ann[(ann.year >= y0) & (ann.year <= y1)]
            for uid, g in sub.groupby("unit_id"):
                if len(g) < s["completeness"]["min_years_trend"]:
                    continue
                r = mann_kendall_sen(g.year.to_numpy(), g["mean"].to_numpy(), alpha)
                recs.append({"unit_id": uid, "variable": terra, "period": f"{y0}-{y1}",
                             "gap_mean": round(float(g["mean"].mean()), 3),
                             "gap_slope_per_decade": r["sen_slope_per_decade"], "gap_p_value": r["p_value"],
                             "gap_significant": r["significant"], "n_years": r["n_years"]})
    return pd.DataFrame(recs)


def lst_terra_aqua() -> pd.DataFrame:
    inds = [*PAIRS, *PAIRS.values()]
    raw = monthly_from_cubes(inds, cubes={i: "lst" for i in inds}, publication=False)
    missing = sorted(set(inds) - set(raw.indicator))
    if missing:
        raise SystemExit(f"Cubes manquants : {missing}. Lancer d'abord : python -m pipeline lst / lst-aqua")
    monthly = _common_sample(finalize_monthly(raw))
    monthly = monthly[monthly.year >= DECISION[0]]
    season = seasonal(monthly)
    tr = pd.concat([_trends_on(season, DECISION), _trends_on(season, DIAGNOSTIC)], ignore_index=True)

    keep = ["unit_id", "season", "period", "n_years", "sen_slope_per_decade",
            "sen_ci95_low_per_decade", "sen_ci95_high_per_decade", "p_value", "significant"]
    rows = []
    for terra, aqua in PAIRS.items():
        m = tr[tr.indicator == terra][keep].merge(tr[tr.indicator == aqua][keep],
                                                  on=["unit_id", "season", "period"], suffixes=("_terra", "_aqua"))
        m.insert(1, "variable", terra)
        rows.append(m)
    out = pd.concat(rows, ignore_index=True)
    out["same_sign"] = (out.sen_slope_per_decade_terra * out.sen_slope_per_decade_aqua) > 0
    decision = out.period == f"{DECISION[0]}-{DECISION[1]}"
    robust = out.same_sign & out.significant_terra & out.significant_aqua
    out["robust"] = robust.where(decision)          # vide (NaN) hors période de décision

    units = load_units()[["unit_id", "level", "name"]]
    out = units.merge(out, on="unit_id", how="right")
    gap = units.merge(_gap_trend(monthly), on="unit_id", how="right")
    OUT.mkdir(parents=True, exist_ok=True)
    for name, df in (("lst_terra_aqua", out), ("lst_terra_aqua_ecart", gap)):
        df.to_parquet(OUT / f"{name}.parquet", index=False)
        df.to_csv(OUT / f"{name}.csv", index=False, encoding="utf-8")
    _print_summary(out, gap)
    return out


def _print_summary(out: pd.DataFrame, gap: pd.DataFrame) -> None:
    pd.set_option("display.width", 220)
    print(f"\nTendances Terra / Aqua, mêmes mois (robuste = période de décision {DECISION[0]}-{DECISION[1]} seulement) :")
    g = out.groupby(["variable", "season", "period"])
    print(pd.DataFrame({
        "n": g.size(),
        "terra_sig_%": g.significant_terra.mean().mul(100).round(0),
        "aqua_sig_%": g.significant_aqua.mean().mul(100).round(0),
        "meme_signe_%": g.same_sign.mean().mul(100).round(0),
        "robuste_%": g.robust.apply(lambda r: r.dropna().astype(bool).mean() * 100 if r.notna().any() else np.nan).round(0),
        "pente_terra_med": g.sen_slope_per_decade_terra.median().round(2),
        "pente_aqua_med": g.sen_slope_per_decade_aqua.median().round(2),
    }).to_string())
    gg = gap.groupby(["variable", "period"])
    print("\nÉcart Terra − Aqua (anomalies, moyenne annuelle) : une tendance significative signale une dérive")
    print(pd.DataFrame({"n": gg.size(), "ecart_sig_%": gg.gap_significant.mean().mul(100).round(0),
                        "pente_ecart_med": gg.gap_slope_per_decade.median().round(2)}).to_string())
    reg = out[out.level.isin(["region", "site"]) & (out.season == "annual")]
    cols = ["name", "variable", "period", "sen_slope_per_decade_terra", "p_value_terra",
            "sen_slope_per_decade_aqua", "p_value_aqua", "robust"]
    print("\nRégions et sites, moyenne annuelle (°C / décennie) :")
    print(reg.sort_values(["variable", "period", "level", "name"])[cols].to_string(index=False))
    print(f"\n→ {OUT}")

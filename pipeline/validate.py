"""Contrôles automatiques avant publication : plages physiques, couverture, cohérences attendues.

Écrit data/api/validation.json. Un contrôle « fail » n'arrête pas l'export : il est signalé pour
qu'un humain regarde avant la démo.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from . import config

# plages physiquement plausibles au Togo, en moyenne mensuelle sur une zone
RANGES = {
    "rainfall": (0, 900),         # mm/mois
    "rainfall_merra2": (0, 900),
    "ndvi": (-0.2, 0.95),
    "lst_day": (15, 60),          # °C
    "lst_night": (5, 35),
    "air_temp": (15, 40),
}


def _check(name, ok, detail, level="fail"):
    return {"check": name, "status": "pass" if ok else level, "detail": detail}


def run(monthly: pd.DataFrame, seasonal: pd.DataFrame, trends: pd.DataFrame) -> list[dict]:
    out = []
    m = monthly.dropna(subset=["value"])
    for ind, (lo, hi) in RANGES.items():
        g = m[m.indicator == ind]
        if g.empty:
            out.append(_check(f"{ind}: présent", False, "aucune donnée", level="warn"))
            continue
        bad = g[(g.value < lo) | (g.value > hi)]
        out.append(_check(f"{ind}: valeurs dans [{lo}, {hi}]", bad.empty,
                          f"{len(bad)} valeur(s) hors plage sur {len(g)}"
                          + (f", ex. {bad.iloc[0].unit_id} {bad.iloc[0].date} = {bad.iloc[0].value:.2f}" if len(bad) else "")))
        # couverture : part des mois publiés (non null) par indicateur
        tot = monthly[monthly.indicator == ind]
        share = float(tot.value.notna().mean())
        out.append(_check(f"{ind}: mois publiés", share >= 0.7, f"{share:.0%} des mois × unités ont une valeur",
                          level="warn"))

    # cohérences géographiques attendues (gradient sud-nord du Togo)
    ann = seasonal[(seasonal.season == "annual")].dropna(subset=["value"])
    def mean_of(uid, ind):
        v = ann[(ann.unit_id == uid) & (ann.indicator == ind)].value
        return float(v.mean()) if len(v) else np.nan
    nd_s, nd_n = mean_of("kpalime", "ndvi"), mean_of("dapaong", "ndvi")
    if np.isfinite(nd_s) and np.isfinite(nd_n):
        out.append(_check("NDVI Kpalimé (forêt) > Dapaong (savane)", nd_s > nd_n,
                          f"{nd_s:.3f} vs {nd_n:.3f}", level="warn"))
    jfm = seasonal[(seasonal.season == "jfm") & (seasonal.indicator == "lst_day")].dropna(subset=["value"])
    if len(jfm):
        n = jfm[jfm.unit_id == "dapaong"].value.mean()
        s = jfm[jfm.unit_id == "lome"].value.mean()
        if np.isfinite(n) and np.isfinite(s):
            out.append(_check("LST jour saison sèche : Dapaong > Lomé", n > s, f"{n:.1f} °C vs {s:.1f} °C", level="warn"))
    if "rainfall" in set(ann.indicator) and "rainfall_merra2" in set(ann.indicator):
        a = ann[ann.indicator == "rainfall"].groupby("unit_id").value.mean()
        b = ann[ann.indicator == "rainfall_merra2"].groupby("unit_id").value.mean()
        j = pd.concat([a, b], axis=1, keys=["imerg", "merra2"]).dropna()
        if len(j):
            ratio = (j.merra2 / j.imerg)
            worst = ratio.sub(1).abs().idxmax()
            out.append(_check("Pluie annuelle IMERG vs MERRA-2 à ±30 %", bool((ratio.sub(1).abs() <= 0.3).all()),
                              f"pire écart : {worst} (MERRA-2/IMERG = {ratio[worst]:.2f})", level="warn"))
    n_sig = int(trends.significant.sum()) if len(trends) else 0
    out.append(_check("Tendances significatives (information)", True,
                      f"{n_sig} / {len(trends)} séries ; ~5 % attendus par hasard"))

    report = {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
              "summary": {s: sum(c["status"] == s for c in out) for s in ("pass", "warn", "fail")},
              "checks": out}
    p = config.API / "validation.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    for c in out:
        print(f"  [{c['status']:>4}] {c['check']} — {c['detail']}")
    return out

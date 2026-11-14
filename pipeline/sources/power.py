"""NASA POWER (réanalyse MERRA-2) : température de l'air à 2 m et pluie, mensuel, par site.

API sans compte. Le point demandé est le centre du site ; POWER renvoie la maille MERRA-2
(~55 km) qui le contient, ce qui est indiqué dans le catalogue comme limite.
"""
from __future__ import annotations

import calendar
import json
from datetime import date

import pandas as pd
import requests

from .. import config
from .http import USER_AGENT, get_with_retry

URL = "https://power.larc.nasa.gov/api/temporal/monthly/point"
PARAMS = ["T2M", "PRECTOTCORR"]
RAW_DIR = config.RAW / "power"


def fetch(force: bool = False) -> None:
    start = config.settings()["period"]["start_year"]
    end = date.today().year - 1  # l'API mensuelle n'accepte que des années complètes
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    s = requests.Session()
    s.headers["User-Agent"] = USER_AGENT
    for site in config.sites()["sites"]:
        out = RAW_DIR / f"{site['id']}.json"
        if out.exists() and not force:
            continue
        r = get_with_retry(s, URL, params={
            "parameters": ",".join(PARAMS), "community": "AG",
            "longitude": site["lon"], "latitude": site["lat"],
            "start": start, "end": end, "format": "JSON"})
        r.raise_for_status()
        out.write_text(r.text, encoding="utf-8")
        print(f"POWER {site['id']} → {out.name}")


def to_monthly() -> pd.DataFrame:
    """Table longue : unit_id, indicator, year, month, value, valid_frac."""
    recs = []
    for f in sorted(RAW_DIR.glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        fill = d.get("header", {}).get("fill_value", -999)
        p = d["properties"]["parameter"]
        for key, v in p["T2M"].items():
            y, m = int(key[:4]), int(key[4:])
            if m == 13 or v == fill:
                continue
            recs.append((f.stem, "air_temp", y, m, float(v), 1.0))
        for key, v in p["PRECTOTCORR"].items():
            y, m = int(key[:4]), int(key[4:])
            if m == 13 or v == fill:
                continue
            ndays = calendar.monthrange(y, m)[1]
            recs.append((f.stem, "rainfall_merra2", y, m, float(v) * ndays, 1.0))  # mm/jour → mm/mois
    return pd.DataFrame(recs, columns=["unit_id", "indicator", "year", "month", "value", "valid_frac"])

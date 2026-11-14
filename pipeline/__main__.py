"""Ligne de commande : python -m pipeline <étape> [options]

Étapes, dans l'ordre :
  boundaries [--map-togo-dir DIR] [--hdx-dir DIR]
                              unités d'analyse (pays, régions, préfectures, cantons, sites)
  power                       NASA POWER / MERRA-2 (air 2 m, pluie de contrôle) par site
  dem                         NASADEM → altitude ~90 m
  ndvi  [--start Y --end Y]   MODIS MOD13A1 → cubes mensuels NDVI
  lst   [--start Y --end Y]   MODIS MOD11A2 → cubes mensuels LST jour/nuit
  imerg [--start Y --end Y]   GPM IMERG mensuel Final (compte Earthdata requis) → cube pluie
  imerg-daily [--days N]      GPM IMERG journalier Late (compte Earthdata requis) → pluie 30 jours
  analyse                     zonal + mensuel/saisonnier/climatologie/tendances
  export                      publie data/api/ (livrable complet)
  export-backend              livrable P2 du backend : data/regions.geojson, data/processed/{monthly.parquet,static.json}
  all                         tout, dans l'ordre (saute IMERG proprement sans identifiants)
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from . import config


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):  # console Windows en cp1252 : on force l'UTF-8
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    p = argparse.ArgumentParser(prog="pipeline", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("step", choices=["boundaries", "power", "dem", "ndvi", "lst", "imerg",
                                    "imerg-daily", "analyse", "export", "export-backend", "all"])
    p.add_argument("--hdx-dir", type=Path, help="dossier contenant tgo_admin{0..3}_em.geojson")
    p.add_argument("--map-togo-dir", type=Path, help="dossier web/data du projet MAP TOGO (regions/prefectures.geojson)")
    p.add_argument("--start", type=int)
    p.add_argument("--end", type=int)
    p.add_argument("--days", type=int, default=45)
    p.add_argument("--force", action="store_true", help="refait même si les fichiers existent")
    a = p.parse_args(argv)
    config.ensure_dirs()
    t0 = time.time()

    from . import analysis, backend_export, boundaries, export
    from .sources import imerg, modis, nasadem, power

    def step_imerg():
        try:
            imerg.fetch_monthly(a.start, a.end, force=a.force)
        except imerg.CredentialsMissing as e:
            print(f"IMERG ignoré : {e}")
        imerg.build_monthly_cube()

    def step_imerg_daily():
        try:
            imerg.fetch_daily_late(a.days, force=a.force)
        except imerg.CredentialsMissing as e:
            print(f"IMERG journalier ignoré : {e}")

    steps = {
        "boundaries": lambda: (a.hdx_dir and boundaries.import_hdx(a.hdx_dir),
                               a.map_togo_dir and boundaries.import_map_togo(a.map_togo_dir),
                               boundaries.build_units()),
        "power": lambda: power.fetch(force=a.force),
        "dem": lambda: nasadem.fetch(force=a.force),
        "ndvi": lambda: modis.fetch("ndvi", a.start, a.end, force=a.force),
        "lst": lambda: modis.fetch("lst", a.start, a.end, force=a.force),
        "imerg": step_imerg,
        "imerg-daily": step_imerg_daily,
        "analyse": analysis.run,
        "export": export.run,
        "export-backend": backend_export.run,
    }
    order = ["boundaries", "power", "dem", "imerg", "imerg-daily", "ndvi", "lst", "analyse", "export", "export-backend"]
    for name in (order if a.step == "all" else [a.step]):
        print(f"\n=== {name} ===", flush=True)
        steps[name]()
    print(f"\nDurée : {time.time() - t0:.0f} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())

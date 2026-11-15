"""Comblement des trous de la copie Planetary Computer, directement depuis NASA LP DAAC.

Constat du 14/11/2026 : Planetary Computer n'a aucun composite MODIS entre fin juin et mi-novembre
2025, alors que le catalogue NASA (CMR) les a tous. Pour chaque année, on compare les dates du CMR à
celles de Planetary Computer ; les composites manquants sont téléchargés en HDF4 (tuile complète,
pas de sous-ensemble possible) depuis LP DAAC avec le jeton Earthdata, puis lus avec pyhdf.

Géoréférencement : coins de la tuile lus dans StructMetadata.0, projection sinusoïdale MODIS.
"""
from __future__ import annotations

import re
import threading
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import requests
from rasterio.transform import from_bounds as transform_from_bounds
from rasterio.warp import Resampling, reproject

from .. import config
from ..grid import Grid
from .http import EarthdataSession, get_with_retry

CMR = "https://cmr.earthdata.nasa.gov/search/granules.json"
SINUSOIDAL = "+proj=sinu +lon_0=0 +x_0=0 +y_0=0 +R=6371007.181 +units=m +no_defs"
RAW = config.RAW / "modis_hdf"

_hdf_lock = threading.Lock()          # la bibliothèque HDF4 n'est pas sûre en multi-thread
_dl_locks: dict[str, threading.Lock] = {}
_dl_guard = threading.Lock()
_session: EarthdataSession | None = None


def _sess() -> EarthdataSession:
    global _session
    if _session is None:
        _session = EarthdataSession()
    return _session


def cmr_granules(short_name: str, year: int) -> list[tuple[date, str, str]]:
    """[(début du composite, tuile hXXvYY, URL https du .hdf)] pour l'emprise et l'année."""
    b = config.bbox()
    r = get_with_retry(requests.Session(), CMR, params={
        "short_name": short_name, "version": "061", "page_size": 2000,
        "bounding_box": f"{b.west},{b.south},{b.east},{b.north}",
        "temporal": f"{year}-01-01T00:00:00Z,{year}-12-31T23:59:59Z"})
    r.raise_for_status()
    out = []
    for e in r.json()["feed"]["entry"]:
        m = re.match(r"\w+\.A(\d{4})(\d{3})\.(h\d{2}v\d{2})\.", e["title"])
        if not m:
            continue
        start = date(int(m.group(1)), 1, 1) + timedelta(days=int(m.group(2)) - 1)
        href = next((lk["href"] for lk in e.get("links", [])
                     if lk["href"].startswith("https") and lk["href"].endswith(".hdf")), None)
        if href:
            out.append((start, m.group(3), href))
    return out


def _download(href: str) -> Path:
    path = RAW / href.rsplit("/", 2)[-2].split(".")[0] / href.rsplit("/", 1)[-1]
    with _dl_guard:
        lock = _dl_locks.setdefault(str(path), threading.Lock())
    with lock:  # NDVI/QA ou LST jour/nuit partagent le même fichier : un seul téléchargement
        if path.exists():
            return path
        path.parent.mkdir(parents=True, exist_ok=True)
        r = get_with_retry(_sess(), href, timeout=600)
        if r.status_code in (401, 403) or "text/html" in r.headers.get("Content-Type", ""):
            raise RuntimeError("LP DAAC refuse l'accès : vérifier EARTHDATA_TOKEN")
        r.raise_for_status()
        tmp = path.with_suffix(".part")
        tmp.write_bytes(r.content)
        tmp.replace(path)
        return path


def read_reproject(href: str, sds_val: str, sds_qa: str, indicator: str, grid: Grid, masks: dict) -> np.ndarray | None:
    from pyhdf.SD import SD, SDC  # import local : dépendance utilisée seulement pour les trous

    path = _download(href)
    with _hdf_lock:
        f = SD(str(path), SDC.READ)
        try:
            names = f.datasets()
            # Planetary Computer : « 500m_16_days_NDVI » ; HDF4 d'origine : « 500m 16 days NDVI »
            pick = lambda n: n if n in names else n.replace("_", " ")  # noqa: E731
            val = f.select(pick(sds_val))[:]
            qa = f.select(pick(sds_qa))[:]
            sm = f.attributes()["StructMetadata.0"]
        finally:
            f.end()
    ul = [float(x) for x in re.search(r"UpperLeftPointMtrs=\(([^)]+)\)", sm).group(1).split(",")]
    lr = [float(x) for x in re.search(r"LowerRightMtrs=\(([^)]+)\)", sm).group(1).split(",")]
    h, w = val.shape
    transform = transform_from_bounds(ul[0], lr[1], lr[0], ul[1], w, h)
    arr = masks[indicator](val, qa)
    dst = grid.empty()
    reproject(arr, dst, src_transform=transform, src_crs=SINUSOIDAL, dst_transform=grid.transform,
              dst_crs="EPSG:4326", src_nodata=np.nan, dst_nodata=np.nan, resampling=Resampling.nearest)
    return dst if np.isfinite(dst).any() else None

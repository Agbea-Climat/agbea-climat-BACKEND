"""MODIS Terra v061 (NDVI MOD13A1, LST MOD11A2) et Aqua (LST MYD11A2, contrôle seulement) via le STAC de Microsoft Planetary Computer.

Pour chaque composite : lecture de la seule fenêtre « Togo » de chaque tuile sinusoïdale
(h17/h18 × v07/v08), masque qualité, reprojection sur la grille commune EPSG:4326, puis
moyenne mensuelle par pixel. Un mois = composites dont le milieu tombe dans le mois.

Sortie : data/interim/cubes/<indicateur>/AAAA-MM.tif, 2 bandes : moyenne, nb de composites valides.
"""
from __future__ import annotations

import warnings
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import date, datetime, timedelta

import numpy as np
import planetary_computer as pc
import pystac_client
import rasterio
from rasterio.warp import Resampling, reproject, transform_bounds
from rasterio.windows import Window, from_bounds

from .. import config
from ..grid import Grid, get_grid, write_tif

STAC_URL = "https://planetarycomputer.microsoft.com/api/stac/v1"

# rasterio émet cet avertissement sur les tableaux numpy temporaires de reproject() alors que le
# géoréférencement est bien transmis (vérifié : trait de côte, lac Togo — voir notes/).
warnings.filterwarnings("ignore", category=rasterio.errors.NotGeoreferencedWarning)

GDAL_ENV = dict(
    GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR",
    CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif,.TIF,.tiff",
    GDAL_HTTP_MERGE_CONSECUTIVE_RANGES="YES",
    GDAL_HTTP_MULTIPLEX="YES",
    GDAL_HTTP_MAX_RETRY="5",
    GDAL_HTTP_RETRY_DELAY="2",
    VSI_CACHE="TRUE",
)


@dataclass(frozen=True)
class Product:
    key: str                 # nom interne
    collection: str
    id_prefix: str           # MOD = Terra (séries publiées) ; MYD = Aqua (contrôle croisé seulement)
    half_period_days: int    # milieu du composite = début + half_period
    grid: str
    outputs: tuple           # ((indicateur, asset valeur, asset qualité), ...)


NDVI = Product("ndvi", "modis-13A1-061", "MOD13A1", 8, "ndvi",
               (("ndvi", "500m_16_days_NDVI", "500m_16_days_pixel_reliability"),))
LST = Product("lst", "modis-11A2-061", "MOD11A2", 4, "lst",
              (("lst_day", "LST_Day_1km", "QC_Day"), ("lst_night", "LST_Night_1km", "QC_Night")))
# Aqua (passage ~13 h 30 / ~1 h 30 au lieu de ~10 h 30 / ~22 h 30) : sert à vérifier les tendances LST de
# Terra (dérive d'orbite). Jamais publié comme indicateur. Voir pipeline/controls.py.
LST_AQUA = Product("lst_aqua", "modis-11A2-061", "MYD11A2", 4, "lst",
                   (("lst_day_aqua", "LST_Day_1km", "QC_Day"), ("lst_night_aqua", "LST_Night_1km", "QC_Night")))
PRODUCTS = {"ndvi": NDVI, "lst": LST, "lst_aqua": LST_AQUA}


def _cube_dir(indicator: str):
    return config.INTERIM / "cubes" / indicator


# ----------------------------------------------------------------------------- qualité

def _mask_ndvi(val: np.ndarray, rel: np.ndarray) -> np.ndarray:
    """pixel_reliability : 0 = bon, 1 = marginal (gardés) ; -1 vide, 2 neige, 3 nuage (rejetés)."""
    out = val.astype("float32") * 1e-4
    out[(rel < 0) | (rel > 1) | (val < -2000) | (val > 10000)] = np.nan
    return out


def _mask_lst(val: np.ndarray, qc: np.ndarray) -> np.ndarray:
    """QC bits 0-1 : 00 = bonne qualité ; 01 = autre qualité, gardé si erreur LST ≤ 2 K (bits 6-7 ≤ 1)."""
    mandatory = qc & 0b11
    err = (qc >> 6) & 0b11
    keep = (mandatory == 0) | ((mandatory == 1) & (err <= 1))
    out = val.astype("float32") * 0.02 - 273.15
    out[(val == 0) | ~keep] = np.nan
    return out


MASKS = {"ndvi": _mask_ndvi, "lst_day": _mask_lst, "lst_night": _mask_lst,
         "lst_day_aqua": _mask_lst, "lst_night_aqua": _mask_lst}


# ----------------------------------------------------------------------------- lecture

def _read_reproject(href: str, qa_href: str, indicator: str, grid: Grid) -> np.ndarray | None:
    """Lit la fenêtre utile d'une tuile, applique le masque qualité, reprojette sur la grille."""
    b = config.bbox()
    with rasterio.Env(**GDAL_ENV):
        with rasterio.open(pc.sign(href)) as src, rasterio.open(pc.sign(qa_href)) as qsrc:
            sb = transform_bounds("EPSG:4326", src.crs, *b.as_tuple(), densify_pts=51)
            win = from_bounds(*sb, transform=src.transform)
            full = Window(0, 0, src.width, src.height)
            try:
                win = win.intersection(full)
            except Exception:  # noqa: BLE001 — pas d'intersection
                return None
            win = win.round_offsets().round_lengths()
            if win.width < 1 or win.height < 1:
                return None
            val = src.read(1, window=win)
            qa = qsrc.read(1, window=win)
            arr = MASKS[indicator](val, qa)
            dst = grid.empty()
            reproject(arr, dst, src_transform=src.window_transform(win), src_crs=src.crs,
                      dst_transform=grid.transform, dst_crs="EPSG:4326",
                      src_nodata=np.nan, dst_nodata=np.nan, resampling=Resampling.nearest)
            return dst


def _search(product: Product, year: int):
    cat = pystac_client.Client.open(STAC_URL)
    b = config.bbox().as_tuple()
    items = cat.search(collections=[product.collection], bbox=b,
                       datetime=f"{year}-01-01/{year}-12-31").item_collection()
    return [it for it in items if it.id.startswith(product.id_prefix)]


def _lpdaac_gaps(product: Product, year: int, pc_dates: set) -> list[tuple[date, str]]:
    """Composites présents au CMR (NASA) mais absents de Planetary Computer → [(début, URL hdf)]."""
    from . import modis_lpdaac
    from .http import EarthdataSession

    if not EarthdataSession().has_credentials:
        return []
    try:
        granules = modis_lpdaac.cmr_granules(product.id_prefix, year)
    except Exception as e:  # noqa: BLE001 — CMR indisponible : on continue avec Planetary Computer seul
        print(f"  CMR indisponible ({e}) : pas de contrôle des trous pour {year}")
        return []
    return [(start, href) for start, _tile, href in granules if start not in pc_dates]


def _tag(path) -> str:
    with rasterio.open(path) as src:
        return src.tags().get("source", "")


def process_year(product: Product, year: int, force: bool = False) -> int:
    """Construit les cubes mensuels d'une année. Retourne le nombre de mois écrits."""
    from . import modis_lpdaac

    grids = get_grid(product.grid)
    items = _search(product, year)
    by_month: dict[int, list] = defaultdict(list)
    pc_dates = set()
    for it in items:
        start = it.datetime.date() if it.datetime else datetime.fromisoformat(
            it.properties["start_datetime"].replace("Z", "+00:00")).date()
        pc_dates.add(start)
        mid = start + timedelta(days=product.half_period_days)
        if mid.year == year:
            by_month[mid.month].append(("pc", start, it))
    gaps = _lpdaac_gaps(product, year, pc_dates)
    lp_months = set()
    for start, href in gaps:
        mid = start + timedelta(days=product.half_period_days)
        if mid.year == year:
            by_month[mid.month].append(("lp", start, href))
            lp_months.add(mid.month)
    if gaps:
        print(f"  {year} : {len({s for s, _ in gaps})} composite(s) absent(s) de Planetary Computer → LP DAAC",
              flush=True)

    written = 0
    today = date.today()
    for month in sorted(by_month):
        outs = {ind: _cube_dir(ind) / f"{year:04d}-{month:02d}.tif" for ind, _, _ in product.outputs}
        # les 2 derniers mois peuvent encore recevoir des composites : on les refait toujours
        recent = (today.year * 12 + today.month) - (year * 12 + month) <= 1
        # un mois qui a des composites LP DAAC à intégrer est refait s'il ne les contient pas encore
        missing_lp = month in lp_months and not all(p.exists() and "LP DAAC" in _tag(p) for p in outs.values())
        if not force and not recent and not missing_lp and all(p.exists() for p in outs.values()):
            continue
        composites: dict[tuple, dict] = defaultdict(dict)  # (indicateur, date) -> mosaïque
        tasks = []
        for kind, start, obj in by_month[month]:
            for ind, a_val, a_qa in product.outputs:
                if kind == "pc" and a_val in obj.assets and a_qa in obj.assets:
                    tasks.append((ind, start, (_read_reproject, obj.assets[a_val].href, obj.assets[a_qa].href, ind, grids)))
                elif kind == "lp":
                    tasks.append((ind, start, (modis_lpdaac.read_reproject, obj, a_val, a_qa, ind, grids, MASKS)))
        sources = {"Planetary Computer"} | ({"LP DAAC"} if any(k == "lp" for k, _, _ in by_month[month]) else set())
        with ThreadPoolExecutor(config.settings()["network"]["max_workers"]) as ex:
            futs = {ex.submit(fn, *args): (ind, d) for ind, d, (fn, *args) in tasks}
            for fut in as_completed(futs):
                ind, d = futs[fut]
                arr = fut.result()
                if arr is None:
                    continue
                cur = composites[(ind, d)].get("a")
                composites[(ind, d)]["a"] = arr if cur is None else np.where(np.isnan(cur), arr, cur)
        for ind, path in outs.items():
            stack = [v["a"] for (i, _), v in composites.items() if i == ind and "a" in v]
            if not stack:
                continue
            st = np.stack(stack)
            count = np.isfinite(st).sum(axis=0).astype("float32")
            with warnings.catch_warnings():  # pixels sans aucun composite valide → NaN, attendu
                warnings.simplefilter("ignore", RuntimeWarning)
                mean = np.nanmean(st, axis=0).astype("float32")
            write_tif(path, grids, [mean, count], descriptions=[ind, "n_composites_valides"],
                      tags={"source": f"{product.id_prefix} v061 ({' + '.join(sorted(sources))})",
                            "year": year, "month": month, "n_composites": len(stack)})
            written += 1
    return written


def fetch(product_key: str, start_year: int | None = None, end_year: int | None = None,
          force: bool = False) -> None:
    product = PRODUCTS[product_key]
    start_year = start_year or config.settings()["period"]["start_year"]
    end_year = end_year or date.today().year
    for y in range(start_year, end_year + 1):
        t0 = datetime.now()
        n = process_year(product, y, force=force)
        print(f"MODIS {product_key} {y} : {n} cube(s) mensuel(s) écrit(s) en {(datetime.now() - t0).seconds}s",
              flush=True)

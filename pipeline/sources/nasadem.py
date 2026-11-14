"""NASADEM (altitude, mission SRTM 2000) via Planetary Computer, mosaïqué à ~90 m sur l'emprise.

Lecture par les aperçus (overviews) des COG : on ne télécharge pas les tuiles 30 m complètes.
Sortie : data/interim/static/elevation.tif
"""
from __future__ import annotations

import numpy as np
import planetary_computer as pc
import pystac_client
import rasterio
from rasterio.warp import Resampling, reproject

from .. import config
from ..grid import get_grid, write_tif
from .modis import GDAL_ENV, STAC_URL

OUT = config.INTERIM / "static" / "elevation.tif"


def fetch(force: bool = False) -> None:
    if OUT.exists() and not force:
        print(f"{OUT} existe déjà")
        return
    g = get_grid("dem")
    items = pystac_client.Client.open(STAC_URL).search(
        collections=["nasadem"], bbox=config.bbox().as_tuple()).item_collection()
    print(f"NASADEM : {len(items)} tuile(s)")
    mosaic = g.empty()
    with rasterio.Env(**GDAL_ENV):
        for k, it in enumerate(items, 1):
            with rasterio.open(pc.sign(it.assets["elevation"].href)) as src:
                # lecture à ~90 m (facteur 3) via les aperçus, puis reprojection par moyenne
                f = 3
                arr = src.read(1, out_shape=(src.height // f, src.width // f),
                               resampling=Resampling.average).astype("float32")
                if src.nodata is not None:
                    arr[arr == src.nodata] = np.nan
                t = src.transform * src.transform.scale(src.width / arr.shape[1], src.height / arr.shape[0])
                tmp = g.empty()
                reproject(arr, tmp, src_transform=t, src_crs=src.crs, dst_transform=g.transform,
                          dst_crs="EPSG:4326", src_nodata=np.nan, dst_nodata=np.nan,
                          resampling=Resampling.average)
                mosaic = np.where(np.isnan(mosaic), tmp, mosaic)
            print(f"  {k}/{len(items)} {it.id}")
    write_tif(OUT, g, mosaic.astype("float32"), descriptions=["elevation_m"],
              tags={"source": "NASADEM_HGT v001 (Planetary Computer)", "units": "m"})
    print(f"Altitude → {OUT}")

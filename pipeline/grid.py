"""Grilles régulières EPSG:4326 sur l'emprise du Togo et lecture/écriture GeoTIFF.

Toutes les couches d'un même indicateur partagent la même grille : on peut empiler les mois
sans ré-échantillonner et les poids zonaux se calculent une seule fois par grille.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import from_origin

from . import config

CRS = "EPSG:4326"


@dataclass(frozen=True)
class Grid:
    name: str
    res: float
    west: float
    south: float
    east: float
    north: float

    @property
    def width(self) -> int:
        return int(round((self.east - self.west) / self.res))

    @property
    def height(self) -> int:
        return int(round((self.north - self.south) / self.res))

    @property
    def shape(self) -> tuple[int, int]:
        return (self.height, self.width)

    @property
    def transform(self):
        return from_origin(self.west, self.north, self.res, self.res)

    def lon_centers(self) -> np.ndarray:
        return self.west + self.res * (np.arange(self.width) + 0.5)

    def lat_centers(self) -> np.ndarray:
        """Du nord vers le sud (ligne 0 = nord)."""
        return self.north - self.res * (np.arange(self.height) + 0.5)

    def empty(self, fill=np.nan, dtype="float32") -> np.ndarray:
        return np.full(self.shape, fill, dtype=dtype)


def get_grid(name: str) -> Grid:
    b = config.bbox()
    res = float(config.settings()["grids"][name])
    return Grid(name, res, b.west, b.south, b.east, b.north)


def write_tif(path: Path, grid: Grid, bands: list[np.ndarray] | np.ndarray,
              descriptions: list[str] | None = None, tags: dict | None = None,
              nodata=np.nan) -> None:
    """Écrit un GeoTIFF tuilé et compressé (lisible comme COG simple par le backend)."""
    if isinstance(bands, np.ndarray) and bands.ndim == 2:
        bands = [bands]
    path.parent.mkdir(parents=True, exist_ok=True)
    dtype = bands[0].dtype
    profile = dict(
        driver="GTiff", width=grid.width, height=grid.height, count=len(bands),
        dtype=dtype, crs=CRS, transform=grid.transform, nodata=nodata,
        compress="deflate", predictor=3 if np.issubdtype(dtype, np.floating) else 2,
        tiled=True, blockxsize=256, blockysize=256,
    )
    tmp = path.with_suffix(".tmp.tif")
    with rasterio.open(tmp, "w", **profile) as dst:
        for i, b in enumerate(bands, start=1):
            dst.write(b.astype(dtype), i)
            if descriptions:
                dst.set_band_description(i, descriptions[i - 1])
        if tags:
            dst.update_tags(**{k: str(v) for k, v in tags.items()})
    tmp.replace(path)  # écriture atomique : un fichier présent est toujours complet


def read_tif(path: Path, band: int = 1) -> np.ndarray:
    with rasterio.open(path) as src:
        return src.read(band)

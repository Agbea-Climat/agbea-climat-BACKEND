"""Statistiques zonales pondérées par la fraction de chaque pixel couverte par l'unité.

Indispensable pour IMERG (pixels de ~11 km) : un site de 10 km de rayon ne couvre que quelques
mailles, souvent partiellement. Les poids sont calculés par sur-échantillonnage (rastérisation
à une résolution `k` fois plus fine puis moyenne par bloc) et mis en cache par grille.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from rasterio import features
from rasterio.transform import from_origin

from . import config
from .boundaries import UNITS_PATH, load_units
from .grid import Grid

# Facteur de sur-échantillonnage par grille : plus la maille est grosse, plus on affine.
SUPERSAMPLE = {"imerg": 20, "lst": 5, "ndvi": 3, "dem": 1}


def _weights_path(grid: Grid):
    return config.PROCESSED / "weights" / f"{grid.name}_{grid.res:g}.npz"


def build_weights(grid: Grid, units=None) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    """Retourne {unit_id: (indices à plat dans la grille, poids ∈ ]0,1])}."""
    path = _weights_path(grid)
    # cache périmé si les unités (sites, limites) ont été reconstruites depuis
    stale = path.exists() and UNITS_PATH.exists() and UNITS_PATH.stat().st_mtime > path.stat().st_mtime
    if path.exists() and units is None and not stale:
        z = np.load(path, allow_pickle=False)
        ids = [str(x) for x in z["ids"]]
        return {u: (z[f"i_{n}"], z[f"w_{n}"]) for n, u in enumerate(ids)}

    explicit = units is not None
    units = load_units() if units is None else units
    k = SUPERSAMPLE.get(grid.name, 4)
    H, W = grid.shape
    out: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    for uid, geom in zip(units.unit_id, units.geometry):
        if geom is None or geom.is_empty:
            continue
        minx, miny, maxx, maxy = geom.bounds
        # fenêtre de la grille couvrant l'unité (+1 pixel de marge)
        c0 = max(int(np.floor((minx - grid.west) / grid.res)) - 1, 0)
        c1 = min(int(np.ceil((maxx - grid.west) / grid.res)) + 1, W)
        r0 = max(int(np.floor((grid.north - maxy) / grid.res)) - 1, 0)
        r1 = min(int(np.ceil((grid.north - miny) / grid.res)) + 1, H)
        if c1 <= c0 or r1 <= r0:
            continue
        h, w = r1 - r0, c1 - c0
        t = from_origin(grid.west + c0 * grid.res, grid.north - r0 * grid.res, grid.res / k, grid.res / k)
        fine = features.rasterize([(geom, 1)], out_shape=(h * k, w * k), transform=t,
                                  fill=0, dtype="uint8", all_touched=False)
        frac = fine.reshape(h, k, w, k).mean(axis=(1, 3))
        rr, cc = np.nonzero(frac > 0)
        if rr.size == 0:  # unité plus petite qu'un sous-pixel : on prend le pixel du centroïde
            p = geom.representative_point()
            rr = np.array([int((grid.north - p.y) / grid.res) - r0])
            cc = np.array([int((p.x - grid.west) / grid.res) - c0])
            wts = np.array([1.0])
        else:
            wts = frac[rr, cc]
        flat = (rr + r0) * W + (cc + c0)
        out[str(uid)] = (flat.astype(np.int64), wts.astype(np.float32))

    if explicit:  # unités passées à la main (tests) : pas de cache
        return out
    path.parent.mkdir(parents=True, exist_ok=True)
    ids = list(out)
    arrays = {"ids": np.array(ids)}
    for n, u in enumerate(ids):
        arrays[f"i_{n}"], arrays[f"w_{n}"] = out[u]
    np.savez_compressed(path, **arrays)
    return out


def zonal_mean(arr: np.ndarray, weights: dict) -> pd.DataFrame:
    """Moyenne pondérée des pixels valides + part de l'unité couverte par des pixels valides."""
    flat = arr.ravel()
    recs = []
    for uid, (idx, w) in weights.items():
        v = flat[idx]
        ok = np.isfinite(v)
        wsum = float(w.sum())
        wok = float(w[ok].sum())
        value = float(np.dot(v[ok], w[ok]) / wok) if wok > 0 else np.nan
        recs.append((uid, value, wok / wsum if wsum > 0 else 0.0))
    return pd.DataFrame(recs, columns=["unit_id", "value", "valid_frac"])


def zonal_stats(arr: np.ndarray, weights: dict, thresholds: dict[str, float] | None = None) -> pd.DataFrame:
    """Min / max / moyenne / percentiles (pixels touchés à ≥ 50 %) — pour les couches statiques (altitude)."""
    flat = arr.ravel()
    recs = []
    for uid, (idx, w) in weights.items():
        v = flat[idx]
        ok = np.isfinite(v)
        core = ok & (w >= 0.5)
        if not core.any():
            core = ok
        if not ok.any():
            recs.append({"unit_id": uid})
            continue
        r = {
            "unit_id": uid,
            "mean": float(np.dot(v[ok], w[ok]) / w[ok].sum()),
            "min": float(v[core].min()),
            "p10": float(np.percentile(v[core], 10)),
            "median": float(np.median(v[core])),
            "p90": float(np.percentile(v[core], 90)),
            "max": float(v[core].max()),
        }
        for name, thr in (thresholds or {}).items():
            r[name] = float(w[ok][v[ok] < thr].sum() / w[ok].sum() * 100)
        recs.append(r)
    return pd.DataFrame(recs)

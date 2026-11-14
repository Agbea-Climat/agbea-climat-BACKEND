"""NASA GPM IMERG V07 via OPeNDAP (GES DISC) : on ne télécharge que la fenêtre du Togo.

- Mensuel Final Run (GPM_3IMERGM) → séries et tendances. Variable `precipitation` en mm/h
  (taux moyen du mois), converti en cumul mensuel (mm).
- Journalier Late Run (GPM_3IMERGDL) → « pluie des 30 derniers jours » uniquement.

Les noms de fichiers changent avec les sous-versions (V07B, V07C…) : on les découvre en lisant
le listing public du dossier au lieu de les construire.
Un compte NASA Earthdata (gratuit) est nécessaire pour les données ; les listings et métadonnées
(.dmr) sont publics.
"""
from __future__ import annotations

import calendar
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import quote

import h5py
import numpy as np

from .. import config
from ..grid import get_grid, write_tif
from .http import EarthdataSession, get_with_retry

DATA_ROOT = "https://gpm1.gesdisc.eosdis.nasa.gov/data/GPM_L3"
DAP_ROOT = "https://gpm1.gesdisc.eosdis.nasa.gov/opendap/GPM_L3"
MONTHLY = "GPM_3IMERGM.07"
DAILY_LATE = "GPM_3IMERGDL.07"

RAW_M = config.RAW / "imerg_monthly"
RAW_D = config.RAW / "imerg_daily_late"
CUBE = config.INTERIM / "cubes" / "rainfall"


class CredentialsMissing(RuntimeError):
    pass


def _index_window():
    """Indices IMERG (grille globale 0,1°, centres -179.95 + 0.1 i) couvrant l'emprise."""
    g = get_grid("imerg")
    lon, lat = g.lon_centers(), g.lat_centers()
    i = np.rint((lon + 179.95) / 0.1).astype(int)
    j = np.rint((lat + 89.95) / 0.1).astype(int)
    return int(i.min()), int(i.max()), int(j.min()), int(j.max())


def _listing(session, url: str, pattern: str) -> list[str]:
    r = get_with_retry(session, url)
    if r.status_code == 404:
        return []
    r.raise_for_status()
    return sorted(set(re.findall(pattern, r.text)))


def _dap_url(product: str, rel_path: str) -> str:
    i0, i1, j0, j1 = _index_window()
    ce = (f"/precipitation[0:1:0][{i0}:1:{i1}][{j0}:1:{j1}];"
          f"/lon[{i0}:1:{i1}];/lat[{j0}:1:{j1}]")
    return f"{DAP_ROOT}/{product}/{rel_path}.dap.nc4?dap4.ce={quote(ce, safe='/:')}"


def _download(session, url: str, out: Path) -> None:
    r = get_with_retry(session, url, allow_redirects=True)
    ctype = r.headers.get("Content-Type", "")
    if r.status_code in (401, 403) or "text/html" in ctype:
        raise CredentialsMissing(
            "Accès refusé par NASA Earthdata. Vérifier EARTHDATA_TOKEN (ou ~/.netrc) et que "
            "l'application « NASA GESDISC DATA ARCHIVE » est autorisée dans le profil Earthdata.")
    r.raise_for_status()
    if not r.content.startswith(b"\x89HDF"):
        raise RuntimeError(f"Réponse inattendue (pas du netCDF4) pour {url[:120]}…")
    tmp = out.with_suffix(".part")
    tmp.write_bytes(r.content)
    tmp.replace(out)


def read_subset(path: Path) -> tuple[np.ndarray, str]:
    """Lit un sous-ensemble netCDF4 et le renvoie sur la grille `imerg` (nord en haut), + unité."""
    g = get_grid("imerg")
    with h5py.File(path, "r") as f:
        pr = f["precipitation"]
        units = pr.attrs.get("units", b"")
        units = units.decode() if isinstance(units, bytes) else str(units)
        fill = pr.attrs.get("_FillValue", np.array([-9999.9]))
        a = pr[...].astype("float32")
        lon = f["lon"][...]
        lat = f["lat"][...]
    a = a[0]
    if a.shape == (lon.size, lat.size):  # dims (lon, lat) → (lat, lon)
        a = a.T
    a[(a < 0) | (a == np.float32(np.ravel(fill)[0]))] = np.nan
    # Contrôle de géoréférencement : on doit retomber exactement sur la grille de travail.
    if not (np.allclose(lon, g.lon_centers(), atol=1e-3) and np.allclose(np.sort(lat)[::-1], g.lat_centers(), atol=1e-3)):
        raise ValueError(f"{path.name} : coordonnées incompatibles avec la grille imerg")
    if lat[0] < lat[-1]:  # sud → nord dans le fichier : on retourne
        a = a[::-1]
    return a, units


def _to_mm_total(a: np.ndarray, units: str, hours: float) -> np.ndarray:
    u = units.lower().replace(" ", "")
    if u in ("mm/hr", "mm/h", "mmhr-1", "mm/hour"):
        return a * hours
    if u in ("mm/day", "mm/d"):
        return a * hours / 24
    if u in ("mm", "mm/month"):
        return a
    raise ValueError(f"Unité IMERG inattendue : {units!r}")


# --------------------------------------------------------------------------- mensuel (Final)

def fetch_monthly(start_year: int | None = None, end_year: int | None = None, force: bool = False) -> None:
    s = EarthdataSession()
    if not s.has_credentials:
        raise CredentialsMissing(
            "Aucun identifiant NASA Earthdata. Créer un compte sur https://urs.earthdata.nasa.gov, "
            "générer un jeton, puis le mettre dans .env : EARTHDATA_TOKEN=...  (voir docs/acces-donnees.md)")
    start_year = start_year or config.settings()["period"]["start_year"]
    end_year = end_year or date.today().year
    RAW_M.mkdir(parents=True, exist_ok=True)
    todo = []
    for y in range(start_year, end_year + 1):
        names = _listing(s, f"{DATA_ROOT}/{MONTHLY}/{y}/", r"3B-MO\.MS\.MRG\.3IMERG\.\d{8}-S000000-E235959\.\d{2}\.V07[A-Z]\.HDF5")
        for n in names:
            ym = re.search(r"\.(\d{4})(\d{2})01-", n)
            out = RAW_M / f"{ym.group(1)}{ym.group(2)}.nc4"
            if force or not out.exists():
                todo.append((f"{y}/{n}", out))
    print(f"IMERG mensuel : {len(todo)} fichier(s) à télécharger")
    _run_downloads(s, MONTHLY, todo)


def build_monthly_cube() -> int:
    g = get_grid("imerg")
    n = 0
    for f in sorted(RAW_M.glob("*.nc4")):
        y, m = int(f.stem[:4]), int(f.stem[4:])
        out = CUBE / f"{y:04d}-{m:02d}.tif"
        if out.exists() and out.stat().st_mtime >= f.stat().st_mtime:
            continue
        a, units = read_subset(f)
        hours = calendar.monthrange(y, m)[1] * 24
        write_tif(out, g, _to_mm_total(a, units, hours).astype("float32"),
                  descriptions=["precipitation_mm"],
                  tags={"source": "GPM_3IMERGM V07", "units": "mm/month", "year": y, "month": m})
        n += 1
    print(f"Cube pluie : {n} mois écrits dans {CUBE}")
    return n


# --------------------------------------------------------------------------- journalier (Late)

def fetch_daily_late(days: int = 45, force: bool = False) -> None:
    s = EarthdataSession()
    if not s.has_credentials:
        raise CredentialsMissing("Aucun identifiant NASA Earthdata (voir docs/acces-donnees.md).")
    RAW_D.mkdir(parents=True, exist_ok=True)
    today = date.today()
    months = sorted({(d.year, d.month) for d in (today - timedelta(n) for n in range(days + 1))})
    todo = []
    cutoff = (today - timedelta(days)).strftime("%Y%m%d")
    for y, m in months:
        names = _listing(s, f"{DATA_ROOT}/{DAILY_LATE}/{y}/{m:02d}/",
                         r"3B-DAY-L\.MS\.MRG\.3IMERG\.\d{8}-S000000-E235959\.V07[A-Z]\.nc4")
        for n in names:
            d = re.search(r"\.(\d{8})-", n).group(1)
            out = RAW_D / f"{d}.nc4"
            if d >= cutoff and (force or not out.exists()):
                todo.append((f"{y}/{m:02d}/{n}", out))
    print(f"IMERG journalier Late : {len(todo)} fichier(s) à télécharger")
    _run_downloads(s, DAILY_LATE, todo)
    # ménage : on ne garde que la fenêtre glissante
    for f in RAW_D.glob("*.nc4"):
        if f.stem < cutoff:
            f.unlink()


def daily_late_stack() -> tuple[list[date], np.ndarray]:
    """Pile (jours, lat, lon) en mm/jour, triée par date."""
    files = sorted(RAW_D.glob("*.nc4"))
    days, arrs = [], []
    for f in files:
        a, units = read_subset(f)
        arrs.append(_to_mm_total(a, units, 24))
        days.append(date(int(f.stem[:4]), int(f.stem[4:6]), int(f.stem[6:])))
    if not arrs:
        return [], np.empty((0,) + get_grid("imerg").shape, dtype="float32")
    return days, np.stack(arrs)


def _run_downloads(session, product: str, todo: list[tuple[str, Path]]) -> None:
    if not todo:
        return
    workers = min(config.settings()["network"]["max_workers"], 4)  # GES DISC limite le parallélisme
    errors = []
    with ThreadPoolExecutor(workers) as ex:
        futs = {ex.submit(_download, session, _dap_url(product, rel), out): rel for rel, out in todo}
        for k, fut in enumerate(as_completed(futs), 1):
            try:
                fut.result()
            except CredentialsMissing:
                ex.shutdown(cancel_futures=True)
                raise
            except Exception as e:  # noqa: BLE001 — on continue, on liste les échecs à la fin
                errors.append((futs[fut], str(e)[:200]))
            if k % 25 == 0 or k == len(todo):
                print(f"  {k}/{len(todo)}")
    if errors:
        print(f"{len(errors)} échec(s) :")
        for rel, e in errors[:10]:
            print(f"  {rel} : {e}")

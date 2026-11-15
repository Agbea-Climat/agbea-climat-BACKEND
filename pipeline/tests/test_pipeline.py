"""Tests sans réseau : statistiques, poids zonaux, lecture IMERG, règles de saison."""
from __future__ import annotations

import datetime as dt

import h5py
import numpy as np
import pandas as pd
import pytest
from shapely.geometry import box

from pipeline import analysis
from pipeline.grid import Grid, get_grid
from pipeline.sources import imerg
from pipeline.zonal import build_weights, zonal_mean


# ----------------------------------------------------------------------------- tendances

def test_mann_kendall_detects_linear_trend():
    years = np.arange(2001, 2025)
    rng = np.random.default_rng(0)
    values = 0.5 + 0.004 * (years - 2001) + rng.normal(0, 0.005, years.size)
    r = analysis.mann_kendall_sen(years, values, alpha=0.05)
    assert r["significant"] and r["direction"] == "hausse"
    assert r["sen_slope_per_decade"] == pytest.approx(0.04, abs=0.01)
    assert r["sen_ci95_low_per_decade"] <= r["sen_slope_per_decade"] <= r["sen_ci95_high_per_decade"]


def test_mann_kendall_noise_is_not_significant():
    years = np.arange(2001, 2025)
    values = np.random.default_rng(1).normal(1000, 100, years.size)
    r = analysis.mann_kendall_sen(years, values, alpha=0.05)
    assert not r["significant"]
    assert r["direction"] == "pas de tendance significative"


def test_mann_kendall_ignores_nan():
    years = np.arange(2001, 2021).astype(float)
    values = years.copy()
    values[[3, 7]] = np.nan
    assert analysis.mann_kendall_sen(years, values, 0.05)["n_years"] == 18


# ----------------------------------------------------------------------------- poids zonaux

class _Units:
    """Remplace le GeoDataFrame des unités pour build_weights()."""
    def __init__(self, ids, geoms):
        self.unit_id, self.geometry = ids, geoms


def test_weights_fraction_of_partially_covered_cell(tmp_path, monkeypatch):
    monkeypatch.setattr("pipeline.config.PROCESSED", tmp_path)
    g = Grid("imerg", 1.0, 0.0, 0.0, 2.0, 2.0)  # 2 x 2 cellules de 1°
    # unité couvrant toute la cellule NO et la moitié gauche de la cellule NE
    w = build_weights(g, _Units(["u"], [box(0, 1, 1.5, 2)]))
    idx, wts = w["u"]
    got = dict(zip(idx.tolist(), np.round(wts, 2).tolist()))
    assert got == {0: 1.0, 1: 0.5}


def test_zonal_mean_weighted_and_valid_fraction():
    weights = {"u": (np.array([0, 1]), np.array([1.0, 0.5], dtype="float32"))}
    arr = np.array([[10.0, 40.0], [0, 0]], dtype="float32")
    r = zonal_mean(arr, weights).iloc[0]
    assert r.value == pytest.approx((10 * 1 + 40 * 0.5) / 1.5)
    assert r.valid_frac == pytest.approx(1.0)
    arr[0, 1] = np.nan
    r = zonal_mean(arr, weights).iloc[0]
    assert r.value == pytest.approx(10.0)
    assert r.valid_frac == pytest.approx(1 / 1.5)


# ----------------------------------------------------------------------------- IMERG

def _fake_imerg(path, units="mm/hr", lat_ascending=True):
    g = get_grid("imerg")
    lon = g.lon_centers().astype("float32")
    lat = g.lat_centers()[::-1].astype("float32") if lat_ascending else g.lat_centers().astype("float32")
    # valeur = indice de latitude dans le fichier → permet de vérifier l'orientation
    data = np.tile(np.arange(lat.size, dtype="float32"), (lon.size, 1))[None]  # (time, lon, lat)
    data[0, 0, 0] = -9999.9
    with h5py.File(path, "w") as f:
        f["lon"], f["lat"] = lon, lat
        d = f.create_dataset("precipitation", data=data)
        d.attrs["units"] = units.encode()
        d.attrs["_FillValue"] = np.array([-9999.9], dtype="float32")
    return lat


def test_imerg_window_matches_grid():
    i0, i1, j0, j1 = imerg._index_window()
    g = get_grid("imerg")
    assert (i1 - i0 + 1, j1 - j0 + 1) == (g.width, g.height)
    assert -179.95 + 0.1 * i0 == pytest.approx(g.lon_centers()[0])
    assert -89.95 + 0.1 * j1 == pytest.approx(g.lat_centers()[0])


def test_imerg_read_subset_orients_north_up_and_masks_fill(tmp_path):
    lat = _fake_imerg(tmp_path / "m.nc4")
    a, units = imerg.read_subset(tmp_path / "m.nc4")
    g = get_grid("imerg")
    assert a.shape == g.shape and units == "mm/hr"
    # ligne 0 = latitude la plus au nord = dernier indice du fichier (croissant)
    assert a[0, 1] == lat.size - 1 and a[-1, 1] == 0
    assert np.isnan(a[-1, 0])  # la valeur de remplissage est masquée


def test_imerg_unit_conversion():
    one = np.ones((2, 2), dtype="float32")
    assert imerg._to_mm_total(one, "mm/hr", 744)[0, 0] == 744
    assert imerg._to_mm_total(one, "mm/day", 24)[0, 0] == 1
    with pytest.raises(ValueError):
        imerg._to_mm_total(one, "kg m-2 s-1", 24)


# ----------------------------------------------------------------------------- saisons

def test_season_over_excludes_current_year():
    today = dt.date.today()
    assert analysis._season_over(today.year - 1, [12])
    assert not analysis._season_over(today.year, [today.month])


def test_annual_rainfall_requires_12_months(monkeypatch):
    rows = [("u", "rainfall", 2010, m, 100.0) for m in range(1, 13)]
    rows += [("u", "rainfall", 2011, m, 100.0) for m in range(1, 12)]  # décembre manquant
    df = pd.DataFrame(rows, columns=["unit_id", "indicator", "year", "month", "value"])
    s = analysis.seasonal(df)
    ann = s[s.season == "annual"].set_index("year").value
    assert ann[2010] == 1200 and np.isnan(ann[2011])


def _season_rows(ind, years):
    return pd.DataFrame({"unit_id": "u", "indicator": ind, "season": "annual", "year": years,
                         "value": 20 + 0.05 * (years - years[0])})


def test_lst_trends_stop_at_last_year():
    """D27 : tendances LST coupées à trend.last_year (dérive de Terra) ; la pluie n'est pas coupée ;
    les contrôles (apply_last_year=False) gardent toute la série."""
    years = np.arange(2001, 2026)
    df = pd.concat([_season_rows("lst_night", years), _season_rows("rainfall", years)], ignore_index=True)
    t = analysis.trends(df).set_index("indicator")
    assert t.loc["lst_night", "last_year"] == 2020
    assert t.loc["rainfall", "last_year"] == 2025
    full = analysis.trends(df, apply_last_year=False).set_index("indicator")
    assert full.loc["lst_night", "last_year"] == 2025


def test_expected_composites_per_month():
    assert analysis.expected_composites(8, 2026, 10) == 4     # LST 8 jours
    assert analysis.expected_composites(16, 2026, 10) == 2    # NDVI 16 jours
    assert sum(analysis.expected_composites(8, 2025, m) for m in range(1, 13)) == 46


def test_incomplete_months_are_dropped():
    today = dt.date(2026, 11, 14)
    assert analysis.month_incomplete(2026, 11, 1, 8, today) == "mois en cours"
    assert analysis.month_incomplete(2026, 10, 3, 8, today) == "3/4 composites"
    assert analysis.month_incomplete(2026, 10, 4, 8, today) is None
    assert analysis.month_incomplete(2026, 10, None, None, today) is None   # IMERG : pas de composites
    assert analysis.month_incomplete(2026, 8, 3, 8, today) is None          # lacune ancienne : gardée


# ----------------------------------------------------------------------------- MODIS HDF4 (LP DAAC)

def test_lpdaac_hdf4_georeferencing(tmp_path, monkeypatch):
    """Une tuile h18v08 factice (NDVI = 0,5 partout) doit couvrir Lomé et pas Dapaong (tuile v07)."""
    pytest.importorskip("pyhdf")
    from pyhdf.SD import SD, SDC
    from pipeline.sources import modis, modis_lpdaac

    path = tmp_path / "MOD13A1.A2025209.h18v08.061.x.hdf"
    f = SD(str(path), SDC.WRITE | SDC.CREATE)
    n = 240  # 10x plus grossier que la vraie tuile, même emprise
    v = f.create("NDVI", SDC.INT16, (n, n)); v[:] = np.full((n, n), 5000, dtype="int16"); v.endaccess()
    q = f.create("QA", SDC.INT8, (n, n)); q[:] = np.zeros((n, n), dtype="int8"); q.endaccess()
    f.attr("StructMetadata.0").set(SDC.CHAR8, "UpperLeftPointMtrs=(0.000000,1111950.519767)\n"
                                              "LowerRightMtrs=(1111950.519767,0.000000)\n")
    f.end()
    monkeypatch.setattr(modis_lpdaac, "_download", lambda href: path)
    g = get_grid("ndvi")
    arr = modis_lpdaac.read_reproject("x", "NDVI", "QA", "ndvi", g, modis.MASKS)
    r_lome, c_lome = int((g.north - 6.2) / g.res), int((1.2 - g.west) / g.res)
    r_dap, c_dap = int((g.north - 10.86) / g.res), int((0.21 - g.west) / g.res)
    assert arr[r_lome, c_lome] == pytest.approx(0.5)
    assert np.isnan(arr[r_dap, c_dap])          # au nord de 10° N : tuile v07
    assert np.isnan(arr[r_lome, int((-0.2 - g.west) / g.res)])  # à l'ouest de 0° : tuile h17


def test_publication_cutoff_lst():
    """D30 : LST publiée jusqu'en 2022-12 (dérive d'orbite) ; pluie et NDVI sans coupure."""
    assert analysis.publication_cutoff("lst_day") == "2022-12"
    assert analysis.publication_cutoff("lst_night") == "2022-12"
    assert analysis.publication_cutoff("rainfall") is None
    assert analysis.publication_cutoff("ndvi") is None


def test_corpus_fiche_format():
    """Étape corpus (D31) : nombres au format français, tendance seulement si significative, pas de « -0,0 »."""
    from pipeline import corpus
    assert corpus.fr(-0.04, 1) == "0,0" and corpus.fr(1234.5, 1) == "1234,5"
    s = {"unit": {"id": "X", "level": "prefecture", "name": "Test", "parent_id": "TG-A", "area_km2": 100.0,
                  "centroid": [1.2, 6.2]},
         "elevation_m": {"mean": 20.0, "min": 1.0, "max": 50.0, "pct_below_10m": 12.0},
         "trends": {"rainfall": {"annual": {"first_year": 2001, "last_year": 2024, "significant": False,
                                            "sen_slope_per_decade": 5.0}},
                    "lst_night": {"annual": {"first_year": 2001, "last_year": 2020, "significant": True,
                                             "sen_slope_per_decade": 0.8, "sen_ci95_low_per_decade": 0.5,
                                             "sen_ci95_high_per_decade": 1.1}}},
         "latest": {}}
    idx = {"TG-A": {"id": "TG-A", "level": "region", "name": "Maritime", "parent_id": "TG"}}
    txt = corpus.fiche(s, idx, pd.DataFrame(columns=["indicator", "month", "clim_mean"]), "2026-11-15")
    assert "hausse de 0,80 °C par décennie" in txt
    assert "Pas de tendance significative pour : pluie (sur l'année, 2001-2024)" in txt
    assert "((" not in txt and "ANAMET" in txt
    assert corpus.region_slugs(s["unit"], idx) == ["maritime"]

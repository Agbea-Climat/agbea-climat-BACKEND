"""Corrections du rapport notes/2026-11-15_tests-api.md (points 1, 4, 9, 10, 15–19) : dates par
indicateur, conseils sans donnée, années incomplètes, faible couverture, arrondis, bornes."""
import math

import pandas as pd
import pytest

from conftest import API, DATA, data, err_code

DS = {"precipitation": "ds:gpm_imerg", "ndvi": "ds:modis_ndvi", "lst_day": "ds:modis_lst"}


@pytest.fixture(scope="module")
def df():
    return pd.read_parquet(DATA / "processed" / "monthly.parquet")


@pytest.fixture(scope="module")
def last(df):
    return df[df.value.notna()].groupby("indicator").date.max().to_dict()


def _base(df, region, ind, month):
    s = df[(df.region_id == region) & (df.indicator == ind) & (df.date.str[5:7] == f"{month:02d}")
           & df.date.str[:4].astype(int).between(2001, 2020)].value.dropna()
    return math.fsum(float(x) for x in s) / len(s)


# ── 1 · chaque snapshot garde sa date, le texte la cite ──
@pytest.mark.m14
@pytest.mark.real_data
def test_summary_without_date_dates_each_value(client, last):
    s = data(client.get(f"{API}/regions/maritime/summary"))
    assert s["date"] == max(last.values())
    for snap in s["indicators"]:
        assert snap["date"] == last[snap["indicator"]]
        if snap["date"] != s["date"]:
            assert snap["date"][:4] in snap["plain_summary"] and "dernier mois disponible" in snap["plain_summary"]


@pytest.mark.m20
@pytest.mark.real_data
def test_agriculture_same_month_for_season_and_rain(client, last):
    a = data(client.get(f"{API}/regions/savanes/agriculture"))
    if last["precipitation"] < a["date"]:
        assert a["rainfall_status"] == "unknown"
        assert not any(s["nature"] == "interpreted" and DS["precipitation"] in s["source_ids"]
                       for s in a["statements"])


# ── 4 · aucune donnée → aucun conseil fondé sur elle ; sources cohérentes ──
@pytest.mark.m20
@pytest.mark.real_data
@pytest.mark.parametrize("region,date", [("maritime", "2026-10"), ("savanes", "2024-07"),
                                         ("kara", "2024-11"), ("plateaux", "2025-01"), ("centrale", "2024-08")])
def test_advice_only_on_known_data(client, region, date):
    a = data(client.get(f"{API}/regions/{region}/agriculture", params={"date": date}))
    status = {DS["precipitation"]: a["rainfall_status"], DS["ndvi"]: a["vegetation_status"]}
    for s in a["statements"]:
        if s["nature"] == "interpreted":
            assert s["source_ids"], s
            assert all(status[i] != "unknown" for i in s["source_ids"]), s
            if s["text"].startswith("Pluie plus") or "Mois de bascule" in s["text"]:
                assert s["source_ids"] == [DS["precipitation"]], s
            if s["text"].startswith("La végétation"):
                assert s["source_ids"] == [DS["ndvi"]], s


# ── 9 · /meta par indicateur ──
@pytest.mark.m02
@pytest.mark.real_data
def test_meta_last_updated_by_indicator(client, last):
    m = data(client.get(f"{API}/meta"))
    assert m["data_last_updated"].startswith(max(last.values()))
    assert m["data_last_updated_by_indicator"] == last


# ── 10 · années incomplètes ──
@pytest.mark.m16
@pytest.mark.real_data
def test_compare_label_reflects_complete_years(client, df):
    c = data(client.get(f"{API}/regions/savanes/compare", params={"indicator": "precipitation"}))
    rain = df[(df.region_id == "savanes") & (df.indicator == "precipitation")]
    months = rain.groupby(rain.date.str[:4]).value.count()
    complete = [y for y in range(2016, 2026) if months.get(str(y), 0) == 12]
    assert c["period_b"]["end"] == str(max(complete))
    assert c["period_b"]["label"].startswith(f"2016–{max(complete)}")


@pytest.mark.m16
def test_compare_incomplete_year_invalid(client, last):
    year = last["precipitation"][:4]
    if last["precipitation"].endswith("-12"):
        pytest.skip("dernière année de pluie complète")
    r = client.get(f"{API}/regions/kara/compare", params={
        "indicator": "precipitation", "a_start": "2001", "a_end": "2010", "b_start": year, "b_end": year})
    assert r.status_code == 400 and err_code(r) == "invalid_period"


@pytest.mark.m15
@pytest.mark.real_data
def test_year_baseline_on_same_months(client, df, last):
    end = last["ndvi"]
    y = end[:4]
    ts = data(client.get(f"{API}/regions/savanes/timeseries",
                         params={"indicator": "ndvi", "start": f"{y}-01", "end": end, "granularity": "year"}))
    p = ts["points"][-1]
    n = int(end[5:7])
    if n < 10:
        assert p["value"] is None and p["baseline"] is None
    else:
        exp = math.fsum(_base(df, "savanes", "ndvi", m) for m in range(1, n + 1)) / n
        assert abs(p["baseline"] - exp) < 0.0006


@pytest.mark.m15
def test_year_rain_needs_12_months(client):
    ts = data(client.get(f"{API}/regions/kara/timeseries",
                         params={"indicator": "precipitation", "start": "2023-03", "end": "2024-12",
                                 "granularity": "year"}))
    by = {p["date"]: p for p in ts["points"]}
    assert by["2023"]["value"] is None and by["2023"]["baseline"] is None
    assert by["2024"]["value"] is not None


# ── 15 · faible couverture en annuel et dans l'export ──
@pytest.mark.m15
@pytest.mark.real_data
def test_year_low_coverage(client, df):
    ts = data(client.get(f"{API}/regions/maritime/timeseries",
                         params={"indicator": "ndvi", "start": "2001-01", "end": "2024-12", "granularity": "year"}))
    g = df[(df.region_id == "maritime") & (df.indicator == "ndvi")]
    for p in ts["points"]:
        yr = g[g.date.str[:4] == p["date"]]
        assert p["low_coverage"] == bool(yr.low_coverage.any())
        assert abs(p["valid_frac"] - yr.valid_frac.min()) < 1e-9


@pytest.mark.m17
@pytest.mark.real_data
def test_export_csv_flags_low_coverage(client, df):
    r = client.get(f"{API}/regions/maritime/timeseries/export",
                   params={"indicator": "ndvi", "start": "2024-01", "end": "2024-12", "format": "csv"})
    lines = r.text.strip().splitlines()
    assert lines[2] == "date,value,baseline,anomaly_pct"
    g = df[(df.region_id == "maritime") & (df.indicator == "ndvi") & df.date.between("2024-01", "2024-12")]
    flagged = {l.split()[2] for l in lines if l.startswith("# low_coverage:")}
    assert flagged == set(g[g.low_coverage].date)


# ── 16 · pleine précision ──
@pytest.mark.m16
@pytest.mark.real_data
def test_compare_full_precision(client, df):
    c = data(client.get(f"{API}/regions/kara/compare", params={
        "indicator": "ndvi", "a_start": "2001", "a_end": "2010", "b_start": "2011", "b_end": "2020"}))
    g = df[(df.region_id == "kara") & (df.indicator == "ndvi")]
    yearly = g.groupby(g.date.str[:4]).value.apply(lambda s: math.fsum(s) / len(s))
    a = math.fsum(yearly.loc["2001":"2010"]) / 10
    b = math.fsum(yearly.loc["2011":"2020"]) / 10
    assert abs(c["delta_pct"] - (b - a) / a * 100) <= 0.05 + 1e-9


# ── 17 · faits marquants ──
@pytest.mark.m19
def test_dashboard_highlights_rules(client):
    d = data(client.get(f"{API}/dashboard", params={"date": "2024-08"}))
    snaps = [(r["region"]["name"], s) for r in d["regions"] for s in r["indicators"]]
    for h in d["highlights"]:
        assert "août 2024" in h["text"]
        src = [s for n, s in snaps if h["text"].startswith(n) and f"ds:{s['dataset_id']}" in h["source_ids"]]
        assert src and src[0]["trend"] in ("above_normal", "below_normal") and not src[0]["low_coverage"]


# ── 18 · bornes ──
@pytest.mark.m15
def test_timeseries_unbounded_invalid(client):
    r = client.get(f"{API}/regions/kara/timeseries",
                   params={"indicator": "ndvi", "start": "0001-01", "end": "9999-12"})
    assert r.status_code == 400 and err_code(r) == "invalid_period"


@pytest.mark.parametrize("path", ["/regions/kara/summary", "/regions/kara/agriculture", "/dashboard"])
@pytest.mark.m14
def test_date_outside_data_invalid(client, path):
    for date in ("1990-01", "2099-01"):
        r = client.get(f"{API}{path}", params={"date": date})
        assert r.status_code == 400 and err_code(r) == "invalid_period"


# ── 19 · avant / après ──
@pytest.mark.m18
@pytest.mark.parametrize("before,after", [("2016-02-30", "2024-09-13"), ("2024-09-13", "2016-09-13")])
def test_before_after_invalid_dates(client, before, after):
    r = client.get(f"{API}/layers/ndvi/before-after", params={"before": before, "after": after})
    assert r.status_code == 400 and err_code(r) == "invalid_period"


@pytest.mark.m18
@pytest.mark.real_data
def test_before_after_note_when_no_comparison(client):
    # Couche pluie : 90 derniers jours (2026), alors que la série de pluie s'arrête en 2025-09 → pas de comparaison chiffrée
    ba = data(client.get(f"{API}/layers/precipitation/before-after", params={"region_id": "kara"}))
    assert ba["comparison"] is None and ba["comparison_note"]
    # Date hors des images de la couche LST (limitée à 2016-2022, D30) → invalid_period
    r = client.get(f"{API}/layers/lst_day/before-after",
                   params={"before": "2016-09-13", "after": "2024-09-13", "region_id": "kara"})
    assert r.status_code == 400 and err_code(r) == "invalid_period"

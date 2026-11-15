import json

import pytest

from conftest import API, data, err_code, months

RANGES = {"precipitation": (0, 1000), "ndvi": (-1, 1), "lst_day": (-10, 75)}


def _trend_ok(s):
    a = s["anomaly_pct"]
    if s["value"] is None:
        return s["trend"] == "unknown"
    if s["indicator"] == "lst_day":
        d = s["value"] - s["baseline"]
        return s["trend"] == ("above_normal" if d > 1.5 else "below_normal" if d < -1.5 else "normal")
    return s["trend"] == ("above_normal" if a > 10 else "below_normal" if a < -10 else "normal")


# ── M14 ──
@pytest.mark.m14
def test_summary_shape(client):
    r = client.get(f"{API}/regions/kara/summary", params={"date": "2024-08"})
    assert r.status_code == 200
    s = data(r)
    assert {i["indicator"] for i in s["indicators"]} == {"precipitation", "ndvi", "lst_day"}
    for i in s["indicators"]:
        assert i["plain_summary"] and i["dataset_id"]


@pytest.mark.m14
@pytest.mark.real_data
def test_summary_deterministic_and_consistent(client):
    p = {"date": "2024-08"}
    a = data(client.get(f"{API}/regions/kara/summary", params=p))
    b = data(client.get(f"{API}/regions/kara/summary", params=p))
    assert a == b, "le résumé doit être déterministe (plus de données aléatoires)"
    for s in a["indicators"]:
        lo, hi = RANGES[s["indicator"]]
        assert lo <= s["value"] <= hi
        if s["baseline"]:
            exp = (s["value"] - s["baseline"]) / s["baseline"] * 100
            assert abs(s["anomaly_pct"] - exp) <= 0.6
        assert _trend_ok(s), s


@pytest.mark.m14
def test_summary_unknown_region(client):
    r = client.get(f"{API}/regions/abidjan/summary")
    assert r.status_code == 404 and err_code(r) == "region_not_found"


# ── M15 ──
@pytest.mark.m15
def test_timeseries_contiguous(client):
    r = client.get(f"{API}/regions/savanes/timeseries",
                   params={"indicator": "precipitation", "start": "2023-01", "end": "2024-12"})
    assert r.status_code == 200
    ts = data(r)
    assert [p["date"] for p in ts["points"]] == months("2023-01", "2024-12")
    assert ts["units"] == "mm" and ts["dataset_id"] == "gpm_imerg"


@pytest.mark.m15
@pytest.mark.real_data
def test_timeseries_seasonality(client):
    ts = data(client.get(f"{API}/regions/savanes/timeseries",
                    params={"indicator": "precipitation", "start": "2023-01", "end": "2023-12"}))
    v = {p["date"]: p["value"] for p in ts["points"]}
    assert v["2023-08"] > v["2023-01"], "Savanes : août doit être plus pluvieux que janvier"
    for p in ts["points"]:
        lo, hi = RANGES["precipitation"]
        assert p["value"] is None or lo <= p["value"] <= hi


@pytest.mark.m15
def test_timeseries_errors(client):
    r = client.get(f"{API}/regions/kara/timeseries", params={"indicator": "elevation"})
    assert r.status_code == 400 and err_code(r) == "no_timeseries"
    r = client.get(f"{API}/regions/kara/timeseries",
                   params={"indicator": "ndvi", "start": "2024-06", "end": "2024-01"})
    assert r.status_code == 400 and err_code(r) == "invalid_period"


# ── M16 ──
@pytest.mark.m16
def test_compare_math(client):
    r = client.get(f"{API}/regions/savanes/compare", params={
        "indicator": "precipitation", "a_start": "2001", "a_end": "2010", "b_start": "2015", "b_end": "2024"})
    assert r.status_code == 200
    c = data(r)
    a, b = c["period_a"]["mean"], c["period_b"]["mean"]
    assert abs(c["delta_abs"] - (b - a)) < 0.01
    assert abs(c["delta_pct"] - (b - a) / a * 100) < 0.1
    assert c["period_a"]["label"] == "2001–2010"


@pytest.mark.m16
@pytest.mark.real_data
def test_compare_deterministic(client):
    p = {"indicator": "ndvi", "a_start": "2001", "a_end": "2010", "b_start": "2015", "b_end": "2024"}
    assert data(client.get(f"{API}/regions/kara/compare", params=p)) == \
        data(client.get(f"{API}/regions/kara/compare", params=p))


@pytest.mark.m16
def test_compare_invalid(client):
    r = client.get(f"{API}/regions/kara/compare", params={
        "indicator": "ndvi", "a_start": "2010", "a_end": "2001", "b_start": "2015", "b_end": "2024"})
    assert r.status_code == 400 and err_code(r) == "invalid_period"


# ── M17 ──
@pytest.mark.m17
def test_export_csv(client):
    r = client.get(f"{API}/regions/kara/timeseries/export",
                   params={"indicator": "ndvi", "start": "2024-01", "end": "2024-03", "format": "csv"})
    assert r.status_code == 200
    assert "attachment" in r.headers["content-disposition"]
    lines = r.text.strip().splitlines()
    assert lines[0].startswith("# source:") and lines[1].startswith("# units:")
    assert lines[2] == "date,value,baseline,anomaly_pct"
    assert [l.split(",")[0] for l in lines[3:]] == months("2024-01", "2024-03")


@pytest.mark.m17
def test_export_json(client):
    r = client.get(f"{API}/regions/kara/timeseries/export",
                   params={"indicator": "ndvi", "start": "2024-01", "end": "2024-02", "format": "json"})
    assert r.status_code == 200
    assert json.loads(r.text)["indicator"] == "ndvi"


# ── M18 ──
@pytest.mark.m18
def test_before_after(client):
    r = client.get(f"{API}/layers/ndvi/before-after",
                   params={"before": "2016-09-14", "after": "2024-09-13", "region_id": "kara"})
    assert r.status_code == 200
    ba = data(r)
    assert ba["before"]["url_template"] != ba["after"]["url_template"]
    assert "2016-09-14" in ba["before"]["url_template"]
    assert "{date}" not in ba["after"]["url_template"]
    assert ba["comparison"]["region_id"] == "kara"


@pytest.mark.m18
def test_before_after_unknown(client):
    r = client.get(f"{API}/layers/inconnue/before-after")
    assert r.status_code == 404 and err_code(r) == "layer_not_found"

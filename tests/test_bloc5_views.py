import pytest

from conftest import API, REGION_IDS, data, err_code


@pytest.mark.m19
def test_dashboard(client):
    d = data(client.get(f"{API}/dashboard", params={"date": "2024-08"}))
    assert {r["region"]["id"] for r in d["regions"]} == REGION_IDS
    assert 1 <= len(d["highlights"]) <= 3
    for h in d["highlights"]:
        assert h["nature"] == "observed" and h["source_ids"]


@pytest.mark.m20
@pytest.mark.parametrize("region,date,season", [
    ("savanes", "2024-08", "rainy"),
    ("savanes", "2024-01", "dry"),
    ("maritime", "2024-05", "rainy"),
])
def test_agriculture_season(client, region, date, season):
    a = data(client.get(f"{API}/regions/{region}/agriculture", params={"date": date}))
    assert a["season"] == season


@pytest.mark.m20
def test_agriculture_rules(client):
    a = data(client.get(f"{API}/regions/savanes/agriculture", params={"date": "2024-08"}))
    assert "prévisions officielles" in a["disclaimer"]
    assert a["statements"]
    assert all(s["nature"] != "predicted" for s in a["statements"])
    assert any(s["nature"] == "observed" and s["source_ids"] for s in a["statements"])


@pytest.mark.m21
def test_voice_501(client):
    r = client.post(f"{API}/voice/transcribe")
    assert r.status_code == 501 and err_code(r) == "in_development"

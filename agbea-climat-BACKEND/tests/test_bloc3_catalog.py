import pytest

from conftest import API, err_code


@pytest.mark.m10
def test_indicators(client):
    inds = {i["id"]: i for i in client.get(f"{API}/indicators").json()}
    assert set(inds) == {"precipitation", "ndvi", "lst_day", "elevation"}
    assert inds["elevation"]["has_timeseries"] is False
    assert all(inds[k]["has_timeseries"] for k in ("precipitation", "ndvi", "lst_day"))
    datasets = {d["id"] for d in client.get(f"{API}/datasets").json()}
    layers = {l["id"] for m in ("public", "scientific") for l in client.get(f"{API}/layers", params={"mode": m}).json()}
    for i in inds.values():
        assert i["dataset_id"] in datasets
        assert i["description_public"] and i["description_scientific"]
        if i.get("layer_id"):
            assert i["layer_id"] in layers


@pytest.mark.m11
def test_datasets_complete(client):
    ds = client.get(f"{API}/datasets").json()
    assert len(ds) == 4
    for d in ds:
        for k in ("name", "provider", "variable", "spatial_resolution", "temporal_resolution",
                  "coverage", "period_start"):
            assert d[k], f"{d['id']}.{k} vide"
        assert d["limitations"], f"{d['id']}: limitations vide"
        assert d["source_url"].startswith("https://")


@pytest.mark.m12
def test_dataset_detail(client):
    assert client.get(f"{API}/datasets/gpm_imerg").json()["indicator"] == "precipitation"
    r = client.get(f"{API}/datasets/inconnu")
    assert r.status_code == 404 and err_code(r) == "dataset_not_found"


@pytest.mark.m13
def test_layers(client):
    layers = client.get(f"{API}/layers", params={"mode": "public"}).json()
    assert layers
    datasets = {d["id"] for d in client.get(f"{API}/datasets").json()}
    for l in layers:
        u = l["url_template"]
        assert u.startswith("https://")
        for ph in ("{z}", "{x}", "{y}", "{date}"):
            assert ph in u, f"{l['id']}: {ph} manquant"
        assert len(l["legend"]) >= 2
        assert l["dataset_id"] in datasets
        assert l["default_date"] in l["available_dates"]

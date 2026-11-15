import pytest

from conftest import API, REGION_IDS, TOGO_LAT, TOGO_LON, data, err_code


def _in_togo(lon, lat):
    return TOGO_LON[0] <= lon <= TOGO_LON[1] and TOGO_LAT[0] <= lat <= TOGO_LAT[1]


@pytest.mark.m06
def test_regions(client):
    r = client.get(f"{API}/regions")
    assert r.status_code == 200
    regions = data(r)
    assert {x["id"] for x in regions} == REGION_IDS
    for x in regions:
        lon, lat = x["centroid"]
        assert _in_togo(lon, lat), f"{x['id']}: centroid hors Togo ou [lat, lon] inversé"
        assert x["capital"]


@pytest.mark.m07
def test_geojson_valid(client):
    g = data(client.get(f"{API}/regions/geojson"))
    assert g["type"] == "FeatureCollection"
    assert {f["properties"]["id"] for f in g["features"]} == REGION_IDS
    for f in g["features"]:
        assert f["geometry"]["type"] in ("Polygon", "MultiPolygon")


@pytest.mark.m07
@pytest.mark.real_data
def test_geojson_real_boundaries(client):
    g = data(client.get(f"{API}/regions/geojson"))
    for f in g["features"]:
        geom = f["geometry"]
        rings = geom["coordinates"] if geom["type"] == "Polygon" else [r for p in geom["coordinates"] for r in p]
        pts = [pt for ring in rings for pt in ring]
        assert len(pts) >= 20, f"{f['properties']['id']}: contour trop simple (rectangle ?)"
        assert all(_in_togo(lon, lat) for lon, lat in pts), "coordonnées hors Togo ou inversées"


@pytest.mark.m08
def test_region_detail(client):
    assert data(client.get(f"{API}/regions/kara"))["id"] == "kara"
    r = client.get(f"{API}/regions/abidjan")
    assert r.status_code == 404 and err_code(r) == "region_not_found"


@pytest.mark.m09
@pytest.mark.parametrize("name,lon,lat,expected", [
    ("Lomé", 1.2228, 6.1319, "maritime"),
    ("Atakpamé", 1.1261, 7.5333, "plateaux"),
    ("Sokodé", 1.1333, 8.9833, "centrale"),
    ("Kara", 1.1861, 9.5511, "kara"),
    ("Dapaong", 0.2075, 10.8622, "savanes"),
])
def test_locate_cities(client, name, lon, lat, expected):
    r = client.get(f"{API}/locate", params={"lon": lon, "lat": lat})
    assert r.status_code == 200, name
    assert data(r)["id"] == expected, name


@pytest.mark.m09
def test_locate_outside(client):
    r = client.get(f"{API}/locate", params={"lon": -0.187, "lat": 5.6037})  # Accra
    assert r.status_code == 404 and err_code(r) == "outside_togo"

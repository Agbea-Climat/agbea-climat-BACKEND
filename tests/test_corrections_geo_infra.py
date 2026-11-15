"""Corrections du rapport de tests du 15/11/2026 (notes/2026-11-15_tests-api.md) :
géographie (/locate, /regions/geojson), catalogue (couches, contrat) et socle (erreurs, routes)."""
import json
import math
from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from shapely.geometry import Point, shape
from shapely.ops import unary_union

from backend.main import create_app
from backend.services import catalog
from conftest import API, DATA, data, err_code


def _locate(client, lon, lat):
    return client.get(f"{API}/locate", params={"lon": lon, "lat": lat})


# ─────────── 7 · /locate : un point hors du Togo n'est jamais classé ───────────
@pytest.mark.m09
@pytest.mark.parametrize("name,lon,lat", [
    ("Aflao (Ghana)", 1.193, 6.115),
    ("Ghana à 400 m de la frontière", 1.1940, 6.1300),
    ("Bénin, Sanvee Condji", 1.6450, 6.2420),
    ("Burkina Faso, près de Sinkansé", 0.0200, 11.1500),
    ("Golfe de Guinée à 1 km de Lomé", 1.2400, 6.1150),
])
def test_locate_outside_near_border(client, name, lon, lat):
    r = _locate(client, lon, lat)
    assert r.status_code == 404 and err_code(r) == "outside_togo", name


@pytest.mark.m09
@pytest.mark.real_data
def test_locate_no_point_beyond_100m(client):
    """Points tirés autour du contour national : > 100 m dehors → 404 ; dedans → la région shapely."""
    g = json.loads((DATA / "regions.geojson").read_text(encoding="utf-8"))
    regs = {f["properties"]["id"]: shape(f["geometry"]) for f in g["features"]}
    togo = unary_union(list(regs.values()))
    m_per_deg_min = 110574 * math.cos(math.radians(11.2))
    ring = list(togo.exterior.coords)
    for k in range(0, len(ring) - 1, 7):
        (x0, y0), (x1, y1) = ring[k], ring[k + 1]
        nx, ny = y1 - y0, -(x1 - x0)                      # normale au segment
        n = math.hypot(nx, ny) or 1
        for d in (-0.004, -0.0015, 0.0015, 0.004):        # ±170 m et ±440 m
            lon, lat = (x0 + x1) / 2 + d * nx / n, (y0 + y1) / 2 + d * ny / n
            p = Point(lon, lat)
            inside = [rid for rid, geom in regs.items() if geom.covers(p)]
            r = _locate(client, lon, lat)
            if inside:
                assert r.status_code == 200 and data(r)["id"] in inside, (lon, lat)
            elif togo.distance(p) * m_per_deg_min > 100:
                assert r.status_code == 404 and err_code(r) == "outside_togo", (lon, lat)


@pytest.mark.m09
def test_locate_coast_tolerance(client):
    # En mer à ~50 m de la plage de Lomé : rattaché à Maritime (seule tolérance, documentée)
    r = _locate(client, 1.2500, 6.1283)
    assert r.status_code == 200 and data(r)["id"] == "maritime"


@pytest.mark.m09
@pytest.mark.parametrize("lon,lat,expected", [
    (1.2225, 6.1319, "maritime"), (1.126, 7.527, "plateaux"), (1.133, 8.983, "centrale"),
    (1.186, 9.551, "kara"), (0.207, 10.862, "savanes"),
])
def test_locate_capitals(client, lon, lat, expected):
    assert data(_locate(client, lon, lat))["id"] == expected


# ─────────── 8 · /locate : bornes et inversion ───────────
@pytest.mark.m09
@pytest.mark.parametrize("lon,lat", [(200, 95), (-181, 6), (1, -91), ("nan", 6), (1, "nan"), ("inf", 6), (1, "-inf"), ("abc", 6)])
def test_locate_invalid_coordinates(client, lon, lat):
    r = _locate(client, lon, lat)
    assert r.status_code == 422 and err_code(r) == "validation_error"


@pytest.mark.m09
def test_locate_swapped_hint(client):
    r = _locate(client, 6.1319, 1.2225)             # Lomé, lat et lon inversés
    assert r.status_code == 404 and err_code(r) == "outside_togo"
    details = r.json()["response"]["details"]
    assert details["region_id"] == "maritime"
    assert details["suggested"] == {"lon": 1.2225, "lat": 6.1319}
    # Accra : pas de suggestion
    assert _locate(client, -0.187, 5.6037).json()["response"]["details"] is None


# ─────────── 23 · /regions/geojson : attribution de la source ───────────
@pytest.mark.m07
def test_geojson_source(client):
    g = data(client.get(f"{API}/regions/geojson"))
    raw = json.loads((DATA / "regions.geojson").read_text(encoding="utf-8"))
    assert g["source"] == raw["source"] and "geodata.gouv.tg" in g["source"]


@pytest.mark.m07
def test_geojson_openapi_schema(client):
    spec = client.get("/openapi.json").json()
    ref = spec["paths"][f"{API}/regions/geojson"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]["$ref"]
    assert ref.endswith("ApiResponse_RegionFeatureCollection_")


# ─────────── 22 · Couches : provenance et dates ───────────
@pytest.mark.m13
def test_layers_provenance_and_dates(client):
    layers = {l["id"]: l for m in ("public", "scientific") for l in data(client.get(f"{API}/layers", params={"mode": m}))}
    for l in layers.values():
        assert l["description"], f"{l['id']}: provenance des tuiles absente"
        assert l["available_dates"] == sorted(set(l["available_dates"]))
        assert l["default_date"] == l["available_dates"][-1]
    assert "mm/h" in layers["precipitation"]["title"] and "GPM_3IMERGM" in layers["precipitation"]["description"]
    assert "MOD13Q1" in layers["ndvi"]["description"] and "250 m" in layers["ndvi"]["title"]
    # Température du sol : pas de dates après la fin des valeurs publiées (dataset modis_lst)
    end = data(client.get(f"{API}/datasets/modis_lst"))["period_end"]
    assert max(layers["lst_day"]["available_dates"]) <= end


# ─────────── 21 · Socle : barre oblique, HEAD, erreurs du framework, OpenAPI ───────────
@pytest.mark.m01
def test_trailing_slash_no_redirect(client):
    for path in ("/regions/", "/regions/kara/", "/health/"):
        r = client.get(f"{API}{path}", follow_redirects=False)
        assert r.status_code == 200, path
        assert data(r) == data(client.get(f"{API}{path.rstrip('/')}"))


@pytest.mark.m01
def test_head_health(client):
    assert client.head(f"{API}/health").status_code == 200


@pytest.mark.m01
def test_framework_errors_in_french(client):
    r = client.get(f"{API}/route-inconnue")
    assert r.status_code == 404 and err_code(r) == "not_found"
    assert r.json()["message"] == "Ressource introuvable"
    r = client.delete(f"{API}/regions")
    assert r.status_code == 405 and err_code(r) == "method_not_allowed"
    assert "Méthode" in r.json()["message"] and r.headers.get("allow") == "GET"


@pytest.mark.m01
def test_internal_error_envelope():
    app = create_app()

    @app.get(f"{API}/_boom")
    def boom():
        raise RuntimeError("panne simulée")

    r = TestClient(app, raise_server_exceptions=False).get(f"{API}/_boom")  # sans lifespan
    assert r.status_code == 500 and err_code(r) == "internal_error"
    assert "panne simulée" not in r.text


@pytest.mark.m01
def test_openapi_documents_503(client):
    spec = client.get("/openapi.json").json()
    assert "503" in spec["paths"][f"{API}/regions"]["get"]["responses"]


# ─────────── B4 · 422 : valeur reçue tronquée ───────────
@pytest.mark.m26
def test_validation_error_input_truncated(client):
    r = client.post(f"{API}/chat", json={"message": "x" * 2001})
    assert r.status_code == 422 and err_code(r) == "validation_error"
    assert len(r.text) < 1000
    issue = r.json()["response"]["details"][0]
    assert issue["loc"] == ["body", "message"] and len(issue["input"]) <= 101


# ─────────── Deuxième tour (F1-F6) ───────────
def _spec(client):
    return client.get("/openapi.json").json()


@pytest.mark.m09
def test_locate_openapi_documents_tolerance(client):
    op = _spec(client)["paths"][f"{API}/locate"]["get"]
    assert "100 m" in op["description"] and "frontières terrestres" in op["description"]
    assert "inversés" in op["description"]


@pytest.mark.m01
def test_openapi_503_only_on_data_routes(client):
    paths = _spec(client)["paths"]
    for path, method in (("/health", "get"), ("/profiles", "get"), ("/sessions", "post"),
                         ("/sessions/{session_id}", "get"), ("/indicators", "get"), ("/datasets", "get"),
                         ("/layers", "get"), ("/voice/transcribe", "post")):
        assert "503" not in paths[f"{API}{path}"][method]["responses"], path
    for path, method in (("/regions", "get"), ("/locate", "get"), ("/meta", "get"),
                         ("/regions/{region_id}/summary", "get"), ("/dashboard", "get"), ("/chat", "post")):
        assert "503" in paths[f"{API}{path}"][method]["responses"], path
    assert "405" in paths[f"{API}/regions"]["get"]["responses"]


@pytest.mark.m01
def test_openapi_validation_issue_component(client):
    spec = _spec(client)
    assert "ValidationIssue" in spec["components"]["schemas"]
    ref = spec["paths"][f"{API}/locate"]["get"]["responses"]["422"]["content"]["application/json"]["schema"]["$ref"]
    assert ref.endswith("ApiValidationErrorResponse")


@pytest.mark.m13
def test_validation_error_french_without_ctx(client):
    r = client.get(f"{API}/layers", params={"mode": "xyz"})
    issue = r.json()["response"]["details"][0]
    assert "ctx" not in issue and issue["msg"] == "valeur non autorisée (attendu : 'public' ou 'scientific')"
    r = client.post(f"{API}/chat", content="pas du json", headers={"Content-Type": "application/json"})
    assert r.status_code == 422 and "ctx" not in r.json()["response"]["details"][0]


@pytest.mark.m08
def test_not_found_message_truncated(client):
    r = client.get(f"{API}/regions/" + "a" * 3000)
    assert r.status_code == 404 and err_code(r) == "region_not_found"
    assert len(r.json()["message"]) <= 301 and len(r.text) < 700
    r = client.get(f"{API}/inconnue/" + "b" * 3000)
    assert r.status_code == 404 and len(r.text) < 700


@pytest.mark.m13
def test_imerg_sliding_window(client):
    layer = {l["id"]: l for l in data(client.get(f"{API}/layers"))}["precipitation"]
    today = datetime.now(timezone.utc).date()
    assert layer["default_date"] == (today - timedelta(days=2)).isoformat()
    assert layer["available_dates"][0] == (today - timedelta(days=91)).isoformat() or len(layer["available_dates"]) < 90
    # Trous connus de GIBS retirés ; fenêtre de 90 jours, J-2 compris
    dates = catalog.imerg_dates(date(2026, 3, 1))
    assert "2026-02-10" not in dates and "2026-02-11" not in dates and "2026-02-03" not in dates
    assert dates[-1] == "2026-02-27" and len(dates) == 90 - 4
    assert catalog.imerg_dates(date(2026, 11, 15))[-1] == "2026-11-13"

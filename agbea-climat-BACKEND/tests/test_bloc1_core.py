import pytest

from conftest import API, ISO_DATE, err_code, is_uuid


@pytest.mark.m01
def test_health(client):
    r = client.get(f"{API}/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


@pytest.mark.m02
def test_meta_features(client):
    r = client.get(f"{API}/meta")
    assert r.status_code == 200
    body = r.json()
    status = {f["id"]: f["status"] for f in body["features"]}
    assert status["voice"] == "in_development"
    assert status["ewe"] == "planned"
    assert ISO_DATE.match(body["data_last_updated"])
    assert body["regions_count"] == 5


@pytest.mark.m27
def test_profiles(client):
    r = client.get(f"{API}/profiles")
    assert r.status_code == 200
    profiles = {p["id"]: p for p in r.json()}
    assert set(profiles) == {"farmer", "community", "researcher", "decision_maker"}
    indicators = {i["id"] for i in client.get(f"{API}/indicators").json()}
    for p in profiles.values():
        assert p["title"] and p["benefit"] and p["icon"] and p["ai_tone"]
        assert p["featured_indicators"] and set(p["featured_indicators"]) <= indicators
    assert profiles["farmer"]["landing_screen"] == "agriculture"
    assert profiles["farmer"]["default_mode"] == "public"
    assert profiles["researcher"]["default_mode"] == "scientific"


@pytest.mark.m03
def test_create_session(client):
    a = client.post(f"{API}/sessions")
    b = client.post(f"{API}/sessions")
    assert a.status_code == b.status_code == 201
    ida, idb = a.json()["session_id"], b.json()["session_id"]
    assert is_uuid(ida) and is_uuid(idb) and ida != idb
    assert a.json()["threads"] == []


@pytest.mark.m04
def test_get_session_unknown(client):
    r = client.get(f"{API}/sessions/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404
    assert err_code(r) == "session_not_found"


@pytest.mark.m04
def test_get_session_roundtrip(client, session_id):
    r = client.get(f"{API}/sessions/{session_id}")
    assert r.status_code == 200
    assert r.json()["session_id"] == session_id


@pytest.mark.m04
@pytest.mark.m26
@pytest.mark.llm
def test_session_threads_sorted(client, session_id):
    h = {"X-Session-Id": session_id}
    client.post(f"{API}/chat", json={"message": "Pluie dans les Savanes ?"}, headers=h)
    client.post(f"{API}/chat", json={"message": "Végétation à Kara ?"}, headers=h)
    threads = client.get(f"{API}/sessions/{session_id}").json()["threads"]
    assert len(threads) == 2
    assert threads[0]["updated_at"] >= threads[1]["updated_at"]


@pytest.mark.m05
def test_preferences_roundtrip(client, session_id):
    r = client.patch(f"{API}/sessions/{session_id}/preferences",
                     json={"profile": "farmer", "region_id": "savanes"})
    assert r.status_code == 200
    r = client.patch(f"{API}/sessions/{session_id}/preferences", json={"mode": "scientific"})
    assert r.status_code == 200
    prefs = client.get(f"{API}/sessions/{session_id}").json()["preferences"]
    assert prefs["profile"] == "farmer"
    assert prefs["region_id"] == "savanes"
    assert prefs["mode"] == "scientific"


@pytest.mark.m05
def test_preferences_invalid(client, session_id):
    r = client.patch(f"{API}/sessions/{session_id}/preferences", json={"profile": "pilote"})
    assert r.status_code == 422 and err_code(r) == "validation_error"
    r = client.patch(f"{API}/sessions/{session_id}/preferences", json={"region_id": "abidjan"})
    assert r.status_code == 404 and err_code(r) == "region_not_found"

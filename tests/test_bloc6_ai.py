import pytest

from conftest import API, DATA, NATURES, data, sse_events


# ── Prérequis ──
@pytest.mark.p2
@pytest.mark.real_data
def test_p2_data_files():
    import pandas as pd
    df = pd.read_parquet(DATA / "processed" / "monthly.parquet")
    assert set(df.columns) >= {"region_id", "indicator", "date", "value"}
    assert set(df.region_id) == {"maritime", "plateaux", "centrale", "kara", "savanes"}
    assert set(df.indicator) == {"precipitation", "ndvi", "lst_day"}
    assert df.date.min() <= "2001-01"
    assert (DATA / "regions.geojson").exists() and (DATA / "processed" / "static.json").exists()


@pytest.mark.p3
def test_p3_corpus():
    import json
    src = DATA / "corpus" / "sources.json"
    assert src.exists(), "data/corpus/sources.json manquant"
    entries = json.loads(src.read_text())
    assert len(entries) >= 5
    for e in entries:
        assert (DATA / "corpus" / e["file"]).exists() and e["title"] and e["source_url"]


# ── M22 / M23 ──
@pytest.mark.m22
def test_ingest_idempotent(client):
    a = data(client.post(f"{API}/admin/rag/ingest"))
    b = data(client.post(f"{API}/admin/rag/ingest"))
    assert a["documents"] >= 5 and a["chunks"] > 0
    assert a == b, "relancer l'ingestion ne doit pas créer de doublons"


@pytest.mark.m23
def test_documents(client):
    docs = data(client.get(f"{API}/admin/rag/documents"))["documents"]
    assert len(docs) >= 5
    for d in docs:
        assert d["title"] and d["source_url"] and d["chunks"] > 0


# ── M24 ──
def _explain(client, profile):
    r = client.post(f"{API}/explain", json={
        "region_id": "savanes", "indicator": "precipitation", "date": "2024-08",
        "mode": "public", "lang": "fr", "profile": profile})
    assert r.status_code == 200
    return data(r)


@pytest.mark.m24
def test_explain_structure(client):
    e = _explain(client, "farmer")
    ids = {s["id"] for s in e["sources"]}
    assert e["statements"] and "prévisions officielles" in e["disclaimer"]
    for s in e["statements"]:
        assert s["nature"] in NATURES
        assert s["source_ids"], f"phrase sans source : {s['text']}"
        assert set(s["source_ids"]) <= ids


@pytest.mark.m24
@pytest.mark.llm
def test_explain_profile_changes_text(client):
    farmer = " ".join(s["text"] for s in _explain(client, "farmer")["statements"])
    researcher = " ".join(s["text"] for s in _explain(client, "researcher")["statements"])
    assert farmer != researcher
    assert "mm" in researcher


# ── M25 ──
@pytest.mark.m25
def test_stream_event_order(client):
    r = client.post(f"{API}/chat/stream", json={"message": "Comment évolue la pluie dans les Savanes ?"})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")
    types = [e["type"] for e in sse_events(r.text)]
    assert types[0] == "meta" and types[-1] == "done"
    assert "status" in types and "token" in types and "sources" in types
    assert types.index("status") < types.index("token") < types.index("sources") < types.index("done")


@pytest.mark.m25
@pytest.mark.llm
def test_stream_off_topic(client):
    r = client.post(f"{API}/chat/stream", json={"message": "Qui a gagné la Ligue des champions ?"})
    text = "".join(e["content"] for e in sse_events(r.text) if e["type"] == "token").lower()
    assert any(w in text for w in ("climat", "environnement", "togo"))


# ── M26 ──
@pytest.mark.m26
def test_chat_thread_kept(client):
    a = data(client.post(f"{API}/chat", json={"message": "Bonjour"}))
    assert a["thread_id"] and a["answer"]
    b = data(client.post(f"{API}/chat", json={"message": "Et à Kara ?", "thread_id": a["thread_id"]}))
    assert b["thread_id"] == a["thread_id"]

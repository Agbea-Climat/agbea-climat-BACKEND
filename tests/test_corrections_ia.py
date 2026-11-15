"""Corrections de l'assistant (rapport notes/2026-11-15_tests-api.md, points 2-6, 11-14, 24, M2, M6).

Les tests « LLM simulé » remplacent chatbot.llm.client par un faux modèle (aucun appel réseau) pour
vérifier les garde-fous du mode LLM : chiffres inventés et phrases prédictives retirés, avertissement
ajouté, repli propre si le flux s'interrompt.
"""
import pytest
from sqlalchemy.exc import OperationalError

from backend.core.constants import DISCLAIMER
from backend.core.database import ping
from chatbot import guard
from chatbot.llm import client as llm_client
from chatbot.prompts.i18n import DISCLAIMER_EN
from chatbot.tools import question
from conftest import API, data, err_code, sse_events


def _db_up() -> bool:
    try:
        return ping()
    except OperationalError:
        return False


needs_db = [pytest.mark.db, pytest.mark.skipif(not _db_up(), reason="PostgreSQL injoignable")]


def _chat(client, **body):
    r = client.post(f"{API}/chat", json=body)
    assert r.status_code == 200, r.text
    return data(r)


def _explain(client, **body):
    r = client.post(f"{API}/explain", json=body)
    assert r.status_code == 200, r.text
    return data(r)


def _computed(sources):
    return {s["id"] for s in sources if s["kind"] == "computed"}


# ── Lecture de la question ──
@pytest.mark.m26
@pytest.mark.parametrize("text,expected", [
    ("Il a plu combien à Lomé en juillet 2024 ?", {"kind": "month", "value": "2024-07"}),
    ("How much rain fell in Savanes in August 2025?", {"kind": "month", "value": "2025-08"}),
    ("pluie 2024-07", {"kind": "month", "value": "2024-07"}),
    ("pluie 07/2024", {"kind": "month", "value": "2024-07"}),
    ("Il a plu combien en 2015 ?", {"kind": "year", "value": "2015"}),
    ("Et l'an dernier ?", {"kind": "year", "value": "2025"}),
    ("rain last year", {"kind": "year", "value": "2025"}),
    ("Et en juillet ?", {"kind": "month_only", "value": "07"}),
    ("Comment évolue la pluie ?", None),
])
def test_parse_date(text, expected):
    from datetime import date
    assert question.parse_date(text, today=date(2026, 11, 15)) == expected


@pytest.mark.m26
def test_intents():
    assert question.intent("Va-t-il pleuvoir demain à Lomé ?") == "forecast"
    assert question.intent("Will it rain tomorrow?") == "forecast"
    assert question.intent("Quand semer le maïs dans les Plateaux ?") == "calendar"
    assert question.intent("Quelle est la tendance de la température à Kara ?") == "trend"
    assert question.intent("Il a plu combien à Lomé en juillet 2024 ?") is None


# ── Point 2-3 : date de la question, valeurs datées ──
@pytest.mark.m26
@pytest.mark.real_data
def test_chat_uses_question_date_and_follow_up(client):
    a = _chat(client, message="Il a plu combien à Lomé en juillet 2024 ?")
    assert "computed:maritime:precipitation:2024-07" in _computed(a["sources"])
    assert not any(i.endswith(":2025-09") for i in _computed(a["sources"]))
    assert "juillet 2024" in a["answer"] and " mm" in a["answer"]
    b = _chat(client, message="Et en septembre 2025 ?", thread_id=a["thread_id"])
    assert "computed:maritime:precipitation:2025-09" in _computed(b["sources"])
    assert "septembre 2025" in b["answer"]


@pytest.mark.m26
@pytest.mark.real_data
def test_chat_latest_values_are_dated(client):
    r = _chat(client, message="Quel temps a-t-il fait à Kara ? pluie, végétation et température", region_id="kara")
    for s in r["statements"]:
        if s["nature"] == "observed" and s["source_ids"][0].startswith("computed:"):
            y, m = s["source_ids"][0].rsplit(":", 1)[1].split("-")
            assert y in s["text"], f"valeur non datée : {s['text']}"
    assert "les mesures les plus récentes datent" in r["answer"]


@pytest.mark.m26
@pytest.mark.real_data
def test_chat_date_outside_data(client):
    r = _chat(client, message="Il a plu combien à Lomé en mars 1990 ?")
    assert "commencent en janvier 2001" in r["answer"]
    assert not _computed(r["sources"])


# ── M2 : pas de prévision ──
@pytest.mark.m26
@pytest.mark.real_data
def test_chat_no_forecast(client):
    r = _chat(client, message="Va-t-il pleuvoir demain à Lomé ?")
    assert "ne fait pas de prévision" in r["answer"] and "ANAMET" in r["answer"]
    assert all(s["nature"] != "predicted" for s in r["statements"])
    assert "septembre 2025" in r["answer"]  # dernière observation, datée


# ── Point 6 : avertissement toujours présent ──
@pytest.mark.m26
def test_disclaimer_off_topic_chat_and_stream(client):
    r = _chat(client, message="Qui a gagné la coupe du monde 2022 ?")
    assert r["disclaimer"] == DISCLAIMER and DISCLAIMER in r["answer"]
    evs = sse_events(client.post(f"{API}/chat/stream", json={"message": "Qui a gagné la coupe du monde 2022 ?"}).text)
    assert evs[-1]["type"] == "done" and evs[-1]["disclaimer"] == DISCLAIMER
    assert DISCLAIMER in "".join(e["content"] for e in evs if e["type"] == "token")


# ── Point 11 : langue ──
@pytest.mark.m26
@pytest.mark.real_data
def test_chat_english(client):
    r = _chat(client, message="How much rain fell in Savanes in August 2025?", lang="en")
    assert "In August 2025, 191.6 mm of rain fell" in r["answer"] and DISCLAIMER_EN in r["answer"]
    assert r["disclaimer"] == DISCLAIMER
    assert "région" not in r["answer"]


@pytest.mark.m24
@pytest.mark.real_data
def test_explain_english(client):
    e = _explain(client, region_id="savanes", indicator="ndvi", date="2025-07", lang="en")
    assert e["title"].startswith("Vegetation")
    assert "July 2025" in e["statements"][0]["text"] and "0.455" in e["statements"][0]["text"]


# ── Point 12 : le gabarit répond à la question ──
@pytest.mark.m26
@pytest.mark.real_data
@pytest.mark.parametrize("_", [None], ids=["calendar"])
def test_chat_calendar(client, _):
    if not _db_up():
        pytest.skip("PostgreSQL injoignable")
    client.post(f"{API}/admin/rag/ingest")
    r = _chat(client, message="Quand semer le maïs dans les Plateaux ?")
    assert "semis en mars-avril" in r["answer"]
    docs = [s for s in r["sources"] if s["kind"] == "document"]
    assert len({s["title"] for s in docs}) == len(docs), "une source par document"
    quoted = [s for s in r["statements"] if s["nature"] == "interpreted"]
    assert quoted and all(set(s["source_ids"]) <= {d["id"] for d in docs} for s in quoted)


@pytest.mark.m26
@pytest.mark.real_data
def test_chat_trend_temperature(client):
    r = _chat(client, message="Quelle est la tendance de la température à Kara ?")
    assert r["data"]["series"] and r["data"]["series"][0]["granularity"] == "year"
    assert "2020" in r["answer"] and "décembre 2022" in r["answer"]
    assert "computed:kara:lst_day:2011/2020" in _computed(r["sources"])


@pytest.mark.m25
@pytest.mark.real_data
def test_stream_several_series(client):
    evs = sse_events(client.post(f"{API}/chat/stream",
                                 json={"message": "Quelle est la tendance de la température et de la pluie à Kara ?"}).text)
    series = [e["series"] for e in evs if e["type"] == "data" and e.get("series")]
    assert {s["indicator"] for s in series} == {"lst_day", "precipitation"}


# ── Point 14 : région / position invalides ──
@pytest.mark.m26
@pytest.mark.parametrize("path", ["/chat", "/chat/stream"])
@pytest.mark.parametrize("body,code", [({"message": "pluie", "region_id": "atlantis"}, "region_not_found"),
                                       ({"message": "pluie", "location": [2.5, 48.8]}, "outside_togo")])
def test_chat_invalid_place(client, path, body, code):
    r = client.post(f"{API}{path}", json=body)
    assert r.status_code == 404 and err_code(r) == code


# ── Points 4, 5, 13 : /explain ──
@pytest.mark.m24
@pytest.mark.real_data
def test_explain_missing_value_no_interpretation(client):
    e = _explain(client, region_id="maritime", indicator="precipitation", date="2026-10")
    sts = e["statements"]
    assert "Pas de donnée" in sts[0]["text"] and "octobre 2026" in sts[0]["text"]
    assert all(s["nature"] == "observed" for s in sts)
    assert any("septembre 2025" in s["text"] and "computed:maritime:precipitation:2025-09" in s["source_ids"]
               for s in sts)
    assert e["disclaimer"] == DISCLAIMER


@pytest.mark.m24
@pytest.mark.real_data
def test_explain_advice_matches_indicator(client):
    e = _explain(client, region_id="savanes", indicator="ndvi", date="2025-07")
    for s in e["statements"]:
        if s["nature"] == "interpreted":
            assert "Pluie" not in s["text"]
            assert all(":ndvi:" in i for i in s["source_ids"] if i.startswith("computed:"))


@pytest.mark.m24
@pytest.mark.real_data
@pytest.mark.parametrize("body,status,code", [
    ({"indicator": "land_cover"}, 501, "in_development"),
    ({"indicator": "precipitation", "date": "1990-01"}, 400, "invalid_period"),
    ({"indicator": "precipitation", "date": "2099-01"}, 400, "invalid_period"),
    ({"indicator": "elevation", "date": "bad"}, 400, "invalid_period"),
])
def test_explain_errors(client, body, status, code):
    r = client.post(f"{API}/explain", json={"region_id": "kara", **body})
    assert r.status_code == status and err_code(r) == code


# ── Point 24 : altitude ──
@pytest.mark.m24
@pytest.mark.real_data
def test_explain_elevation(client):
    fr = _explain(client, region_id="kara", indicator="elevation")
    en = _explain(client, region_id="kara", indicator="elevation", lang="en")
    assert "273,8 m" in fr["statements"][0]["text"] and "273.8 m" in en["statements"][0]["text"]
    assert fr["statements"][0]["source_ids"] == ["computed:kara:elevation:static", "ds:srtm"]
    assert "ds:srtm" in {s["id"] for s in fr["sources"]}
    if _db_up():
        client.post(f"{API}/admin/rag/ingest")
        fr = _explain(client, region_id="kara", indicator="elevation")
        assert any("NASADEM" in s["title"] for s in fr["sources"] if s["kind"] == "document")


# ── M6 : garde-fous du mode LLM (LLM simulé) ──
@pytest.mark.m26
def test_guard_numbers_and_prediction():
    known = guard.known_numbers(["Pluie en juillet 2024 : 31,8 mm (normale 2001–2020 : 107,2 mm)."])
    assert guard.sentence_ok("Il est tombé 31,8 mm en juillet 2024.", known)
    assert not guard.sentence_ok("Il est tombé 45 mm.", known)
    assert not guard.sentence_ok("Il va pleuvoir demain.", known)
    assert guard.ensure_disclaimer("Texte.", "fr").endswith(DISCLAIMER)


@pytest.mark.m26
@pytest.mark.real_data
def test_chat_llm_guarded(client, monkeypatch):
    async def fake_stream(system, messages, effort="medium", max_tokens=2000):
        for piece in ["Il est tombé 31,8 mm en juillet ", "2024 à Lomé. Il est tombé 999 mm l'an passé. ",
                      "Il va pleuvoir demain. ", "Restez attentifs."]:
            yield piece
    monkeypatch.setattr(llm_client, "available", lambda: True)
    monkeypatch.setattr(llm_client, "stream_text", fake_stream)
    r = _chat(client, message="Il a plu combien à Lomé en juillet 2024 ?")
    assert "31,8 mm" in r["answer"] and "999" not in r["answer"] and "demain" not in r["answer"]
    assert r["answer"].endswith(DISCLAIMER)
    evs = sse_events(client.post(f"{API}/chat/stream", json={"message": "Il a plu combien à Lomé en juillet 2024 ?"}).text)
    text = "".join(e["content"] for e in evs if e["type"] == "token")
    assert "999" not in text and DISCLAIMER in text


@pytest.mark.m25
@pytest.mark.real_data
def test_chat_llm_fails_mid_stream(client, monkeypatch):
    async def broken(system, messages, effort="medium", max_tokens=2000):
        yield "Il est tombé 31,8 mm en juillet 2024 à Lomé. "
        raise llm_client.LLMUnavailable("coupure")
    monkeypatch.setattr(llm_client, "available", lambda: True)
    monkeypatch.setattr(llm_client, "stream_text", broken)
    evs = sse_events(client.post(f"{API}/chat/stream", json={"message": "Il a plu combien à Lomé en juillet 2024 ?"}).text)
    text = "".join(e["content"] for e in evs if e["type"] == "token")
    assert "interrompue" in text and "En juillet 2024, il est tombé 31,8 mm" in text and DISCLAIMER in text
    assert evs[-1]["type"] == "done"


@pytest.mark.m26
@pytest.mark.real_data
def test_forecast_never_uses_llm(client, monkeypatch):
    async def predictive(system, messages, effort="medium", max_tokens=2000):
        yield "Oui, il pleuvra demain."
    monkeypatch.setattr(llm_client, "available", lambda: True)
    monkeypatch.setattr(llm_client, "stream_text", predictive)
    r = _chat(client, message="Va-t-il pleuvoir demain à Lomé ?")
    assert "pleuvra" not in r["answer"] and "ne fait pas de prévision" in r["answer"]


@pytest.mark.m24
@pytest.mark.real_data
def test_explain_llm_guarded(client, monkeypatch):
    from chatbot import explain as explainer

    async def fake_structured(system, user, schema, effort="medium", max_tokens=4000):
        return explainer._LLMExplain(title="Pluie 2099", statements=[
            explainer._LLMStatement(text="Il est tombé 174,8 mm en août 2024.", nature="observed",
                                    source_ids=["computed:savanes:precipitation:2024-08"]),
            explainer._LLMStatement(text="Il est tombé 500 mm.", nature="observed",
                                    source_ids=["computed:savanes:precipitation:2024-08"]),
            explainer._LLMStatement(text="Les rendements baisseront de 30 %.", nature="interpreted",
                                    source_ids=["computed:savanes:precipitation:2024-08"]),
            explainer._LLMStatement(text="Il va pleuvoir demain.", nature="interpreted",
                                    source_ids=["computed:savanes:precipitation:2024-08"]),
        ])
    monkeypatch.setattr(llm_client, "available", lambda: True)
    monkeypatch.setattr(llm_client, "structured", fake_structured)
    e = _explain(client, region_id="savanes", indicator="precipitation", date="2024-08")
    texts = [s["text"] for s in e["statements"]]
    assert texts == ["Il est tombé 174,8 mm en août 2024."]
    assert "2099" not in e["title"] and e["disclaimer"] == DISCLAIMER

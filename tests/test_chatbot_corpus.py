"""Chatbot et corpus élargi (fiches de zone, D31) : préfectures, sites, température de nuit, questions générales.

Défauts corrigés le 15/11/2026 (docs/chatbot-corpus.md §5) :
1. sans LLM, les gabarits n'utilisaient que le titre des documents (questions générales → « Précisez une région ») ;
2. les fiches de zone noyaient les documents généraux dans la recherche lexicale ;
3. préfectures, sites pilotes et température de nuit n'étaient pas reconnus.
"""
import pytest
from sqlalchemy.exc import OperationalError

from backend.core.constants import DISCLAIMER
from backend.core.database import ping
from chatbot.tools import retrieve, zones
from conftest import API, data


def _db_up() -> bool:
    try:
        return ping()
    except OperationalError:
        return False




# ── Reconnaissance des zones (sans base) ──
@pytest.mark.m25
@pytest.mark.parametrize("text,expected", [
    ("Tendance de la température la nuit à Kpalimé", "fiches/site_kpalime-mont-agou.md"),
    ("Il a plu combien à Agoè-Nyivé ?", "fiches/prefecture_agoe-nyive.md"),
    ("Le relief de la préfecture des Lacs", "fiches/prefecture_lacs.md"),
    ("Pluie dans la préfecture de Vo", "fiches/prefecture_vo.md"),
    ("Quelle pluie à Kpendjal-Ouest ?", "fiches/prefecture_kpendjal-ouest.md"),
    ("La forêt de Fazao", "fiches/site_sokode-corridor-fazao.md"),
])
def test_zone_found(text, expected):
    z = zones.find(text)
    assert z is not None and z.file == expected, (text, z)


@pytest.mark.m25
@pytest.mark.parametrize("text", [
    "je mange une mangue",                 # pas le site de Mango
    "quelle pluie a vo en 2024",           # « vo » sans contexte ni majuscule
    "Pluie à Kara en juillet 2024",        # région : pas de fiche de zone (« kara » n'est pas une clé de site)
    "Pluie à Kara (pas à Lomé)",           # zone niée
])
def test_zone_not_found(text):
    z = zones.find(text)
    assert z is None, (text, z)


@pytest.mark.m25
def test_zone_region_and_region_fiche():
    assert zones.find("Kpalimé").region_id == "plateaux"
    assert zones.region_fiche("savanes").file == "fiches/region_savanes.md"


@pytest.mark.m25
def test_passages_use_section_heading():
    """Une puce sous « ## 8. Tendances » répond à « Comment sont calculées les tendances ? »."""
    kws = retrieve.keywords("Comment sont calculées les tendances ?")
    assert retrieve.unit_score("8. Tendances", "Test de Mann-Kendall au seuil α = 0,05.", kws) > \
        retrieve.unit_score("Risques", "Pluie : tendances contrastées selon les régions.", kws)


# ── Réponses du chat (base requise) ──
@pytest.fixture(scope="module")
def ingested(client):
    client.post(f"{API}/admin/rag/ingest")
    return True


def _chat(client, msg, **kw):
    r = client.post(f"{API}/chat", json={"message": msg, **kw})
    assert r.status_code == 200, r.text
    d = data(r)
    assert d["disclaimer"] == DISCLAIMER and d["answer"].rstrip().endswith(DISCLAIMER)
    assert all(s["nature"] != "predicted" for s in d["statements"])
    return d


@pytest.mark.m25
@pytest.mark.real_data
@pytest.mark.usefixtures("ingested")
def test_general_question_uses_document(client):
    if not _db_up():
        pytest.skip("PostgreSQL injoignable")
    a = _chat(client, "Comment sont calculées les tendances ?")["answer"]
    assert "Mann-Kendall" in a and "Précisez une région" not in a
    a = _chat(client, "Qu'est-ce qu'une normale ?")["answer"]
    assert "2001-2020" in a and "Précisez une région" not in a


@pytest.mark.m25
@pytest.mark.real_data
@pytest.mark.usefixtures("ingested")
def test_site_night_temperature(client):
    if not _db_up():
        pytest.skip("PostgreSQL injoignable")
    d = _chat(client, "Quelle est la tendance de la température la nuit à Kpalimé ?")
    a = d["answer"]
    assert "Kpalimé" in a and "la nuit" in a and "hausse" in a
    assert "le jour" not in a                       # pas de température de jour pour une question sur la nuit
    assert any("Kpalimé" in s["title"] for s in d["sources"])


@pytest.mark.m25
@pytest.mark.real_data
@pytest.mark.usefixtures("ingested")
def test_prefecture_and_follow_up(client):
    if not _db_up():
        pytest.skip("PostgreSQL injoignable")
    a = _chat(client, "Quel est le relief de la préfecture des Lacs ?")["answer"]
    assert "préfecture Lacs" in a and "moins de 10 m" in a
    first = _chat(client, "Parle-moi de Kpalimé")
    a = _chat(client, "Et la température la nuit ?", thread_id=first["thread_id"])["answer"]
    assert "Kpalimé" in a and "nuit" in a


@pytest.mark.m25
@pytest.mark.real_data
@pytest.mark.usefixtures("ingested")
def test_general_search_excludes_fiches(client):
    if not _db_up():
        pytest.skip("PostgreSQL injoignable")
    hits = retrieve.search("normale pluie tendance", k=5, exclude_fiches=True)
    assert hits and not any(h.file.startswith("fiches/") for h in hits)

"""Nœuds du graphe LangGraph : route → fetch_data → retrieve → generate (M25/M26).

Chaque nœud publie son étape (`status`) et `generate` publie les morceaux de texte (`token`)
via le flux « custom » de LangGraph ; chatbot.graph les transforme en événements SSE.
"""
import operator
import re
import unicodedata
from typing import Annotated, Optional, TypedDict

from langgraph.config import get_stream_writer

from backend.core.constants import DISCLAIMER
from backend.core.exceptions import ApiError
from backend.services import indicators as ind_service
from backend.services import regions as region_service
from chatbot.llm import client as llm
from chatbot.prompts import templates
from chatbot.tools import data as data_tools
from chatbot.tools import retrieve

HISTORY_TURNS = 6  # tours précédents envoyés au LLM

REGION_WORDS = {
    "maritime": ("maritime", "lome", "aneho", "tsevie", "golfe", "lacs", "vo", "zio", "yoto", "ave"),
    "plateaux": ("plateaux", "plateau", "atakpame", "kpalime", "badou", "notse", "amlame"),
    "centrale": ("centrale", "central", "sokode", "tchamba", "blitta", "sotouboua"),
    "kara": ("kara", "bassar", "niamtougou", "bafilo", "kante"),
    "savanes": ("savanes", "savane", "dapaong", "mango", "oti", "cinkasse", "tandjoare"),
}
INDICATOR_WORDS = {
    "precipitation": ("pluie", "pluies", "pluvio", "precipitation", "precipitations", "secheresse", "inondation",
                      "inondations", "rain", "rainfall", "pleut", "humidite"),
    "ndvi": ("vegetation", "verdure", "ndvi", "vert", "verte", "foret", "pature", "paturages", "culture", "cultures",
             "recolte", "vegetation"),
    "lst_day": ("temperature", "chaleur", "chaud", "canicule", "lst", "heat", "temperatures"),
    "elevation": ("altitude", "relief", "montagne", "elevation", "pente"),
}
# Racines comparées par préfixe (climatique, agriculture…) puis mots exacts
TOPIC_STEMS = ("climat", "environnement", "agricult", "meteo", "satellit", "secheress", "vegetal", "pluviom")
TOPIC_WORDS = {"saison", "saisons", "semis", "semer", "sol", "sols", "eau", "nasa", "togo", "tendance", "normale",
               "anomalie", "champ", "champs", "planter", "region", "regions", "carte", "donnee", "donnees",
               "cultiver", "recoltes", "elevage"}


class ChatState(TypedDict, total=False):
    message: str
    profile: Optional[str]
    mode: str
    lang: str
    region_hint: Optional[str]
    location: Optional[tuple[float, float]]
    region_id: Optional[str]          # conservé d'un tour à l'autre (mémoire du fil)
    indicators: list[str]
    off_topic: bool
    facts: list[dict]
    sources: list[dict]
    snapshots: list[dict]
    docs: list[dict]
    answer: str
    statements: list[dict]
    history: Annotated[list[dict], operator.add]


def _norm(text: str) -> list[str]:
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.findall(r"[a-z0-9]+", text)


def _status(step: str) -> None:
    get_stream_writer()({"status": step})


# ─────────── route ───────────
async def route(state: ChatState) -> dict:
    _status("routing")
    words = set(_norm(state["message"]))
    region_id = state.get("region_hint")
    if not region_id and state.get("location"):
        try:
            region_id = region_service.locate(*state["location"]).id
        except ApiError:
            region_id = None
    if not region_id:
        region_id = next((rid for rid, ws in REGION_WORDS.items() if words & set(ws)), None)
    inds = [i for i, ws in INDICATOR_WORDS.items() if words & set(ws)]
    on_topic = bool(region_id or inds or words & TOPIC_WORDS or any(w.startswith(t) for w in words for t in TOPIC_STEMS))
    # Question de suite (« Et à Kara ? ») : on garde la région / l'indicateur du tour précédent
    if not region_id and on_topic:
        region_id = state.get("region_id")
    if not inds and state.get("indicators"):
        inds = state["indicators"]
    return {"region_id": region_id, "indicators": inds, "off_topic": not on_topic,
            "facts": [], "sources": [], "snapshots": [], "docs": []}


def after_route(state: ChatState) -> str:
    return "generate" if state.get("off_topic") else "fetch_data"


# ─────────── fetch_data ───────────
async def fetch_data(state: ChatState) -> dict:
    _status("fetching_data")
    region_id = state.get("region_id")
    if not region_id:
        return {}
    wanted = state.get("indicators") or list(ind_service.TS_INDICATORS)
    ts_inds = [i for i in wanted if i in ind_service.TS_INDICATORS]
    try:
        snaps = data_tools.snapshots(region_id, ts_inds) if ts_inds else []
        facts, sources = data_tools.facts_and_sources(region_id, snaps)
        if "elevation" in wanted:
            extra = data_tools.elevation_fact(region_id)
            if extra:
                facts.append(extra[0])
                sources.append(extra[1])
        public = {s.indicator: s for s in ind_service.summary(region_id, None, state.get("mode", "public")).indicators}
    except ApiError:
        return {}
    return {"facts": facts, "sources": [s.model_dump() for s in sources],
            "snapshots": [public[s.indicator].model_dump() for s in snaps]}


# ─────────── retrieve ───────────
async def retrieve_docs(state: ChatState) -> dict:
    _status("retrieving")
    inds = state.get("indicators") or []
    chunks = retrieve.search(state["message"], k=3, indicator=inds[0] if len(inds) == 1 else None,
                             region_id=state.get("region_id"))
    docs = [{"source_id": c.source_id, "title": c.title, "content": c.snippet(700), "url": c.source_url,
             "snippet": c.snippet()} for c in chunks]
    return {"docs": docs}


# ─────────── generate ───────────
def _template_answer(state: ChatState) -> str:
    lang = state.get("lang", "fr")
    if state.get("off_topic"):
        return templates.OFF_TOPIC.get(lang, templates.OFF_TOPIC["fr"])
    region_id = state.get("region_id")
    parts = []
    if region_id and state.get("snapshots"):
        name = region_service.get_region(region_id).name
        parts.append(f"Voici ce que montrent les satellites pour la région {name} :")
        parts += [s["plain_summary"] for s in state["snapshots"]]
    elif region_id and state.get("facts"):
        parts += [f["text"] for f in state["facts"]]
    else:
        parts.append("Précisez une région du Togo (Maritime, Plateaux, Centrale, Kara ou Savanes) pour que je "
                     "vous donne les observations satellites correspondantes.")
    if state.get("docs"):
        parts.append(f"Pour en savoir plus : « {state['docs'][0]['title']} ».")
    parts.append(DISCLAIMER)
    return " ".join(parts)


def _statements(state: ChatState) -> list[dict]:
    by_ind = {f["indicator"]: f for f in state.get("facts", [])}
    out = []
    for s in state.get("snapshots", []):
        f = by_ind.get(s["indicator"])
        if f and s.get("value") is not None:
            out.append({"text": s["plain_summary"], "nature": "observed", "source_ids": [f["source_id"]]})
    if "elevation" in by_ind:
        f = by_ind["elevation"]
        out.append({"text": f["text"], "nature": "observed", "source_ids": [f["source_id"]]})
    return out


async def generate(state: ChatState) -> dict:
    _status("generating")
    write = get_stream_writer()
    answer = ""
    if llm.available() and not state.get("off_topic"):
        history = [{"role": h["role"], "content": h["content"]} for h in state.get("history", [])[-2 * HISTORY_TURNS:]]
        user = (f"{templates.context_block(state.get('facts', []), state.get('docs', []))}\n\n"
                f"QUESTION : {state['message']}")
        try:
            async for piece in llm.stream_text(templates.system_prompt(state.get("profile"), state.get("mode", "public"),
                                                                       state.get("lang", "fr")),
                                               history + [{"role": "user", "content": user}]):
                answer += piece
                write({"token": piece})
        except llm.LLMUnavailable:
            answer = ""  # repli sur le gabarit (si rien n'a encore été envoyé)
    if not answer:
        answer = _template_answer(state)
        for word in answer.split(" "):
            write({"token": word + " "})
    docs = state.get("docs", [])
    doc_sources = [{"id": d["source_id"], "kind": "document", "title": d["title"], "url": d["url"],
                    "snippet": d["snippet"]} for d in docs]
    return {"answer": answer.strip(), "statements": _statements(state),
            "sources": state.get("sources", []) + doc_sources,
            "history": [{"role": "user", "content": state["message"]}, {"role": "assistant", "content": answer.strip()}]}

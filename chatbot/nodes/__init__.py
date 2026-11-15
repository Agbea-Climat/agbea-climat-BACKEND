"""Nœuds du graphe LangGraph : route → fetch_data → retrieve → generate (M25/M26).

Chaque nœud publie son étape (`status`) et `generate` publie les morceaux de texte (`token`)
via le flux « custom » de LangGraph ; chatbot.graph les transforme en événements SSE.

- route      : région, indicateurs, date demandée (« juillet 2024 », « en 2015 », « last year »…) et
               intention (value | trend | calendar | forecast), ou hors sujet ; une question de suite
               (« Et en septembre 2025 ? ») reprend la région, l'indicateur et l'intention du tour précédent ;
- fetch_data : faits chiffrés et datés via backend.services (chatbot.tools.data) ;
- retrieve   : morceaux du corpus (un par document), passages du calendrier agricole ;
- generate   : LLM sous garde-fous (chatbot.guard) ou gabarit. Une demande de prévision a toujours la
               réponse gabarit (« AGBÉA CLIMAT ne fait pas de prévision… ») : jamais de texte prédictif.
               L'avertissement DISCLAIMER termine toujours la réponse.
"""
import logging
import operator
import re
from typing import Annotated, Optional, TypedDict

from langgraph.config import get_stream_writer

from backend.core.exceptions import ApiError
from backend.services import catalog
from backend.services import indicators as ind_service
from backend.services import regions as region_service
from chatbot import guard
from chatbot.llm import client as llm
from chatbot.prompts import i18n, templates
from chatbot.tools import data as data_tools
from chatbot.tools import question, retrieve

log = logging.getLogger(__name__)

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
                      "inondations", "rain", "rainfall", "rains", "rained", "raining", "pleut", "plu", "pleuvoir",
                      "pleuvra", "pluvieux", "pluvieuse", "humidite", "drought", "flood", "floods"),
    "ndvi": ("vegetation", "verdure", "ndvi", "vert", "verte", "foret", "pature", "paturages", "culture", "cultures",
             "recolte", "greenness", "vegetal", "forest", "crops"),
    "lst_day": ("temperature", "chaleur", "chaud", "canicule", "lst", "heat", "temperatures", "hot"),
    "elevation": ("altitude", "relief", "montagne", "elevation", "pente", "altitudes"),
}
# Racines comparées par préfixe (climatique, agriculture…) puis mots exacts
TOPIC_STEMS = ("climat", "environnement", "environment", "agricult", "meteo", "satellit", "secheress", "vegetal",
               "pluviom", "weather")
TOPIC_WORDS = {"saison", "saisons", "semis", "semer", "sol", "sols", "eau", "nasa", "togo", "tendance", "normale",
               "anomalie", "champ", "champs", "planter", "region", "regions", "carte", "donnee", "donnees",
               "cultiver", "recoltes", "elevage", "season", "seasons", "soil", "water", "farm", "farming"}
FOLLOW_UP_FIRST = {"et", "and"}


class ChatState(TypedDict, total=False):
    message: str
    profile: Optional[str]
    mode: str
    lang: str
    region_hint: Optional[str]
    location: Optional[tuple[float, float]]
    region_id: Optional[str]          # conservé d'un tour à l'autre (mémoire du fil)
    indicators: list[str]
    intent: str                       # value | trend | calendar | forecast
    date_req: Optional[dict]          # {"kind": "month"|"year"|"month_only", "value": ...}
    off_topic: bool
    facts: list[dict]
    sources: list[dict]
    snapshots: list[dict]
    series: list[dict]
    recency: Optional[str]
    docs: list[dict]
    passages: list[dict]
    notes: list[dict]                 # phrases « interpreted » sourcées (passages, limites des données)
    answer: str
    statements: list[dict]
    history: Annotated[list[dict], operator.add]


def _status(step: str) -> None:
    get_stream_writer()({"status": step})


def _style(state: ChatState) -> str:
    profile = next((p for p in catalog.PROFILES if p.id == state.get("profile")), None)
    return "scientific" if state.get("mode") == "scientific" or (profile and profile.default_mode == "scientific") \
        else "public"


# ─────────── route ───────────
async def route(state: ChatState) -> dict:
    _status("routing")
    msg = state["message"]
    ws_list = question.words(msg)
    ws = set(ws_list)
    region_id = state.get("region_hint")
    if not region_id and state.get("location"):
        try:
            region_id = region_service.locate(*state["location"]).id
        except ApiError:
            region_id = None
    if not region_id:
        # ordre de la phrase, négation « pas à X », mots ambigus seulement en contexte (question.regions_in)
        region_id = next(iter(question.regions_in(msg)), None)
    inds = [i for i, words in INDICATOR_WORDS.items() if ws & set(words)]
    explicit = question.intent(msg)
    date_req = question.parse_date(msg)
    prev_region = state.get("region_id")
    follow_up = bool(ws_list) and (ws_list[0] in FOLLOW_UP_FIRST or (date_req is not None and len(ws_list) <= 5))
    on_topic = bool(region_id or inds or explicit or ws & TOPIC_WORDS
                    or any(w.startswith(t) for w in ws for t in TOPIC_STEMS)
                    or (prev_region and follow_up))
    if not on_topic:  # hors sujet : on garde le contexte du fil pour la question suivante
        return {"off_topic": True, "facts": [], "sources": [], "snapshots": [], "series": [], "docs": [],
                "passages": [], "notes": [], "recency": None}
    if not region_id:
        region_id = prev_region
    # Une date explicite dans un suivi (« Et en juillet 2024 ? ») remplace l'intention héritée (prévision, tendance…)
    inherited = state.get("intent") if follow_up and state.get("intent") and date_req is None else None
    intent = explicit or inherited or "value"
    if not inds:
        if follow_up and state.get("indicators"):
            inds = state["indicators"]
        elif intent in ("forecast", "calendar"):
            inds = ["precipitation"]
    if date_req is None and follow_up and intent == state.get("intent"):
        date_req = state.get("date_req")
    return {"region_id": region_id, "indicators": inds, "intent": intent, "date_req": date_req,
            "off_topic": False, "facts": [], "sources": [], "snapshots": [], "series": [], "docs": [],
            "passages": [], "notes": [], "recency": None}


def after_route(state: ChatState) -> str:
    return "generate" if state.get("off_topic") else "fetch_data"


# ─────────── fetch_data ───────────
async def fetch_data(state: ChatState) -> dict:
    _status("fetching_data")
    region_id = state.get("region_id")
    if not region_id:
        return {}
    intent = state.get("intent", "value")
    wanted = state.get("indicators") or list(ind_service.TS_INDICATORS)
    ts_inds = [i for i in wanted if i in ind_service.TS_INDICATORS]
    date_req = state.get("date_req")
    col = data_tools.Collector(region_id, state.get("lang", "fr"), state.get("mode", "public"), _style(state))
    try:
        for ind in ts_inds:
            if intent == "trend":
                col.trend(ind)
            elif intent == "forecast" or date_req is None:  # calendrier + date : valeurs du mois demandé
                col.latest(ind)
            elif date_req["kind"] == "month":
                col.month(ind, date_req["value"])
            elif date_req["kind"] == "year":
                col.year(ind, date_req["value"])
            else:
                col.month_only(ind, date_req["value"])
        if "elevation" in wanted:
            col.elevation()
    except ApiError:
        log.exception("fetch_data")
    out = col.dump()
    # La date de la donnée la plus récente est dite quand l'utilisateur n'a pas demandé de date
    out["recency"] = col.recency_text() if intent != "trend" and (date_req is None or intent != "value") else None
    return out


# ─────────── retrieve ───────────
def _doc_dict(c: retrieve.Chunk, source_id: str) -> dict:
    return {"source_id": source_id, "file": c.file, "title": c.title, "content": c.snippet(700), "url": c.source_url,
            "snippet": c.snippet()}


async def retrieve_docs(state: ChatState) -> dict:
    _status("retrieving")
    inds = state.get("indicators") or []
    region_id = state.get("region_id")
    intent = state.get("intent", "value")
    msg = state["message"]
    lang = state.get("lang", "fr")
    chunks: list[retrieve.Chunk] = []
    passages_raw: list[tuple[retrieve.Chunk, str]] = []
    if intent == "calendar":
        cal = retrieve.search(f"{msg} calendrier semis récolte saison des pluies", k=4, files=[retrieve.CALENDAR_FILE])
        passages_raw = retrieve.passages(cal, msg, region_id)
        chunks += cal
    limits: list[retrieve.Chunk] = []
    if intent == "trend" and "lst_day" in (inds or ind_service.TS_INDICATORS):
        limits = retrieve.search("température du sol dérive Terra tendances 2020 décembre 2022", k=1,
                                 files=[retrieve.LIMITS_FILE])
        chunks += limits
    chunks += retrieve.search(msg, k=3, indicator=inds[0] if len(inds) == 1 else None, region_id=region_id)
    # Une source par document : l'id du premier morceau retenu de chaque fichier
    file_ids: dict[str, str] = {}
    for c in chunks:
        file_ids.setdefault(c.file, c.source_id)
    docs = [_doc_dict(c, file_ids[c.file]) for c in retrieve.dedupe(chunks)]
    passages = [{"source_id": file_ids[c.file], "file": c.file, "title": c.title, "text": text}
                for c, text in passages_raw]
    notes = [{"text": p["text"], "nature": "interpreted", "source_ids": [p["source_id"]]} for p in passages]
    if intent == "trend" and "lst_day" in (inds or ind_service.TS_INDICATORS) and any(
            f["indicator"] == "lst_day" for f in state.get("facts", [])):
        src = [file_ids[limits[0].file]] if limits else [f"ds:{catalog.dataset_for('lst_day').id}"]
        notes.append({"text": i18n.t("trend_lst", lang), "nature": "interpreted", "source_ids": src})
    # Les passages cités deviennent le snippet de la source du document
    for d in docs:
        quoted = [p["text"] for p in passages if p["file"] == d["file"]]
        if quoted:
            d["snippet"] = " … ".join(quoted)
    return {"docs": docs, "passages": passages, "notes": notes}


# ─────────── generate ───────────
def _template_answer(state: ChatState, with_disclaimer: bool = True) -> str:
    lang = state.get("lang", "fr")
    intent = state.get("intent", "value")
    region_id = state.get("region_id")
    parts: list[str] = []
    if intent == "forecast":
        parts.append(i18n.t("no_forecast", lang))
    if intent == "calendar":
        passages = state.get("passages") or []
        if passages:
            parts.append(i18n.t("calendar_intro", lang, title=passages[0]["title"]))
            parts += [f"— {p['text']}" for p in passages]
            parts.append(i18n.t("calendar_caveat", lang))
        else:
            parts.append(i18n.t("calendar_none", lang))
    facts = state.get("facts") or []
    if region_id and facts:
        parts.append(i18n.t("intro", lang, region=region_service.get_region(region_id).name))
        parts += [f["text"] for f in facts]
        if state.get("recency"):
            parts.append(state["recency"])
    elif not region_id and intent != "calendar":
        parts.append(i18n.t("need_region", lang))
    parts += [n["text"] for n in state.get("notes", []) if n not in _passage_notes(state)]
    if intent == "trend" and facts:
        parts.append(i18n.t("trend_note", lang))
    docs = [d for d in state.get("docs", []) if d["file"] != retrieve.CALENDAR_FILE or intent != "calendar"]
    if docs:
        parts.append(i18n.t("more", lang, title=docs[0]["title"]))
    if with_disclaimer:
        parts.append(i18n.disclaimer_text(lang))
    return "\n".join(parts)


def _passage_notes(state: ChatState) -> list[dict]:
    ids = {p["text"] for p in state.get("passages", [])}
    return [n for n in state.get("notes", []) if n["text"] in ids]


def _statements(state: ChatState) -> list[dict]:
    out = [{"text": f["text"], "nature": "observed", "source_ids": f["source_ids"]} for f in state.get("facts", [])]
    out += [{"text": n["text"], "nature": "interpreted", "source_ids": n["source_ids"]} for n in state.get("notes", [])]
    return out


def _emit_words(write, text: str) -> None:
    for piece in re.findall(r"\S+\s*", text):
        write({"token": piece})


async def _llm_answer(state: ChatState, write) -> str:
    """Réponse du LLM, phrase par phrase après contrôle des chiffres et des prévisions.

    Échec avant tout envoi → "" (l'appelant passe au gabarit). Échec en plein flux → note explicite
    puis réponse gabarit : la réponse n'est jamais tronquée en silence."""
    lang = state.get("lang", "fr")
    facts, passages, docs = state.get("facts", []), state.get("passages", []), state.get("docs", [])
    system = templates.system_prompt(state.get("profile"), state.get("mode", "public"), lang)
    known = guard.known_numbers([f["text"] for f in facts] + [s for f in facts for s in f["source_ids"]]
                                + [p["text"] for p in passages] + [d["content"] for d in docs] + [system]
                                + [n["text"] for n in state.get("notes", [])])
    history = [{"role": h["role"], "content": h["content"]} for h in state.get("history", [])[-2 * HISTORY_TURNS:]]
    user = f"{templates.context_block(facts, docs, passages)}\n\nQUESTION : {state['message']}"
    gate = guard.SentenceGate(known)
    sent = ""
    try:
        async for piece in llm.stream_text(system, history + [{"role": "user", "content": user}]):
            out = gate.feed(piece)
            if out:
                write({"token": out})
                sent += out
        out = gate.close()
        if out:
            write({"token": out})
            sent += out
    except Exception as e:  # noqa: BLE001 — LLMUnavailable, réseau, SDK : repli propre
        log.warning("LLM (chat) interrompu : %s", e)
        if not sent:
            return ""
        tail = f"\n\n{i18n.t('interrupted', lang)}\n{_template_answer(state)}"
        _emit_words(write, tail)
        return sent + tail
    if gate.dropped:
        log.info("garde-fou : %d phrase(s) du LLM retirée(s)", len(gate.dropped))
    return sent


async def generate(state: ChatState) -> dict:
    _status("generating")
    write = get_stream_writer()
    lang = state.get("lang", "fr")
    if state.get("off_topic"):
        answer = f"{i18n.t('off_topic', lang)}\n\n{i18n.disclaimer_text(lang)}"
        _emit_words(write, answer)
        return {"answer": answer, "statements": [], "sources": [],
                "history": [{"role": "user", "content": state["message"]}, {"role": "assistant", "content": answer}]}
    answer = ""
    # Demande de prévision : toujours le gabarit (refus explicite + observations datées), jamais le LLM
    if llm.available() and state.get("intent") != "forecast":
        answer = await _llm_answer(state, write)
    if not answer.strip():
        answer = _template_answer(state)
        _emit_words(write, answer)
    final = guard.ensure_disclaimer(answer, lang)
    if final != answer.rstrip():
        _emit_words(write, final[len(answer.rstrip()):])
    final = final.strip()
    docs = state.get("docs", [])
    doc_sources = [{"id": d["source_id"], "kind": "document", "title": d["title"], "url": d["url"],
                    "snippet": d["snippet"]} for d in docs]
    return {"answer": final, "statements": _statements(state),
            "sources": state.get("sources", []) + doc_sources,
            "history": [{"role": "user", "content": state["message"]}, {"role": "assistant", "content": final}]}

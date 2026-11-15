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
from chatbot.tools import question, retrieve, zones

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
# « Qu'est-ce qu'une normale ? », « c'est quoi le NDVI », « what is… » : réponse depuis le glossaire
DEFINITION = re.compile(r"\b(qu est[ -]ce|c est quoi|que veut dire|que signifie|signification|definition|definir|"
                        r"what is|what does|meaning of)\b")
GREETINGS = {"bonjour", "bonsoir", "salut", "hello", "hi", "hey", "coucou", "yo"}
# Nom lisible d'un document du corpus dans une phrase (« D'après notre glossaire : »)
DOC_LABELS = {
    "glossaire_faq.md": ("notre glossaire", "our glossary"),
    "methodologie_agbea.md": ("la méthodologie d'AGBÉA CLIMAT", "the AGBÉA CLIMAT methodology"),
    "limites_donnees_agbea.md": ("notre page sur les limites des données", "our page on the data limits"),
    "calendrier_agricole_togo.md": ("le calendrier agricole de la FAO et de l'UNICEF",
                                    "the FAO and UNICEF crop calendar"),
    "climat_togo_tendances.md": ("le rapport de l'UNICEF sur le climat du Togo",
                                 "the UNICEF report on Togo's climate"),
}
# Température de nuit : absente de l'API (lst_day seulement), présente dans les fiches de zone (tendances)
NIGHT_WORDS = {"nuit", "nuits", "nocturne", "nocturnes", "night", "nights", "nighttime"}


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
    zone: Optional[dict]              # préfecture ou site cité (chatbot.tools.zones.Zone.as_dict)
    night: bool                       # question sur la température de nuit
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
    zone = zones.find(msg)                       # préfecture ou site pilote (fiche du corpus)
    if not region_id and zone and zone.region_id:
        region_id = zone.region_id
    night = bool(ws & NIGHT_WORDS)
    inds = [i for i, words in INDICATOR_WORDS.items() if ws & set(words)]
    if night and "lst_day" in inds:
        # l'API n'a que la température du sol le jour : la nuit se lit dans la fiche de zone (tendances)
        inds = [i for i in inds if i != "lst_day"] or ["lst_night"]
    explicit = question.intent(msg)
    date_req = question.parse_date(msg)
    prev_region = state.get("region_id")
    follow_up = bool(ws_list) and (ws_list[0] in FOLLOW_UP_FIRST or (date_req is not None and len(ws_list) <= 5))
    on_topic = bool(region_id or zone or inds or explicit or ws & TOPIC_WORDS
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
    prev_zone = state.get("zone")
    zone_d = zone.as_dict() if zone else (
        prev_zone if follow_up and prev_zone and prev_zone.get("region_id") == region_id else None)
    return {"region_id": region_id, "indicators": inds, "intent": intent, "date_req": date_req,
            "zone": zone_d, "night": night, "off_topic": False, "facts": [], "sources": [], "snapshots": [], "series": [], "docs": [],
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
        passages_raw = _calendar_passages(cal, msg, region_id)
        chunks += cal
    limits: list[retrieve.Chunk] = []
    if intent == "trend" and "lst_day" in (inds or ind_service.TS_INDICATORS):
        limits = retrieve.search("température du sol dérive Terra tendances 2020 décembre 2022", k=1,
                                 files=[retrieve.LIMITS_FILE])
        chunks += limits
    # Fiche de la zone citée (préfecture, site), ou de la région pour une tendance / la température de nuit :
    # cherchée directement par son nom de fichier, puis ses lignes utiles extraites (chatbot.tools.zones)
    zone = state.get("zone")
    fiche = zone["file"] if zone else None
    if not fiche and region_id and (intent == "trend" or state.get("night")):
        rf = zones.region_fiche(region_id)
        fiche = rf.file if rf else None
    zone_raw: list[tuple[retrieve.Chunk, str]] = []
    if fiche:
        fc = retrieve.search(msg, k=3, files=[fiche])
        zone_raw = retrieve.passages(fc, _fiche_query(state, fiche), None, max_n=4)
        if state.get("night"):   # question sur la nuit : pas les lignes de température de jour
            zone_raw = [(c, u) for c, u in zone_raw if "le jour" not in u and "en journée" not in u]
        topic = {"precipitation": ("pluie", "pluvieux"), "ndvi": ("végétation", "verdure", "NDVI", "verte"),
                 "lst_day": ("température",), "lst_night": ("nuit",), "elevation": ("altitude", "mètres", " m ")}
        words = [w for i in inds for w in topic.get(i, ())]
        if words:                # question sur un indicateur : pas les lignes des autres
            zone_raw = [(c, u) for c, u in zone_raw if any(w.lower() in u.lower() for w in words)] or zone_raw
        chunks = fc + chunks
    general = retrieve.search(msg, k=5, indicator=inds[0] if len(inds) == 1 else None, region_id=region_id,
                              exclude_fiches=True)
    chunks += general
    # Sans région ni zone : les données de l'API ne répondent pas, on cite le document général le plus proche
    doc_raw: list[tuple[retrieve.Chunk, str]] = []
    if not region_id and not zone and intent != "calendar" and general:
        # meilleures lignes des 2 documents les plus proches (recherche lexicale : le 1er n'est pas toujours le bon)
        kws = retrieve.keywords(msg)
        # 3 documents les plus proches, lus en entier (jusqu'à 4 morceaux) : on garde celui dont la meilleure
        # ligne répond le mieux à la question (à égalité : le plus proche dans la recherche)
        files = list(dict.fromkeys(c.file for c in general))[:3]
        if DEFINITION.search(question.normalize(msg)) and "glossaire_faq.md" not in files:
            files.insert(0, "glossaire_faq.md")
        candidates = {f: retrieve.search(msg, k=4, files=[f]) for f in files}

        def best_line(f: str) -> int:
            return max((retrieve.unit_score(h, u, kws) for c in candidates[f]
                        for h, u in retrieve._units(c.content, with_heading=True)), default=0)
        # à score égal : les documents qui expliquent l'application (glossaire, méthodologie, limites, indicateurs)
        # passent avant les documents de contexte (rapport UNICEF, calendrier) ; puis le plus proche
        explains = lambda f: f in retrieve.APP_DOCS or f.startswith(("comprendre_", "fiche_"))  # noqa: E731
        definition = bool(DEFINITION.search(question.normalize(msg)))
        chosen = max(candidates, key=lambda f: (best_line(f), definition and f == "glossaire_faq.md", explains(f)))
        doc_raw = retrieve.best_passages(candidates[chosen], msg, max_n=3)
        chunks += [c for c in candidates[chosen] if c not in chunks]
    # Une source par document : l'id du premier morceau retenu de chaque fichier
    file_ids: dict[str, str] = {}
    for c in chunks:
        file_ids.setdefault(c.file, c.source_id)
    docs = [_doc_dict(c, file_ids[c.file]) for c in retrieve.dedupe(chunks)]
    passages = [{"source_id": file_ids[c.file], "file": c.file, "title": c.title, "text": text, "kind": kind}
                for kind, raw in (("calendar", passages_raw), ("zone", zone_raw), ("doc", doc_raw))
                for c, text in raw]
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


def _calendar_passages(cal: list, msg: str, region_id: Optional[str]) -> list:
    rows = retrieve.passages(cal, msg, region_id, max_n=12)
    crops = question.crops(msg)
    region = region_service.get_region(region_id).name if region_id else None
    crop_rows = [(c, u) for c, u in rows if "semis en" in u and any(cr in question.normalize(u) for cr in crops)]
    zone_rows = [(c, u) for c, u in rows if ", zone " in u and region and region in u]
    caveat = [(c, u) for c, u in rows if u.startswith("Attention, les deux sources") and region_id in ("centrale", "kara")]
    chosen = crop_rows[:2] + zone_rows[:1] + caveat
    if not crop_rows and crops:   # culture absente du calendrier : rangées de toutes les cultures
        chosen = [(c, u) for c, u in rows if "semis en" in u][:3] + zone_rows[:1] + caveat
    return chosen or rows[:3]


def _fiche_query(state: ChatState, fiche: str) -> str:
    """Mots-clés pour choisir les lignes de la fiche : la question sans le nom de la zone (présent sur toutes
    les lignes « Où »), plus le sujet (nuit, tendance) ; à défaut, un aperçu général."""
    z = zones.by_file(fiche)
    name_words = set(question.words(z.name)) if z else set()
    kws = [w for w in question.words(state["message"]) if w not in name_words]
    if state.get("night"):
        kws += ["nuit", "temperature"]
    if state.get("intent") == "trend":
        kws += ["tendance", "hausse", "baisse"]
    # mots de niveau présents dans toutes les fiches (« préfecture », « site »…) : pas discriminants
    level_words = {"prefecture", "prefectures", "site", "sites", "pilote", "pilotes", "region", "regions", "zone", "zones"}
    useful = [w for w in kws if w not in retrieve._STOP and w not in level_words and len(w) > 2]
    return " ".join(useful) if useful else "pluie altitude tendance"


# ─────────── generate ───────────
def _template_answer(state: ChatState, with_disclaimer: bool = True) -> str:
    lang = state.get("lang", "fr")
    intent = state.get("intent", "value")
    region_id = state.get("region_id")
    parts: list[str] = []
    if intent == "forecast":
        parts.append(i18n.t("no_forecast", lang))
    all_passages = state.get("passages") or []
    zone_p = [p for p in all_passages if p.get("kind") == "zone"]
    if state.get("date_req") and state.get("facts") and not state.get("night"):
        zone_p = []   # mois ou année précis déjà répondu par les données : la fiche n'ajoute que du bruit
    doc_p = [p for p in all_passages if p.get("kind") == "doc"]
    if intent == "calendar":
        passages = [p for p in all_passages if p.get("kind", "calendar") == "calendar"]
        if passages:
            parts.append(i18n.t("calendar_intro", lang, title=_doc_label(passages[0], lang)))
            parts += [p["text"] for p in passages]
            parts.append(i18n.t("calendar_caveat", lang))
        else:
            parts.append(i18n.t("calendar_none", lang))
    facts = state.get("facts") or []
    zone = state.get("zone")
    if region_id and facts and zone and zone.get("level") in ("prefecture", "site")             and any(f.get("has_value") for f in facts):
        # préfecture ou site cité : dire que les chiffres du mois sont ceux de la région qui le contient
        parts.append(i18n.t("zone_region", lang, region=region_service.get_region(region_id).name,
                            zone=_zone_name(zone["title"])))
    if region_id and facts:
        parts += [f["text"] for f in facts]
        if state.get("recency"):
            parts.append(state["recency"])
    if zone_p:
        parts.append(i18n.t("zone_intro", lang, title=_zone_name(zone_p[0]["title"])))
        parts += [p["text"] for p in zone_p]
    if doc_p:
        parts.append(i18n.t("calendar_intro", lang, title=_doc_label(doc_p[0], lang)))
        parts += [p["text"] for p in doc_p]
    if not region_id and intent != "calendar" and not zone_p and not doc_p:
        parts.append(i18n.t("need_region", lang))
    parts += [n["text"] for n in state.get("notes", []) if n not in _passage_notes(state)]
    if intent == "trend" and facts:
        parts.append(i18n.t("trend_note", lang))
    if with_disclaimer:
        parts.append(i18n.disclaimer_text(lang))
    return "\n".join(parts)


def _zone_name(title: str) -> str:
    """« Fiche climatique AGBÉA : site pilote Kpalimé & Mont Agou » → « le site pilote Kpalimé et Mont Agou »."""
    name = title.split(":", 1)[-1].strip().replace(" & ", " et ")
    if name.startswith(("préfecture", "site", "Togo")):
        return ("le " if name.startswith("site") else "la " if name.startswith("préfecture") else "le ") + name
    if name.startswith("région"):
        return "la " + name
    return name


def _doc_label(passage: dict, lang: str) -> str:
    fr, en = DOC_LABELS.get(passage["file"], (None, None))
    if fr:
        return fr if lang != "en" else en
    title = passage["title"].split(" (")[0]
    return (f"le document {title}" if lang != "en" else f"the document {title}")


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
        hello = i18n.t("greeting", lang) if set(question.words(state["message"])) & GREETINGS else ""
        answer = f"{hello}{i18n.t('off_topic', lang)}\n\n{i18n.disclaimer_text(lang)}"
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

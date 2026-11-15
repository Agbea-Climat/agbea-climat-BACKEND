"""POST /explain (M24) : explication d'un indicateur pour une région et un mois.

1. Contrôles : indicateur sans données (land_cover) → 501 in_development ; date mal formée ou hors de
   la période des données → 400 invalid_period (aussi pour l'altitude, qui ignore la date) ;
2. Faits : valeur du mois via M14 (source `computed:<region>:<indicator>:<date>` + `ds:<dataset>`),
   chacun daté ; mois sans valeur → on le dit, puis la dernière valeur disponible, datée, et rien d'autre ;
3. Documents : 3 à 5 morceaux du corpus filtrés par indicateur (un par document) ;
4. LLM en sortie structurée (Statement[]), ton selon le profil et le mode, seulement quand la valeur existe.

Garde-fous LLM : source inconnue → phrase retirée ; « observed » = source calculée + chiffres des faits ;
« interpreted » = chiffres des faits ou des documents qu'elle cite ; phrase prédictive retirée ; jamais de
« predicted » ; si aucune phrase observée ne passe, la phrase gabarit datée est remise en tête.
Sans LLM (ou si rien ne passe) : phrases par gabarit. Le conseil (« interpreted ») porte toujours sur
l'indicateur demandé et cite la source de SA valeur.
"""
from typing import Literal, Optional

from pydantic import BaseModel, Field

from backend.core.constants import DISCLAIMER
from backend.core.exceptions import NotImplementedYet
from backend.schemas import ExplainRequest, ExplainResponse, IndicatorSnapshot, Source, Statement
from backend.services import catalog, indicators, regions
from chatbot import guard
from chatbot.llm import client as llm
from chatbot.prompts import i18n, templates
from chatbot.tools import data as data_tools
from chatbot.tools import retrieve

N_DOCS = 4


class _LLMStatement(BaseModel):
    text: str
    nature: Literal["observed", "interpreted"]
    source_ids: list[str] = Field(min_length=1)


class _LLMExplain(BaseModel):
    title: str
    statements: list[_LLMStatement]


def _check(statements: list[_LLMStatement], allowed: set[str], computed: set[str], facts_text: str,
           doc_text: Optional[dict[str, str]] = None) -> list[Statement]:
    known = guard.known_numbers([facts_text])
    doc_nums = {sid: guard.quantities(t) for sid, t in (doc_text or {}).items()}
    out = []
    for s in statements:
        if not s.source_ids or not set(s.source_ids) <= allowed or guard.is_predictive(s.text):
            continue
        if s.nature == "observed":
            if not set(s.source_ids) & computed or not guard.numbers_ok(s.text, known):
                continue
        else:
            ok = set(known)
            for sid in s.source_ids:
                ok |= doc_nums.get(sid, set())
            if not guard.numbers_ok(s.text, ok):
                continue
        out.append(Statement(text=s.text, nature=s.nature, source_ids=s.source_ids))
    return out


# ─────────── Interprétation par gabarit (indicateur demandé uniquement) ───────────
INTERPRET = {
    "precipitation": {
        ("rainy", "below_normal"): {
            "fr": "Pluie plus faible que d'habitude pour ce mois de saison des pluies : le sol peut manquer d'eau, "
                  "vérifiez son humidité sur place avant de semer.",
            "en": "Less rain than usual for this rainy-season month: the soil may lack water, check its moisture "
                  "on site before sowing."},
        ("rainy", "above_normal"): {
            "fr": "Pluie plus forte que d'habitude : surveillez l'eau stagnante dans les champs bas et l'érosion des "
                  "sols en pente.",
            "en": "More rain than usual: watch for standing water in low-lying fields and erosion on slopes."},
        ("rainy", "normal"): {
            "fr": "Pluie proche de l'habitude pour ce mois de saison des pluies : pas de signal particulier.",
            "en": "Rainfall close to usual for this rainy-season month: no particular signal."},
        ("transition", "below_normal"): {
            "fr": "Mois de bascule entre saisons, avec moins de pluie que d'habitude : suivez l'arrivée ou l'arrêt "
                  "des pluies avant de planifier semis ou récoltes.",
            "en": "Transition month between seasons, with less rain than usual: follow the start or end of the "
                  "rains before planning sowing or harvests."},
        ("transition", "above_normal"): {
            "fr": "Mois de bascule entre saisons, avec plus de pluie que d'habitude : suivez l'arrivée ou l'arrêt "
                  "des pluies avant de planifier semis ou récoltes.",
            "en": "Transition month between seasons, with more rain than usual: follow the start or end of the "
                  "rains before planning sowing or harvests."},
        ("transition", "normal"): {
            "fr": "Mois de bascule entre saisons, pluie proche de l'habitude : suivez l'arrivée ou l'arrêt des pluies "
                  "avant de planifier semis ou récoltes.",
            "en": "Transition month between seasons, rainfall close to usual: follow the start or end of the rains "
                  "before planning sowing or harvests."},
        ("dry", None): {
            "fr": "Mois de saison sèche : il pleut habituellement peu à cette période, un écart en % porte donc sur "
                  "de petites quantités d'eau.",
            "en": "Dry-season month: little rain is usual at this time, so a % difference concerns small amounts "
                  "of water."},
    },
    "ndvi": {
        "below_normal": {"fr": "Végétation moins verte que d'habitude pour ce mois : vérifiez l'état des cultures "
                               "et des pâturages.",
                         "en": "Vegetation less green than usual for this month: check the condition of crops and "
                               "pastures."},
        "above_normal": {"fr": "Végétation plus verte que d'habitude pour ce mois.",
                         "en": "Vegetation greener than usual for this month."},
        "normal": {"fr": "Végétation proche de l'habitude pour ce mois : pas de signal particulier.",
                   "en": "Vegetation close to usual for this month: no particular signal."},
    },
    "lst_day": {
        "above_normal": {"fr": "Sol plus chaud que d'habitude en journée : cultures et bétail peuvent souffrir de la "
                               "chaleur. C'est la température de la surface du sol, pas celle de l'air.",
                         "en": "Ground hotter than usual during the day: crops and livestock may suffer from heat. "
                               "This is the temperature of the ground surface, not of the air."},
        "below_normal": {"fr": "Sol moins chaud que d'habitude en journée. C'est la température de la surface du sol, "
                               "pas celle de l'air.",
                         "en": "Ground cooler than usual during the day. This is the temperature of the ground "
                               "surface, not of the air."},
        "normal": {"fr": "Température du sol proche de l'habitude pour ce mois. C'est la température de la surface "
                         "du sol, pas celle de l'air.",
                   "en": "Land surface temperature close to usual for this month. This is the temperature of the "
                         "ground surface, not of the air."},
    },
}
LOW_COVERAGE_NOTE = {"fr": " À lire avec prudence : faible couverture (nuages).",
                     "en": " Read with caution: low coverage (clouds)."}


def interpretation(region_id: str, s: IndicatorSnapshot, lang: str) -> Optional[str]:
    """Conseil sur l'indicateur de `s` seulement ; aucun si la valeur ou la normale manque."""
    if s.value is None or s.trend == "unknown":
        return None
    table = INTERPRET.get(s.indicator, {})
    if s.indicator == "precipitation":
        seas = indicators.season(region_id, int(s.date[5:7]))
        entry = table.get(("dry", None)) if seas == "dry" else table.get((seas, s.trend))
    else:
        entry = table.get(s.trend)
    if not entry:
        return None
    text = entry[i18n.lang_of(lang)]
    return text + (LOW_COVERAGE_NOTE[i18n.lang_of(lang)] if s.low_coverage else "")


def _pointer_doc(indicator: str, docs: list[retrieve.Chunk], region_id: str) -> Optional[retrieve.Chunk]:
    """Fiche ou explication de l'indicateur (fiche_nasadem.md pour l'altitude)."""
    for f in retrieve.INDICATOR_DOCS.get(indicator, ()):
        hit = next((d for d in docs if d.file == f), None)
        if hit:
            return hit
    wanted = list(retrieve.INDICATOR_DOCS.get(indicator, ()))
    if wanted:
        found = retrieve.search(f"{indicator} {' '.join(wanted)}", k=len(wanted), files=wanted)
        found.sort(key=lambda c: wanted.index(c.file))
        if found:
            return found[0]
    return docs[0] if docs else None


def _style(req: ExplainRequest) -> str:
    profile = next((p for p in catalog.PROFILES if p.id == req.profile), None)
    return "scientific" if req.mode == "scientific" or (profile and profile.default_mode == "scientific") else "public"


async def explain(req: ExplainRequest) -> ExplainResponse:
    lang = i18n.lang_of(req.lang)
    region = regions.get_region(req.region_id)
    if req.indicator not in indicators.TS_INDICATORS and req.indicator != "elevation":
        raise NotImplementedYet("in_development",
                                f"Indicateur {req.indicator} en cours de développement : pas encore de données "
                                f"ni d'explication")
    data_tools.check_date_format(req.date)
    if req.date:  # aussi pour l'altitude (statique, la date est ignorée mais doit être valable)
        data_tools.check_in_data(req.date)
    col = data_tools.Collector(req.region_id, req.lang, req.mode, _style(req))
    if req.indicator == "elevation":
        primary = col.elevation()
    elif req.date:
        primary = col.month(req.indicator, data_tools.check_in_data(req.date))
    else:
        primary = col.latest(req.indicator)
    snap = col.snapshots[0] if col.snapshots and primary and primary["kind"] in ("value", "latest") else None
    when = f" ({i18n.month_label(snap.date, lang)})" if snap else (
        f" ({i18n.month_label(req.date, lang)})" if req.date and req.indicator != "elevation" else "")
    title = f"{i18n.name(req.indicator, lang)} — {region.name}{when}"

    docs = retrieve.dedupe(retrieve.search(f"{catalog.LABELS.get(req.indicator, req.indicator)} {region.name} "
                                           f"{req.indicator}", k=N_DOCS, indicator=req.indicator,
                                           region_id=req.region_id))
    pointer = _pointer_doc(req.indicator, docs, req.region_id)
    if pointer and pointer.file not in {d.file for d in docs}:
        docs.append(pointer)
    sources: list[Source] = list(col.sources.values())
    sources += [Source(id=d.source_id, kind="document", title=d.title, url=d.source_url, snippet=d.snippet())
                for d in docs]
    allowed = {s.id for s in sources}
    computed = {s.id for s in sources if s.kind == "computed"}
    has_value = bool(primary and primary["has_value"] and primary["kind"] in ("value", "latest", "elevation"))

    # Gabarit : faits datés ; interprétation + document seulement si la valeur demandée existe
    template = [Statement(text=f["text"], nature="observed", source_ids=f["source_ids"]) for f in col.facts]
    if has_value:
        if snap is not None and (advice := interpretation(req.region_id, snap, lang)):
            template.append(Statement(text=advice, nature="interpreted", source_ids=primary["source_ids"]))
        if pointer:
            template.append(Statement(text=i18n.t("doc_pointer", lang, title=pointer.title), nature="interpreted",
                                      source_ids=[pointer.source_id]))

    statements: list[Statement] = []
    if llm.available() and has_value:
        facts = col.facts
        doc_ctx = [{"source_id": d.source_id, "title": d.title, "content": d.snippet(900)} for d in docs]
        prompt = (f"{templates.context_block(facts, doc_ctx)}\n\nRÉGION : {region.name}\nINDICATEUR : "
                  f"{i18n.name(req.indicator, lang)}\nDATE : {primary['date']}\n\n{templates.EXPLAIN_TASK}")
        facts_text = " ".join([f["text"] for f in facts] + [s for f in facts for s in f["source_ids"]])
        try:
            out = await llm.structured(templates.system_prompt(req.profile, req.mode, req.lang), prompt, _LLMExplain)
            statements = _check(out.statements, allowed, computed, facts_text,
                                {d["source_id"]: d["content"] for d in doc_ctx})
            if statements and not any(s.nature == "observed" for s in statements):
                statements = template[:1] + statements
            if (out.title and guard.numbers_ok(out.title, guard.known_numbers([facts_text]))
                    and not guard.is_predictive(out.title)):
                title = out.title
        except Exception:  # noqa: BLE001 — LLMUnavailable, réseau : gabarit
            statements = []
    if not statements:
        statements = template
    used = {i for s in statements for i in s.source_ids}
    return ExplainResponse(title=title, statements=statements,
                           sources=[s for s in sources if s.id in used or s.kind == "dataset"],
                           disclaimer=DISCLAIMER)

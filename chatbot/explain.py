"""POST /explain (M24) : explication d'un indicateur pour une région et un mois.

1. Faits : résumé M14 (source `computed:<region>:<indicator>:<date>`) ;
2. Documents : 3 à 5 morceaux du corpus filtrés par indicateur ;
3. LLM en sortie structurée (Statement[]), ton selon le profil et le mode.
Garde-fous : une phrase dont une source n'existe pas est retirée ; une phrase « observed » doit citer
une source calculée et ne contenir que des chiffres présents dans les faits ; jamais de « predicted ».
Sans LLM (ou si rien ne passe les garde-fous) : phrases par gabarit à partir des mêmes faits.
"""
import re
from typing import Literal

from pydantic import BaseModel, Field

from backend.core.constants import DISCLAIMER
from backend.schemas import ExplainRequest, ExplainResponse, Source, Statement
from backend.services import catalog, indicators, regions
from chatbot.llm import client as llm
from chatbot.prompts import templates
from chatbot.tools import data as data_tools
from chatbot.tools import retrieve

N_DOCS = 4
_NUM = re.compile(r"\d+(?:[.,]\d+)?")


class _LLMStatement(BaseModel):
    text: str
    nature: Literal["observed", "interpreted"]
    source_ids: list[str] = Field(min_length=1)


class _LLMExplain(BaseModel):
    title: str
    statements: list[_LLMStatement]


def _numbers(text: str) -> set[str]:
    return {n.replace(",", ".").rstrip("0").rstrip(".") for n in _NUM.findall(text)}


def _check(statements: list[_LLMStatement], allowed: set[str], computed: set[str], facts_text: str) -> list[Statement]:
    known = _numbers(facts_text)
    out = []
    for s in statements:
        if not set(s.source_ids) <= allowed:
            continue
        if s.nature == "observed" and (not set(s.source_ids) & computed or not _numbers(s.text) <= known):
            continue
        out.append(Statement(text=s.text, nature=s.nature, source_ids=s.source_ids))
    return out


def _template(req: ExplainRequest, snap, fact_id: str, docs, region_name: str) -> list[Statement]:
    out = [Statement(text=f"{region_name} — {snap.plain_summary}", nature="observed", source_ids=[fact_id])]
    if req.indicator in ("precipitation", "ndvi"):
        agri = indicators.agriculture(req.region_id, snap.date)
        advice = next((s for s in agri.statements if s.nature == "interpreted"), None)
        if advice:
            out.append(Statement(text=advice.text, nature="interpreted", source_ids=[fact_id]))
    if docs:
        out.append(Statement(text=f"Pour comprendre cet indicateur, voir « {docs[0].title} ».",
                             nature="interpreted", source_ids=[docs[0].source_id]))
    return out


async def explain(req: ExplainRequest) -> ExplainResponse:
    region = regions.get_region(req.region_id)
    label = catalog.LABELS.get(req.indicator, req.indicator)
    title = f"{label} — {region.name}"
    sources: list[Source] = []
    facts: list[dict] = []
    snap = None
    if req.indicator in indicators.TS_INDICATORS:
        date = indicators._check_month(req.date, "date") if req.date else None
        sci = indicators.summary(req.region_id, date, "scientific")
        snap_sci = next(s for s in sci.indicators if s.indicator == req.indicator)
        facts, sources = data_tools.facts_and_sources(req.region_id, [snap_sci])
        # Gabarit : formulation scientifique (valeurs, unités, normale) en mode scientifique ou pour un
        # profil dont le ton par défaut est scientifique (chercheurs)
        profile = next((p for p in catalog.PROFILES if p.id == req.profile), None)
        style = "scientific" if req.mode == "scientific" or (profile and profile.default_mode == "scientific") else "public"
        snap = snap_sci if style == "scientific" else next(
            s for s in indicators.summary(req.region_id, date, "public").indicators if s.indicator == req.indicator)
    elif req.indicator == "elevation":
        extra = data_tools.elevation_fact(req.region_id)
        if extra:
            facts, sources = [extra[0]], [extra[1]]
    docs = retrieve.search(f"{label} {region.name} {req.indicator}", k=N_DOCS,
                           indicator=req.indicator, region_id=req.region_id)
    sources += [Source(id=d.source_id, kind="document", title=d.title, url=d.source_url, snippet=d.snippet())
                for d in docs]
    allowed = {s.id for s in sources}
    computed = {s.id for s in sources if s.kind == "computed"}

    statements: list[Statement] = []
    if llm.available() and facts:
        doc_ctx = [{"source_id": d.source_id, "title": d.title, "content": d.snippet(900)} for d in docs]
        prompt = (f"{templates.context_block(facts, doc_ctx)}\n\nRÉGION : {region.name}\nINDICATEUR : {label}\n"
                  f"MOIS : {facts[0]['source_id'].rsplit(':', 1)[-1]}\n\n{templates.EXPLAIN_TASK}")
        try:
            out = await llm.structured(templates.system_prompt(req.profile, req.mode, req.lang), prompt, _LLMExplain)
            statements = _check(out.statements, allowed, computed, " ".join(f["text"] for f in facts))
            title = out.title or title
        except llm.LLMUnavailable:
            statements = []
    if not statements:
        if snap is not None:
            statements = _template(req, snap, facts[0]["source_id"], docs, region.name)
        elif facts:
            statements = [Statement(text=facts[0]["text"], nature="observed", source_ids=[facts[0]["source_id"]])]
    used = {i for s in statements for i in s.source_ids}
    return ExplainResponse(title=title, statements=statements,
                           sources=[s for s in sources if s.id in used or s.kind == "dataset"],
                           disclaimer=DISCLAIMER)

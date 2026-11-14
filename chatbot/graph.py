"""Graphe de l'assistant : route → fetch_data → retrieve → generate.

TODO M24–M26 : graphe LangGraph (nœuds dans chatbot/nodes/, prompts dans chatbot/prompts/,
client LLM dans chatbot/llm/, checkpointer SQLite par thread_id dans chatbot/memory/).
D'ici là : réponses mock, même contrat.
"""
import asyncio
import uuid
from collections.abc import AsyncIterator

from pydantic import BaseModel

from backend.core.constants import DISCLAIMER
from backend.schemas import (ChatRequest, ChatResponse, EvDone, EvMeta, EvSources, EvStatus,
                             EvToken, ExplainRequest, ExplainResponse, Source, Statement)
from backend.services.catalog import LABELS, dataset_for
from backend.services.regions import get_region


def explain(req: ExplainRequest) -> ExplainResponse:
    region = get_region(req.region_id)
    ds = dataset_for(req.indicator)
    return ExplainResponse(
        title=f"{LABELS[req.indicator]} — {region.name}",
        statements=[
            Statement(text="Les satellites montrent moins de pluie que la normale ce mois-ci.",
                      nature="observed", source_ids=["computed:1"]),
            Statement(text="Cela peut expliquer une végétation moins verte que d'habitude.",
                      nature="interpreted", source_ids=["doc:1"]),
        ],
        sources=[Source(id="computed:1", kind="computed", title=f"Série {ds.name}", dataset_id=ds.id),
                 Source(id="doc:1", kind="document", title="Doc mock", snippet="…")],
        disclaimer=DISCLAIMER)


async def chat_events(req: ChatRequest) -> AsyncIterator[BaseModel]:
    """Événements SSE dans l'ordre : meta → status → token → (data) → sources → done."""
    tid = req.thread_id or str(uuid.uuid4())
    yield EvMeta(thread_id=tid)
    for step in ("routing", "fetching_data", "retrieving", "generating"):
        yield EvStatus(step=step)
        await asyncio.sleep(0.2)
    for w in "Dans votre région, les satellites observent une baisse de la verdure depuis août.".split():
        yield EvToken(content=w + " ")
        await asyncio.sleep(0.04)
    yield EvSources(sources=[Source(id="ds:modis_ndvi", kind="dataset", title="MODIS MOD13Q1", dataset_id="modis_ndvi")])
    yield EvDone(statements=[Statement(text="Baisse de NDVI depuis août", nature="observed", source_ids=["ds:modis_ndvi"])])


def chat(req: ChatRequest) -> ChatResponse:
    return ChatResponse(thread_id=req.thread_id or str(uuid.uuid4()),
                        answer="Réponse mock.", statements=[], sources=[])

"""Graphe de l'assistant (LangGraph) : route → fetch_data → retrieve → generate (M25/M26).

- Nœuds : chatbot/nodes ; prompts : chatbot/prompts ; LLM : chatbot/llm ; mémoire : chatbot/memory.
- Un fil = un thread_id (checkpointer Postgres) : région, indicateur, intention, date et historique
  sont gardés d'un tour à l'autre.
- `check_request` valide région et position AVANT toute réponse (404 region_not_found / outside_togo).
- Hors sujet → réponse polie qui ramène au climat du Togo, sans RAG.
- Sans clé LLM : réponse par gabarit à partir des seuls faits calculés.
- L'avertissement : en fin de texte (`answer`, tokens) et dans le champ `disclaimer` (ChatResponse, EvDone).
"""
import logging
import uuid
from collections.abc import AsyncIterator

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel

from backend.core.constants import DISCLAIMER
from backend.schemas import (ChatRequest, ChatResponse, EvData, EvDone, EvError, EvMeta, EvSources,
                             EvStatus, EvToken, IndicatorSnapshot, Source, Statement, TimeSeries)
from backend.services import regions as region_service
from chatbot import memory, nodes

log = logging.getLogger(__name__)
_compiled: dict[int, object] = {}


def build(checkpointer):
    g = StateGraph(nodes.ChatState)
    g.add_node("route", nodes.route)
    g.add_node("fetch_data", nodes.fetch_data)
    g.add_node("retrieve", nodes.retrieve_docs)
    g.add_node("generate", nodes.generate)
    g.add_edge(START, "route")
    g.add_conditional_edges("route", nodes.after_route, {"fetch_data": "fetch_data", "generate": "generate"})
    g.add_edge("fetch_data", "retrieve")
    g.add_edge("retrieve", "generate")
    g.add_edge("generate", END)
    return g.compile(checkpointer=checkpointer)


def graph():
    saver = memory.get_saver()
    if id(saver) not in _compiled:
        _compiled[id(saver)] = build(saver)
    return _compiled[id(saver)]


def check_request(req: ChatRequest) -> None:
    """Région inconnue → 404 region_not_found ; position hors du Togo → 404 outside_togo."""
    if req.region_id is not None:
        region_service.get_region(req.region_id)
    if req.location is not None:
        region_service.locate(*req.location)


def _inputs(req: ChatRequest) -> dict:
    return {"message": req.message, "profile": req.profile, "mode": req.mode, "lang": req.lang,
            "region_hint": req.region_id, "location": req.location}


def _config(thread_id: str) -> dict:
    return {"configurable": {"thread_id": thread_id}}


def thread_id_for(req: ChatRequest) -> str:
    return req.thread_id or str(uuid.uuid4())


def _data(state: dict) -> dict | None:
    out = {}
    if state.get("snapshots"):
        out["snapshots"] = state["snapshots"]
    if state.get("series"):
        out["series"] = state["series"]
    return out or None


async def chat(req: ChatRequest, thread_id: str) -> ChatResponse:
    state = await graph().ainvoke(_inputs(req), _config(thread_id))
    return ChatResponse(thread_id=thread_id, answer=state["answer"],
                        statements=[Statement(**s) for s in state.get("statements", [])],
                        sources=[Source(**s) for s in state.get("sources", [])],
                        data=_data(state), disclaimer=DISCLAIMER)


async def chat_events(req: ChatRequest, thread_id: str) -> AsyncIterator[BaseModel]:
    """Événements SSE dans l'ordre : meta → status → token → (data) → sources → done ; error en cas d'échec."""
    yield EvMeta(thread_id=thread_id)
    final: dict = {}
    try:
        async for mode, chunk in graph().astream(_inputs(req), _config(thread_id), stream_mode=["custom", "values"]):
            if mode == "custom":
                if "status" in chunk:
                    yield EvStatus(step=chunk["status"])
                elif "token" in chunk:
                    yield EvToken(content=chunk["token"])
            else:
                final = chunk
    except Exception as e:  # le flux est déjà ouvert : on signale l'erreur puis on termine
        log.exception("chat/stream")
        yield EvError(message=f"Erreur de l'assistant : {type(e).__name__}. {DISCLAIMER}")
        return
    snaps = [IndicatorSnapshot(**s) for s in final.get("snapshots") or []]
    if snaps:
        yield EvData(snapshots=snaps, snapshot=snaps[0] if len(snaps) == 1 else None)
    for s in final.get("series") or []:
        yield EvData(series=TimeSeries(**s))
    yield EvSources(sources=[Source(**s) for s in final.get("sources", [])])
    yield EvDone(statements=[Statement(**s) for s in final.get("statements", [])], disclaimer=DISCLAIMER)

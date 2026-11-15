from typing import Optional

from fastapi import APIRouter, Header
from fastapi.responses import StreamingResponse

from backend.schemas import (ApiResponse, ChatRequest, ChatResponse, ExplainRequest,
                             ExplainResponse, ok)
from backend.services import sessions
from chatbot import explain as explainer
from chatbot import graph
from chatbot.channels import sse

router = APIRouter(tags=["ai"])


@router.post("/explain", response_model=ApiResponse[ExplainResponse])
async def explain(req: ExplainRequest):
    return ok(await explainer.explain(req))


# Flux SSE : pas d'enveloppe (une ligne `data: <événement>` par message)
@router.post("/chat/stream")
async def chat_stream(req: ChatRequest, x_session_id: Optional[str] = Header(None)):
    graph.check_request(req)  # avant d'ouvrir le flux : 404 region_not_found / outside_togo
    thread_id = graph.thread_id_for(req)
    sessions.record_thread(x_session_id, thread_id, req.message)
    return StreamingResponse(sse.stream(graph.chat_events(req, thread_id)), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.post("/chat", response_model=ApiResponse[ChatResponse])
async def chat(req: ChatRequest, x_session_id: Optional[str] = Header(None)):
    graph.check_request(req)
    thread_id = graph.thread_id_for(req)
    sessions.record_thread(x_session_id, thread_id, req.message)
    return ok(await graph.chat(req, thread_id))

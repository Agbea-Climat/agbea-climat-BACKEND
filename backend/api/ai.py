from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from backend.schemas import (ApiResponse, ChatRequest, ChatResponse, ExplainRequest,
                             ExplainResponse, ok)
from chatbot import graph
from chatbot.channels import sse

router = APIRouter(tags=["ai"])


@router.post("/explain", response_model=ApiResponse[ExplainResponse])
def explain(req: ExplainRequest):
    return ok(graph.explain(req))


# Flux SSE : pas d'enveloppe (une ligne `data: <événement>` par message)
@router.post("/chat/stream")
async def chat_stream(req: ChatRequest):
    return StreamingResponse(sse.stream(graph.chat_events(req)), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache"})


@router.post("/chat", response_model=ApiResponse[ChatResponse])
def chat(req: ChatRequest):
    return ok(graph.chat(req))

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from backend.schemas import ChatRequest, ChatResponse, ExplainRequest, ExplainResponse
from chatbot import graph
from chatbot.channels import sse

router = APIRouter(tags=["ai"])


@router.post("/explain", response_model=ExplainResponse)
def explain(req: ExplainRequest):
    return graph.explain(req)


@router.post("/chat/stream")
async def chat_stream(req: ChatRequest):
    return StreamingResponse(sse.stream(graph.chat_events(req)), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache"})


@router.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    return graph.chat(req)

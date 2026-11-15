"""IA / RAG : explication, chat et événements SSE."""
from __future__ import annotations

from typing import Annotated, Literal, Optional, Union

from pydantic import BaseModel, Field

from .common import IndicatorId, Lang, Mode, ProfileId, Source, Statement
from .observations import IndicatorSnapshot, TimeSeries


class ExplainRequest(BaseModel):
    profile: Optional[ProfileId] = None
    region_id: str
    indicator: IndicatorId
    date: Optional[str] = None
    mode: Mode = "public"
    lang: Lang = "fr"


class ExplainResponse(BaseModel):
    title: str
    statements: list[Statement]
    sources: list[Source]
    disclaimer: str


class ChatRequest(BaseModel):
    thread_id: Optional[str] = None
    profile: Optional[ProfileId] = None
    message: str = Field(min_length=1, max_length=2000)
    mode: Mode = "public"
    lang: Lang = "fr"
    region_id: Optional[str] = None
    location: Optional[tuple[float, float]] = None


class ChatResponse(BaseModel):
    thread_id: str
    answer: str
    statements: list[Statement] = []
    sources: list[Source] = []
    data: Optional[dict] = None


# Événements SSE (data: <json>)
class EvMeta(BaseModel):
    type: Literal["meta"] = "meta"
    thread_id: str


class EvStatus(BaseModel):
    type: Literal["status"] = "status"
    step: Literal["routing", "fetching_data", "retrieving", "generating"]


class EvToken(BaseModel):
    type: Literal["token"] = "token"
    content: str


class EvData(BaseModel):
    type: Literal["data"] = "data"
    series: Optional[TimeSeries] = None
    snapshot: Optional[IndicatorSnapshot] = None


class EvSources(BaseModel):
    type: Literal["sources"] = "sources"
    sources: list[Source]


class EvDone(BaseModel):
    type: Literal["done"] = "done"
    statements: Optional[list[Statement]] = None


class EvError(BaseModel):
    type: Literal["error"] = "error"
    message: str


ChatEvent = Annotated[
    Union[EvMeta, EvStatus, EvToken, EvData, EvSources, EvDone, EvError],
    Field(discriminator="type"),
]

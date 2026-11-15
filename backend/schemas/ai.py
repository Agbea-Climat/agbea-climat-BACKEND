"""IA / RAG : explication, chat et événements SSE."""
from __future__ import annotations

from typing import Annotated, Literal, Optional, Union

from pydantic import BaseModel, Field

from backend.core.constants import DISCLAIMER

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
    # [lon, lat] bornés comme /locate : hors bornes, nan ou inf → 422 validation_error
    location: Optional[tuple[Annotated[float, Field(ge=-180, le=180, allow_inf_nan=False)],
                             Annotated[float, Field(ge=-90, le=90, allow_inf_nan=False)]]] = None


class ChatResponse(BaseModel):
    thread_id: str
    answer: str                        # se termine toujours par l'avertissement (traduit si lang=en)
    statements: list[Statement] = []
    sources: list[Source] = []
    data: Optional[dict] = None        # {"snapshots"?: IndicatorSnapshot[], "series"?: TimeSeries[]}
    disclaimer: str = DISCLAIMER       # toujours le texte exact (règle 7)


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
    """Un événement par série (`series`) ; les valeurs du mois dans un seul événement (`snapshots`,
    et `snapshot` quand il n'y en a qu'une, pour compatibilité)."""
    type: Literal["data"] = "data"
    series: Optional[TimeSeries] = None
    snapshot: Optional[IndicatorSnapshot] = None
    snapshots: Optional[list[IndicatorSnapshot]] = None


class EvSources(BaseModel):
    type: Literal["sources"] = "sources"
    sources: list[Source]


class EvDone(BaseModel):
    type: Literal["done"] = "done"
    statements: Optional[list[Statement]] = None
    disclaimer: str = DISCLAIMER       # toujours le texte exact (règle 7)


class EvError(BaseModel):
    type: Literal["error"] = "error"
    message: str


ChatEvent = Annotated[
    Union[EvMeta, EvStatus, EvToken, EvData, EvSources, EvDone, EvError],
    Field(discriminator="type"),
]

"""Formatage Server-Sent Events : une ligne `data: <json>` par événement."""
from collections.abc import AsyncIterator

from pydantic import BaseModel


def to_sse(ev: BaseModel) -> str:
    return f"data: {ev.model_dump_json()}\n\n"


async def stream(events: AsyncIterator[BaseModel]) -> AsyncIterator[str]:
    async for ev in events:
        yield to_sse(ev)

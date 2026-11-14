"""Sessions anonymes."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel

from .common import Lang, Mode, ProfileId


class Preferences(BaseModel):
    profile: Optional[ProfileId] = None
    region_id: Optional[str] = None
    lang: Optional[Lang] = None
    mode: Optional[Mode] = None


class ThreadSummary(BaseModel):
    thread_id: str
    title: str
    updated_at: str


class Session(BaseModel):
    session_id: str
    preferences: Preferences
    threads: list[ThreadSummary]
    created_at: str
    last_seen_at: str

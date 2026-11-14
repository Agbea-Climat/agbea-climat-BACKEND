"""Sessions anonymes : création, lecture, préférences."""
import uuid
from datetime import datetime, timezone

from backend.core.exceptions import NotFound
from backend.repositories import sessions as repo
from backend.schemas import Preferences, Session

from .regions import get_region


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_session() -> Session:
    now = _now()
    s = Session(session_id=str(uuid.uuid4()), preferences=Preferences(), threads=[], created_at=now, last_seen_at=now)
    return repo.save(s)


def _session(session_id: str) -> Session:
    s = repo.get(session_id)
    if s is None:
        raise NotFound("session_not_found", session_id)
    return s


def get_session(session_id: str) -> Session:
    s = _session(session_id)
    s.last_seen_at = _now()
    s.threads.sort(key=lambda t: t.updated_at, reverse=True)
    return repo.save(s)


def update_preferences(session_id: str, prefs: Preferences) -> Preferences:
    s = _session(session_id)
    if prefs.region_id is not None:
        get_region(prefs.region_id)
    s.preferences = s.preferences.model_copy(update=prefs.model_dump(exclude_unset=True))
    repo.save(s)
    return s.preferences

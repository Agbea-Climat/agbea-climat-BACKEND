"""Sessions anonymes : création, lecture, préférences, fils de discussion (M03–M05)."""
import uuid
from datetime import datetime, timezone
from typing import Optional

from backend.core.exceptions import NotFound
from backend.repositories import sessions as repo
from backend.schemas import Preferences, Session

from .regions import get_region

THREAD_TITLE_LEN = 60


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _valid_id(session_id: str) -> str:
    """Un identifiant qui n'est pas un UUID ne peut désigner aucune session."""
    try:
        return str(uuid.UUID(session_id))
    except (ValueError, TypeError, AttributeError):
        raise NotFound("session_not_found", f"Session introuvable : {session_id}") from None


def create_session() -> Session:
    return repo.create(str(uuid.uuid4()), _now())


def get_session(session_id: str) -> Session:
    s = repo.get(_valid_id(session_id), touch=_now())
    if s is None:
        raise NotFound("session_not_found", f"Session introuvable : {session_id}")
    return s


def update_preferences(session_id: str, prefs: Preferences) -> Preferences:
    sid = _valid_id(session_id)
    current = repo.get(sid)
    if current is None:
        raise NotFound("session_not_found", f"Session introuvable : {session_id}")
    if prefs.region_id is not None:
        get_region(prefs.region_id)
    merged = current.preferences.model_copy(update=prefs.model_dump(exclude_unset=True))
    repo.save_preferences(sid, merged.model_dump())
    return merged


def record_thread(session_id: Optional[str], thread_id: str, first_message: str) -> None:
    """Rattache un fil de chat à la session (header X-Session-Id). Session inconnue : ignoré."""
    if not session_id:
        return
    try:
        sid = str(uuid.UUID(session_id))
    except (ValueError, TypeError, AttributeError):
        return
    if repo.exists(sid):
        repo.upsert_thread(sid, thread_id, first_message.strip()[:THREAD_TITLE_LEN], _now())

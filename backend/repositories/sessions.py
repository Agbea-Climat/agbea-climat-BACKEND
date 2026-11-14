"""Stockage des sessions.

TODO M03/M04 : tables PostgreSQL `sessions` et `threads` (backend.core.database.models).
D'ici là : stockage en mémoire (perdu au redémarrage).
"""
from typing import Optional

from backend.schemas import Session

_SESSIONS: dict[str, Session] = {}


def save(session: Session) -> Session:
    _SESSIONS[session.session_id] = session
    return session


def get(session_id: str) -> Optional[Session]:
    return _SESSIONS.get(session_id)

"""Stockage des sessions anonymes et de leurs fils de discussion (PostgreSQL, M03–M05).

Tables `sessions` et `threads` : backend/core/database/models.py. Aucune logique métier ici.
"""
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select

from backend.core.database import SessionLocal
from backend.core.database.models import SessionRow, ThreadRow
from backend.schemas import Preferences, Session, ThreadSummary


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def _to_schema(row: SessionRow) -> Session:
    threads = sorted(row.threads, key=lambda t: t.updated_at, reverse=True)
    return Session(session_id=row.id, preferences=Preferences(**(row.preferences or {})),
                   threads=[ThreadSummary(thread_id=t.thread_id, title=t.title, updated_at=_iso(t.updated_at))
                            for t in threads],
                   created_at=_iso(row.created_at), last_seen_at=_iso(row.last_seen_at))


def create(session_id: str, now: datetime) -> Session:
    with SessionLocal() as db:
        row = SessionRow(id=session_id, preferences={}, created_at=now, last_seen_at=now)
        db.add(row)
        db.commit()
        db.refresh(row)
        return _to_schema(row)


def get(session_id: str, touch: Optional[datetime] = None) -> Optional[Session]:
    """Session ou None. `touch` : met à jour last_seen_at."""
    with SessionLocal() as db:
        row = db.get(SessionRow, session_id)
        if row is None:
            return None
        if touch is not None:
            row.last_seen_at = touch
            db.commit()
            db.refresh(row)
        return _to_schema(row)


def exists(session_id: str) -> bool:
    with SessionLocal() as db:
        return db.scalar(select(SessionRow.id).where(SessionRow.id == session_id)) is not None


def save_preferences(session_id: str, preferences: dict) -> Optional[dict]:
    with SessionLocal() as db:
        row = db.get(SessionRow, session_id)
        if row is None:
            return None
        row.preferences = preferences
        db.commit()
        return dict(row.preferences)


def upsert_thread(session_id: str, thread_id: str, title: str, now: datetime) -> None:
    """Crée le fil (titre = début du premier message) ou met à jour son updated_at."""
    with SessionLocal() as db:
        row = db.get(ThreadRow, thread_id)
        if row is None:
            db.add(ThreadRow(thread_id=thread_id, session_id=session_id, title=title, updated_at=now))
        else:
            row.updated_at = now
        sess = db.get(SessionRow, session_id)
        if sess is not None:
            sess.last_seen_at = now
        db.commit()

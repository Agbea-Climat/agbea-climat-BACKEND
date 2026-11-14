from fastapi import APIRouter

from backend.schemas import Preferences, Session
from backend.services import sessions

router = APIRouter(tags=["sessions"])


@router.post("/sessions", response_model=Session, status_code=201)
def create_session():
    return sessions.create_session()


@router.get("/sessions/{session_id}", response_model=Session)
def get_session(session_id: str):
    return sessions.get_session(session_id)


@router.patch("/sessions/{session_id}/preferences", response_model=Preferences)
def update_preferences(session_id: str, prefs: Preferences):
    return sessions.update_preferences(session_id, prefs)

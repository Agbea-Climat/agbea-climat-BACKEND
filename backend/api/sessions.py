from fastapi import APIRouter

from backend.schemas import ApiResponse, Preferences, Session, ok
from backend.services import sessions

router = APIRouter(tags=["sessions"])


@router.post("/sessions", response_model=ApiResponse[Session], status_code=201)
def create_session():
    return ok(sessions.create_session(), "Session créée")


@router.get("/sessions/{session_id}", response_model=ApiResponse[Session])
def get_session(session_id: str):
    return ok(sessions.get_session(session_id))


@router.patch("/sessions/{session_id}/preferences", response_model=ApiResponse[Preferences])
def update_preferences(session_id: str, prefs: Preferences):
    return ok(sessions.update_preferences(session_id, prefs), "Préférences mises à jour")

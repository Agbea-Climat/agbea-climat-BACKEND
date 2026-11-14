from fastapi import APIRouter

from backend.core.exceptions import NotImplementedYet

router = APIRouter(tags=["voice"])


@router.post("/voice/transcribe", status_code=501)
def voice_transcribe():
    raise NotImplementedYet("in_development", "AGBÉA Voice en développement")

from fastapi import APIRouter

from backend.schemas import Profile
from backend.services import catalog

router = APIRouter(tags=["profiles"])


@router.get("/profiles", response_model=list[Profile])
def list_profiles():
    return catalog.list_profiles()

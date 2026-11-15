from fastapi import APIRouter

from backend.schemas import ApiResponse, Profile, ok
from backend.services import catalog

router = APIRouter(tags=["profiles"])


@router.get("/profiles", response_model=ApiResponse[list[Profile]])
def list_profiles():
    return ok(catalog.list_profiles())

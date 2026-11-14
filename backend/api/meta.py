from fastapi import APIRouter

from backend.schemas import ApiResponse, AppMeta, ok
from backend.services import catalog

router = APIRouter(tags=["meta"])


@router.get("/health", response_model=ApiResponse[dict[str, str]])
def health():
    return ok({"status": "ok"})


@router.get("/meta", response_model=ApiResponse[AppMeta])
def meta():
    return ok(catalog.get_meta())

from fastapi import APIRouter

from backend.schemas import AppMeta
from backend.services import catalog

router = APIRouter(tags=["meta"])


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/meta", response_model=AppMeta)
def meta():
    return catalog.get_meta()

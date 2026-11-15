from fastapi import APIRouter

from backend.schemas import ApiResponse, AppMeta, ok
from backend.services import catalog

router = APIRouter(tags=["meta"])


@router.get("/health", response_model=ApiResponse[dict[str, str]])
def health():
    return ok({"status": "ok"})


# HEAD /health : sondes de disponibilité (Dokploy, moniteurs). Même réponse, sans corps.
@router.head("/health", include_in_schema=False)
def health_head():
    return ok({"status": "ok"})


@router.get("/meta", response_model=ApiResponse[AppMeta])
def meta():
    return ok(catalog.get_meta())

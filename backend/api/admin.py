from fastapi import APIRouter

from backend.schemas import ApiResponse, ok
from worker import rag_ingest

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/rag/ingest", response_model=ApiResponse[dict])
def rag_ingest_route():
    return ok(rag_ingest.ingest(), "Ingestion terminée")


@router.get("/rag/documents", response_model=ApiResponse[dict])
def rag_documents():
    return ok(rag_ingest.list_documents())

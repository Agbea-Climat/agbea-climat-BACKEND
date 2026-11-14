from fastapi import APIRouter

from worker import rag_ingest

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/rag/ingest")
def rag_ingest_route():
    return rag_ingest.ingest()


@router.get("/rag/documents")
def rag_documents():
    return rag_ingest.list_documents()

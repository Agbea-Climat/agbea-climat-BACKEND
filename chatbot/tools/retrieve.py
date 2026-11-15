"""Recherche dans le corpus RAG (table rag_chunks, pgvector, distance cosinus)."""
from dataclasses import dataclass
from typing import Optional

from sqlalchemy import literal, or_, select

from backend.core.database import SessionLocal
from backend.core.database.models import RagChunk
from chatbot.llm import embeddings


@dataclass
class Chunk:
    id: str
    file: str
    title: str
    source_url: str
    content: str
    distance: float

    @property
    def source_id(self) -> str:
        return f"doc:{self.id[:12]}"

    def snippet(self, n: int = 300) -> str:
        return self.content if len(self.content) <= n else self.content[:n].rsplit(" ", 1)[0] + "…"


def search(query: str, k: int = 4, indicator: Optional[str] = None,
           region_id: Optional[str] = None) -> list[Chunk]:
    """k morceaux les plus proches. Filtres : documents de l'indicateur / la région, ou généraux."""
    vec = embeddings.embed_one(query)
    dist = RagChunk.embedding.cosine_distance(vec).label("distance")
    q = select(RagChunk.id, RagChunk.file, RagChunk.title, RagChunk.source_url, RagChunk.content, dist)
    if indicator:
        q = q.where(or_(RagChunk.indicators.overlap([indicator]), RagChunk.indicators == literal([], RagChunk.indicators.type)))
    if region_id:
        q = q.where(or_(RagChunk.region_ids.overlap([region_id]), RagChunk.region_ids == literal([], RagChunk.region_ids.type)))
    try:
        with SessionLocal() as db:
            rows = db.execute(q.order_by(dist).limit(k)).all()
    except Exception:  # base indisponible : l'assistant répond sans documents
        return []
    return [Chunk(*r) for r in rows]

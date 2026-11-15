"""Tables PostgreSQL. Toute modification passe par une migration Alembic :

    alembic revision --autogenerate -m "..."  puis  alembic upgrade head
"""
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.core.config import settings

from .base import Base


# ── Sessions anonymes (M03–M05) ──
class SessionRow(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    preferences: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    threads: Mapped[list["ThreadRow"]] = relationship(back_populates="session", cascade="all, delete-orphan",
                                                      order_by="ThreadRow.updated_at.desc()")


class ThreadRow(Base):
    """Fil de discussion du chat, rattaché à une session (créé par M25/M26)."""
    __tablename__ = "threads"

    thread_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    session: Mapped[SessionRow] = relationship(back_populates="threads")


# ── Corpus RAG (M22–M25) ──
class RagChunk(Base):
    """Morceau de document vectorisé. id = sha1(file + index) → upsert idempotent."""
    __tablename__ = "rag_chunks"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    file: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    region_ids: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, server_default="{}")
    indicators: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, server_default="{}")
    embedding: Mapped[list[float]] = mapped_column(Vector(settings.embedding_dim), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        # Recherche du plus proche voisin (distance cosinus)
        Index("ix_rag_chunks_embedding_hnsw", "embedding", postgresql_using="hnsw",
              postgresql_ops={"embedding": "vector_cosine_ops"}),
        # Filtres par région / indicateur (opérateur &&)
        Index("ix_rag_chunks_region_ids", "region_ids", postgresql_using="gin"),
        Index("ix_rag_chunks_indicators", "indicators", postgresql_using="gin"),
    )

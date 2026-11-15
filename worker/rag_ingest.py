"""Ingestion du corpus RAG (M22) et liste des documents (M23).

Lit data/corpus/ + sources.json, découpe chaque document en morceaux d'environ 600 tokens
(chevauchement ~80), vectorise (chatbot.llm.embeddings) et upsert dans la table `rag_chunks`
(pgvector). Id d'un morceau = sha1(file + index) : relancer ne crée pas de doublons ; les morceaux
devenus inutiles (document raccourci ou retiré de sources.json) sont supprimés.
"""
import hashlib
import json
import logging
from pathlib import Path

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert

from backend.core.config import settings
from backend.core.database import SessionLocal
from backend.core.database.models import RagChunk
from backend.repositories.store import DataUnavailable
from chatbot.llm import embeddings

log = logging.getLogger(__name__)

# ~600 tokens ≈ 450 mots en français ; chevauchement ~80 tokens ≈ 60 mots
CHUNK_WORDS = 450
OVERLAP_WORDS = 60
TEXT_SUFFIXES = {".md", ".txt"}


def corpus_dir() -> Path:
    return Path(settings.data_dir, "corpus")


def _sources() -> list[dict]:
    path = corpus_dir() / "sources.json"
    if not path.exists():
        raise DataUnavailable("data_unavailable", f"Corpus absent : {path} (prérequis P3)")
    return json.loads(path.read_text(encoding="utf-8"))


def _read(path: Path) -> str:
    if path.suffix.lower() in TEXT_SUFFIXES:
        return path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError:
            log.warning("pypdf absent : %s ignoré", path.name)
            return ""
        return "\n".join(page.extract_text() or "" for page in PdfReader(path).pages)
    log.warning("Format non pris en charge : %s", path.name)
    return ""


def chunk(text: str, size: int = CHUNK_WORDS, overlap: int = OVERLAP_WORDS) -> list[str]:
    """Fenêtres de `size` mots (chevauchement `overlap`). Les fins de ligne sont gardées (tableaux,
    puces, titres) pour que l'assistant puisse citer une ligne précise du document."""
    words: list[str] = []
    ends: list[str] = []   # séparateur après chaque mot : " " ou "\n" (fin de ligne / paragraphe)
    for line in text.split("\n"):
        ws = line.split()
        if not ws:
            if ends:
                ends[-1] = "\n\n"
            continue
        words += ws
        ends += [" "] * (len(ws) - 1) + ["\n"]
    if not words:
        return []
    step = size - overlap
    return ["".join(w + e for w, e in zip(words[i:i + size], ends[i:i + size])).strip()
            for i in range(0, max(len(words) - overlap, 1), step)]


def chunk_id(file: str, index: int) -> str:
    return hashlib.sha1(f"{file}{index}".encode()).hexdigest()


def ingest() -> dict:
    entries = _sources()
    files_done, total = [], 0
    with SessionLocal() as db:
        for e in entries:
            path = corpus_dir() / e["file"]
            if not path.exists():
                log.warning("Document absent : %s", path)
                continue
            parts = chunk(_read(path))
            if not parts:
                continue
            vectors = embeddings.embed(parts)
            rows = [{"id": chunk_id(e["file"], i), "file": e["file"], "chunk_index": i, "title": e["title"],
                     "source_url": e["source_url"], "content": text, "region_ids": e.get("region_ids") or [],
                     "indicators": e.get("indicators") or [], "embedding": vec}
                    for i, (text, vec) in enumerate(zip(parts, vectors))]
            stmt = insert(RagChunk).values(rows)
            db.execute(stmt.on_conflict_do_update(index_elements=[RagChunk.id], set_={
                c: stmt.excluded[c] for c in ("file", "chunk_index", "title", "source_url", "content",
                                              "region_ids", "indicators", "embedding")}))
            db.execute(delete(RagChunk).where(RagChunk.file == e["file"], RagChunk.chunk_index >= len(parts)))
            files_done.append(e["file"])
            total += len(parts)
        db.execute(delete(RagChunk).where(RagChunk.file.not_in(files_done or [""])))
        db.commit()
    return {"documents": len(files_done), "chunks": total}


def list_documents() -> dict:
    with SessionLocal() as db:
        rows = db.execute(select(RagChunk.file, RagChunk.title, RagChunk.source_url, func.count())
                          .group_by(RagChunk.file, RagChunk.title, RagChunk.source_url)
                          .order_by(RagChunk.file)).all()
    return {"documents": [{"file": f, "title": t, "source_url": u, "chunks": n} for f, t, u, n in rows]}

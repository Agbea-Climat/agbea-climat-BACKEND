"""Connexion PostgreSQL + pgvector. Ignoré si la base ne répond pas (docker compose up -d db)."""
import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import OperationalError

from backend.core.database import engine, ping


def _db_up() -> bool:
    try:
        return ping()
    except OperationalError:
        return False


pytestmark = [pytest.mark.db,
              pytest.mark.skipif(not _db_up(), reason="PostgreSQL injoignable (docker compose up -d db)")]


def test_pgvector_extension():
    with engine.connect() as conn:
        assert conn.execute(text("SELECT 1 FROM pg_extension WHERE extname = 'vector'")).scalar() == 1


def test_tables_migrated():
    tables = set(inspect(engine).get_table_names())
    assert {"sessions", "threads", "rag_chunks"} <= tables, "lancer : alembic upgrade head"

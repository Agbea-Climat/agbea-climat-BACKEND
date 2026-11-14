"""Mémoire des conversations : checkpointer LangGraph Postgres par thread_id.

Ouvert au démarrage de l'API (lifespan de backend.main). Si la base est injoignable, repli sur un
checkpointer en mémoire (fils perdus au redémarrage). Les tables `checkpoint*` sont créées par
LangGraph (`setup()`), hors Alembic (exclues dans migrations/env.py).
"""
import logging
from typing import Optional

from langgraph.checkpoint.memory import InMemorySaver

from backend.core.config import settings

log = logging.getLogger(__name__)

_memory = InMemorySaver()
_saver = None
_pool = None


def _conninfo() -> str:
    return settings.database_url.set(drivername="postgresql").render_as_string(hide_password=False)


async def open_saver() -> None:
    global _saver, _pool
    try:
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
        from psycopg.rows import dict_row
        from psycopg_pool import AsyncConnectionPool

        _pool = AsyncConnectionPool(_conninfo(), max_size=5, open=False,
                                    kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row})
        await _pool.open(wait=True, timeout=5)
        _saver = AsyncPostgresSaver(_pool)
        await _saver.setup()
    except Exception as e:  # base absente : mémoire locale
        log.warning("Checkpointer Postgres indisponible (%s) : mémoire en RAM", e)
        await close_saver()


async def close_saver() -> None:
    global _saver, _pool
    if _pool is not None:
        await _pool.close()
    _saver, _pool = None, None


def get_saver():
    return _saver or _memory


def backend_name() -> Optional[str]:
    return "postgres" if _saver else "memory"

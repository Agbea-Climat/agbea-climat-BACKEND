"""Connexion SQLite (module standard `sqlite3`), chemin lu dans Settings.DB_PATH."""
import sqlite3

from backend.core.config import settings


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(settings.db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

"""Accès SQLite (sessions, threads). Tables créées par M03/M04, voir MISSIONS.md."""
from .sqlite import get_connection

__all__ = ["get_connection"]

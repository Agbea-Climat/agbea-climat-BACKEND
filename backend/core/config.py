"""Configuration (pydantic-settings, lit .env). Voir .env.example."""
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL, make_url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    data_dir: Path = Path("data")
    cors_origins: str = "http://localhost:5173,https://agbea-climat.vercel.app"

    # PostgreSQL + pgvector
    postgres_user: str = "agbea"
    postgres_password: str = "agbea"
    postgres_db: str = "agbea"
    postgres_host: str = "localhost"
    postgres_port: int = 5433
    database_url_override: str = Field(default="", validation_alias="DATABASE_URL")
    db_pool_size: int = 5
    db_echo: bool = False

    llm_provider: Literal["anthropic", "openrouter"] = "openrouter"
    llm_model: str = ""          # vide = modèle par défaut du fournisseur (chatbot/llm/client.py)
    llm_api_key: str = ""
    llm_base_url: str = ""       # vide = URL par défaut du fournisseur (OpenRouter : https://openrouter.ai/api/v1)
    # En-têtes facultatifs d'OpenRouter (classement de l'application sur openrouter.ai) ; vides = non envoyés
    openrouter_app_url: str = ""
    openrouter_app_name: str = ""

    # Notes vocales (AGBÉA Voice, M21 — encore en développement : POST /voice/transcribe répond 501).
    # Même compte OpenRouter que l'assistant : LLM_API_KEY et LLM_BASE_URL servent aussi à la voix.
    voice_model: str = ""        # id OpenRouter d'un modèle acceptant l'audio ; vide = voix désactivée
    voice_language: str = "fr"   # langue attendue des notes vocales
    embedding_model: str = ""
    embedding_dim: int = 1024

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def database_url(self) -> URL:
        """URL SQLAlchemy (driver psycopg 3). DATABASE_URL prime sur les POSTGRES_*."""
        if self.database_url_override:
            url = make_url(self.database_url_override)
            # postgres:// ou postgresql:// (format des hébergeurs) → driver psycopg 3
            if url.drivername in ("postgres", "postgresql"):
                url = url.set(drivername="postgresql+psycopg")
            return url
        return URL.create("postgresql+psycopg", username=self.postgres_user,
                          password=self.postgres_password, host=self.postgres_host,
                          port=self.postgres_port, database=self.postgres_db)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

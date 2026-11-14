"""Configuration (pydantic-settings, lit .env). Voir .env.example."""
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    data_dir: Path = Path("data")
    db_path: Path = Path("agbea.sqlite")
    chroma_dir: Path = Path(".chroma")
    cors_origins: str = "http://localhost:5173,https://agbea-climat.vercel.app"

    llm_provider: Literal["anthropic", "openai"] = "anthropic"
    llm_model: str = ""
    llm_api_key: str = ""
    embedding_model: str = ""

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

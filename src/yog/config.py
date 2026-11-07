from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for the loader and client.

    Values can be supplied through environment variables or a local ``.env``
    file. The defaults match ``compose.yaml``.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    database_url: str = "postgresql+psycopg://yog:yog@localhost:5432/yog"
    data_root: Path = Field(default=Path("dataset/raw"))
    ingest_workers: int = Field(default=8, ge=1, le=64)
    copy_batch_size: int = Field(default=100_000, ge=1_000)
    news_batch_size: int = Field(default=50, ge=1, le=1_000)

    @property
    def libpq_url(self) -> str:
        """Return the DSN understood by ``psycopg.connect``."""
        return self.database_url.replace("postgresql+psycopg://", "postgresql://", 1)


@lru_cache
def get_settings() -> Settings:
    return Settings()

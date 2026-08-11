"""
Centralized application configuration.

All configuration is loaded from environment variables / a .env file via
pydantic-settings. Never hardcode secrets here — see .env.example.
"""
from functools import lru_cache
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- App ---
    APP_NAME: str = "Agentic Recommendation System"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    API_V1_PREFIX: str = "/api/v1"

    # --- Database ---
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/recsys"
    DATABASE_URL_SYNC: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/recsys"

    # --- Security / JWT ---
    SECRET_KEY: str = "insecure-dev-secret-change-me"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # --- CORS ---
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:5173"]

    # --- Event ingestion ---
    EVENT_BATCH_MAX_SIZE: int = 100
    EVENT_RATE_LIMIT_PER_MINUTE: int = 120
    AUTH_RATE_LIMIT_PER_MINUTE: int = 10

    # --- Recommendations ---
    RECOMMENDATION_MODEL_VERSION: str = "v1"
    RECOMMENDATION_DEFAULT_LIMIT: int = 10

    RECOMMENDATION_ENGINE: str = "agentic"

    LLM_TIMEOUT_SECONDS : int = 30

    MESHAPI_API_KEY : str = 'rsk_01KZK6QCFTWYEADYHEQEABRAQ0'

    MESHAPI_BASE_URL : str = 'https://api.meshapi.ai'


@lru_cache
def get_settings() -> Settings:
    """Cached settings accessor so we parse the environment only once."""
    return Settings()


settings = get_settings()

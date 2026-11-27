from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "ReconIQ"
    environment: str = "development"
    secret_key: str = "development-only-secret-change-in-production"
    database_url: str = "sqlite:///./reconiq.db"
    redis_url: str = "redis://localhost:6379/0"
    cors_origins: str = "http://localhost:5173"
    max_upload_mb: int = 10
    demo_run_quota: int = 20
    access_token_minutes: int = 30
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()

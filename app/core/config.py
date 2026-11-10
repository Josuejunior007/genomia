from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_name: str = "GenomAI API"
    app_env: str = "development"
    database_url: str
    app_database_url: str = "sqlite:///./genomai_app.db"
    db_schema: str = "public"
    db_read_only: bool = True
    ai_enabled: bool = False
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-3.8-flash"
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:5173"]
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

@lru_cache
def get_settings() -> Settings:
    return Settings()

settings = get_settings()

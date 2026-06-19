from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_name: str = "Nano Core"
    app_env: str = "development"
    database_url: str = "sqlite:///./data/nano_core.sqlite3"
    llm_base_url: str = "http://localhost:11434"
    llm_model: str = "local-assistant"
    llm_timeout_seconds: int = Field(default=60, ge=1)


@lru_cache
def get_settings() -> Settings:
    return Settings()

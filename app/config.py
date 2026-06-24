from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_name: str = "Nano Core"
    app_env: str = "development"
    database_url: str = "sqlite:///./data/nano_core.sqlite3"
    workspace_root: str = "."
    llm_provider: Literal["local", "auto", "ollama", "llama_cpp", "llama_cpp_server"] = "local"
    llm_model_path: str = ""
    llm_base_url: str = "http://localhost:11434"
    llm_model: str = "local-assistant"
    llm_timeout_seconds: int = Field(default=60, ge=1)
    llm_context_size: int = Field(default=4096, ge=512)
    llm_max_tokens: int = Field(default=512, ge=1)
    llm_temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    voice_backend: Literal["glados"] = "glados"
    voice_glados_repo_path: str = "./vendor/GLaDOS-TTS"
    voice_sample_rate: int = Field(default=22050, ge=8000)
    chat_history_limit: int = Field(default=12, ge=0)
    note_context_limit: int = Field(default=5, ge=0)
    reminder_poll_interval_seconds: int = Field(default=30, ge=5)
    health_check_interval_seconds: int = Field(default=1800, ge=60)
    database_size_warning_bytes: int = Field(default=50_000_000, ge=1)


@lru_cache
def get_settings() -> Settings:
    """
    Get settings.

    Returns:
        Settings result.
    """
    return Settings()

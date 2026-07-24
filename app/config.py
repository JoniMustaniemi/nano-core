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
    llm_context_size: int = Field(default=32768, ge=512)
    llm_max_tokens: int = Field(default=512, ge=1)
    llm_temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    voice_backend: Literal["glados"] = "glados"
    voice_glados_repo_path: str = "./vendor/GLaDOS-TTS"
    voice_sample_rate: int = Field(default=22050, ge=8000)
    chat_history_limit: int = Field(default=12, ge=0)
    note_context_limit: int = Field(default=5, ge=0)
    reminder_poll_interval_seconds: int = Field(default=30, ge=5)
    health_check_interval_seconds: int = Field(default=1800, ge=60)
    health_test_failure_enabled: bool = False
    health_test_failure_detail: str = "Intentional health-check failure for testing."
    database_size_warning_bytes: int = Field(default=50_000_000, ge=1)
    github_default_base_branch: str = "main"
    git_executable: str = ""
    github_cli_path: str = ""
    github_pr_verify_command: str = ""
    github_pr_verify_timeout_seconds: int = Field(default=300, ge=1)
    pr_naming_diff_max_chars: int = Field(default=4000, ge=256)
    proactive_background_interval_seconds: int = Field(default=300, ge=30)
    idle_examine_idle_seconds: int = Field(default=300, ge=60)
    proactive_outreach_idle_seconds: int = Field(default=600, ge=60)
    proactive_outreach_enabled: bool = True
    idle_examine_enabled: bool = True
    codebase_crawl_files_per_tick: int = Field(default=1, ge=1)
    presence_check_timeout_seconds: int = Field(default=60, ge=10)
    presence_check_poll_interval_seconds: int = Field(default=10, ge=1)
    internal_note_retry_interval_seconds: int = Field(default=1800, ge=60)
    internal_note_retry_max_interval_seconds: int = Field(default=14400, ge=300)
    internal_note_max_attempts: int = Field(default=5, ge=1)
    self_improve_allowed_prefix: str = "app/"
    self_improve_max_files: int = Field(default=5, ge=1)
    self_improve_max_file_chars: int = Field(default=8000, ge=256)
    self_improve_plan_max_tokens: int = Field(default=8192, ge=512)
    proactive_conversation_id: str = "agent-default"


@lru_cache
def get_settings() -> Settings:
    """
    Get settings.

    Returns:
        Settings result.
    """
    return Settings()

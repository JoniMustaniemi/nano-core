from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_name: str = "Nano Core"
    app_env: str = "development"
    database_url: str = "sqlite:///./data/nano_core.sqlite3"
    workspace_root: str = "."
    llm_provider: Literal["local", "auto", "ollama", "llama_cpp", "llama_cpp_server"] = "local"
    llm_model_path: str = "./models/qwen2.5-1.5b-instruct-q5_k_m.gguf"
    llm_code_model_path: str = "./models/qwen2.5-coder-1.5b-instruct-q5_k_m.gguf"
    llm_base_url: str = "http://localhost:11434"
    llm_model: str = "local-assistant"
    llm_code_model: str = ""
    llm_timeout_seconds: int = Field(default=60, ge=1)
    llm_context_size: int = Field(default=32768, ge=512)
    llm_code_context_size: int = Field(default=32768, ge=512)
    llm_max_tokens: int = Field(default=512, ge=1)
    llm_temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    voice_backend: Literal["glados"] = "glados"
    voice_glados_repo_path: str = "./vendor/GLaDOS-TTS"
    voice_sample_rate: int = Field(default=22050, ge=8000)
    chat_history_limit: int = Field(default=12, ge=0)
    timer_poll_interval_seconds: int = Field(default=30, ge=5)
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
    internal_note_retry_interval_seconds: int = Field(default=1800, ge=60)
    internal_note_retry_max_interval_seconds: int = Field(default=14400, ge=300)
    internal_note_max_attempts: int = Field(default=5, ge=1)
    proactive_conversation_id: str = "agent-default"
    google_credentials_path: str = "./credentials.json"
    google_token_path: str = "./token.json"
    google_calendar_timezone: str = "Europe/Helsinki"
    google_calendar_ids: str = "primary"
    api_key: str = ""
    cors_allowed_origins: list[str] = Field(default_factory=list)
    auto_update_on_start: bool = False
    auto_update_branch: str = "main"
    auto_update_install: bool = False
    reboot_enabled: bool = False
    service_restart_enabled: bool = False
    service_unit_name: str = "nano-core"
    api_bind_host: str = "0.0.0.0"
    api_bind_port: int = Field(default=8000, ge=1, le=65535)
    voice_input_enabled: bool = False
    voice_input_device: str = ""
    voice_output_device: str = ""
    stt_backend: Literal["vosk"] = "vosk"
    stt_model_path: str = "./models/vosk-model-small-en-us-0.15"
    voice_wake_phrase: str = "hey nano"
    voice_command_timeout_seconds: float = Field(default=5.0, ge=1.0)
    voice_playback_mode: Literal["local", "browser", "both"] = "both"

    @field_validator("cors_allowed_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: object) -> list[str]:
        if value is None or value == "":
            return []
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        if isinstance(value, list):
            return [str(origin).strip() for origin in value if str(origin).strip()]
        return []


@lru_cache
def get_settings() -> Settings:
    """
    Get settings.

    Returns:
        Settings result.
    """
    return Settings()

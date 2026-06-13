from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

LogLevel = Literal["debug", "info", "warning", "error"]


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables and `.env`."""

    host: str = "127.0.0.1"
    port: int = Field(default=9999, ge=1, le=65535)
    mcp_path: str = "/mcp"
    log_level: LogLevel = "info"
    vault_path: Path = Path("./vault")
    github_push_enabled: bool = False

    model_config = SettingsConfigDict(env_prefix="KB_", env_file=".env", extra="ignore")

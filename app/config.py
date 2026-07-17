from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv()


class Settings(BaseSettings):
    """Application settings loaded from environment variables or .env."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_timezone: str = Field(default="Asia/Shanghai", alias="APP_TIMEZONE")
    app_port: int = Field(default=8088, alias="APP_PORT")
    web_access_token: str = Field(default="", alias="WEB_ACCESS_TOKEN")

    mock_ai: bool = Field(default=False, alias="MOCK_AI")
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4o-mini", alias="OPENAI_MODEL")
    openai_base_url: str = Field(default="", alias="OPENAI_BASE_URL")

    dingtalk_webhook: str = Field(default="", alias="DINGTALK_WEBHOOK")
    dingtalk_secret: str = Field(default="", alias="DINGTALK_SECRET")

    birth_calendar: Literal["solar", "lunar"] = Field(default="solar", alias="BIRTH_CALENDAR")
    birth_date: str = Field(default="1990-01-01", alias="BIRTH_DATE")
    birth_time: str = Field(default="08:00", alias="BIRTH_TIME")
    birth_place: str = Field(default="未知", alias="BIRTH_PLACE")
    birth_gender: str = Field(default="unknown", alias="BIRTH_GENDER")

    daily_push_cron: str = Field(default="0 8 * * *", alias="DAILY_PUSH_CRON")
    data_dir: Path = Field(default=Path("data"), alias="DATA_DIR")

    @field_validator("web_access_token")
    @classmethod
    def token_not_placeholder(cls, value: str) -> str:
        return value.strip()

    @field_validator("birth_date")
    @classmethod
    def birth_date_format(cls, value: str) -> str:
        parts = value.split("-")
        if len(parts) != 3 or not all(part.isdigit() for part in parts):
            raise ValueError("BIRTH_DATE must use YYYY-MM-DD")
        return value

    @field_validator("birth_time")
    @classmethod
    def birth_time_format(cls, value: str) -> str:
        parts = value.split(":")
        if len(parts) not in (2, 3) or not all(part.isdigit() for part in parts):
            raise ValueError("BIRTH_TIME must use HH:mm or HH:mm:ss")
        hour = int(parts[0])
        minute = int(parts[1])
        if hour < 0 or hour > 23 or minute < 0 or minute > 59:
            raise ValueError("BIRTH_TIME hour/minute out of range")
        return value

    def require_web_auth(self) -> None:
        if not self.web_access_token or self.web_access_token == "change-this-private-token":
            raise RuntimeError("WEB_ACCESS_TOKEN is not configured securely")

    def require_openai(self) -> None:
        if self.mock_ai:
            return
        if not self.openai_api_key or self.openai_api_key.startswith("your-"):
            raise RuntimeError("OPENAI_API_KEY is not configured; set MOCK_AI=true for local testing")

    @field_validator("openai_base_url")
    @classmethod
    def normalize_openai_base_url(cls, value: str) -> str:
        return value.strip().rstrip("/")

    def require_dingtalk(self) -> None:
        if not self.dingtalk_webhook or "access_token=xxx" in self.dingtalk_webhook:
            raise RuntimeError("DINGTALK_WEBHOOK is not configured")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    return settings

"""Application settings loaded from environment and optional local files."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from isa_system.constants import DEFAULT_ARTIFACTS_PATH, DEFAULT_DATA_LAKE_PATH, DEFAULT_SQLITE_DSN
from isa_system.domain.enums import RuntimeMode


class Settings(BaseSettings):
    """Runtime settings with safe local defaults."""

    model_config = SettingsConfigDict(
        env_file=("env.local", ".env.local", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    environment: str = Field(
        default="local", validation_alias=AliasChoices("ISA_ENVIRONMENT", "ENVIRONMENT")
    )
    bind_host: str = Field(
        default="127.0.0.1", validation_alias=AliasChoices("ISA_BIND_HOST", "BIND_HOST")
    )
    bind_port: int = Field(
        default=8000, validation_alias=AliasChoices("ISA_BIND_PORT", "BIND_PORT")
    )
    runtime_mode: RuntimeMode = Field(
        default=RuntimeMode.PREVIEW,
        validation_alias=AliasChoices("ISA_RUNTIME_MODE", "RUNTIME_MODE"),
    )
    live_armed: bool = Field(
        default=False, validation_alias=AliasChoices("ISA_LIVE_ARMED", "LIVE_ARMED")
    )
    kill_switch_enabled: bool = Field(
        default=False,
        validation_alias=AliasChoices("ISA_KILL_SWITCH_ENABLED", "KILL_SWITCH_ENABLED"),
    )
    timezone: str = Field(
        default="Europe/London", validation_alias=AliasChoices("ISA_TIMEZONE", "TIMEZONE")
    )
    data_lake_path: Path = Field(
        default=DEFAULT_DATA_LAKE_PATH,
        validation_alias=AliasChoices("ISA_DATA_LAKE_PATH", "DATA_LAKE_PATH"),
    )
    artifacts_path: Path = Field(
        default=DEFAULT_ARTIFACTS_PATH,
        validation_alias=AliasChoices("ISA_ARTIFACTS_PATH", "ARTIFACTS_PATH"),
    )
    operational_db_dsn: str = Field(
        default=DEFAULT_SQLITE_DSN,
        validation_alias=AliasChoices("ISA_OPERATIONAL_DB_DSN", "OPERATIONAL_DB_DSN"),
    )

    trading212_api_key: SecretStr | None = Field(
        default=None, validation_alias=AliasChoices("TRADING212_API_KEY", "T212_API_KEY")
    )
    trading212_api_secret: SecretStr | None = Field(
        default=None, validation_alias=AliasChoices("TRADING212_API_SECRET", "T212_API_SECRET")
    )
    trading212_environment: str = Field(
        default="demo", validation_alias=AliasChoices("TRADING212_ENVIRONMENT", "T212_ENVIRONMENT")
    )
    alpha_vantage_api_key: SecretStr | None = Field(
        default=None, validation_alias="ALPHA_VANTAGE_API_KEY"
    )
    fmp_api_key: SecretStr | None = Field(default=None, validation_alias="FMP_API_KEY")
    fred_api_key: SecretStr | None = Field(default=None, validation_alias="FRED_API_KEY")
    companies_house_api_key: SecretStr | None = Field(
        default=None, validation_alias="COMPANIES_HOUSE_API_KEY"
    )
    sec_user_agent: str | None = Field(default=None, validation_alias="SEC_USER_AGENT")
    reddit_client_id: SecretStr | None = Field(default=None, validation_alias="REDDIT_CLIENT_ID")
    reddit_client_secret: SecretStr | None = Field(
        default=None, validation_alias="REDDIT_CLIENT_SECRET"
    )
    x_bearer_token: SecretStr | None = Field(default=None, validation_alias="X_BEARER_TOKEN")
    openai_api_key: SecretStr | None = Field(default=None, validation_alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4o-mini", validation_alias="OPENAI_MODEL")


@lru_cache
def get_settings() -> Settings:
    """Return cached settings."""

    return Settings()


def clear_settings_cache() -> None:
    """Clear cached settings after env-file changes in long-running apps."""

    get_settings.cache_clear()

from functools import lru_cache
from typing import Literal, Self

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError


class Settings(BaseSettings):
    """Validate deployment configuration before serving requests; redact credentials."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: Literal["development", "test"] = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    database_url: SecretStr
    database_connect_timeout_seconds: int = Field(default=3, ge=1, le=30)
    langfuse_enabled: bool = False
    langfuse_public_key: str = ""
    langfuse_secret_key: SecretStr = SecretStr("")
    langfuse_base_url: str = "https://cloud.langfuse.com"

    @field_validator("database_url")
    @classmethod
    def postgres_url(cls, value: SecretStr) -> SecretStr:
        try:
            url = make_url(value.get_secret_value())
        except (ArgumentError, ValueError) as exc:
            raise ValueError("DATABASE_URL must be a valid PostgreSQL URL") from exc
        if url.drivername != "postgresql+psycopg" or not url.host or not url.database:
            raise ValueError("DATABASE_URL must use postgresql+psycopg with a host and database")
        return value

    @model_validator(mode="after")
    def langfuse_credentials(self) -> Self:
        if self.langfuse_enabled and not (
            self.langfuse_public_key and self.langfuse_secret_key.get_secret_value()
        ):
            raise ValueError("Langfuse credentials are required when enabled")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()

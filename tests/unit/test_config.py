import pytest
from pydantic import ValidationError

from app.config import Settings


@pytest.mark.parametrize("url", ["sqlite:///test.db", "postgresql://localhost/test", "invalid"])
def test_rejects_unsupported_database_configuration(settings: Settings, url: str) -> None:
    with pytest.raises(ValidationError, match="DATABASE_URL"):
        Settings(_env_file=None, database_url=url, langfuse_enabled=False)


def test_credentials_are_redacted(settings: Settings) -> None:
    configured = Settings(
        _env_file=None,
        database_url="postgresql+psycopg://user:secret-db-password@localhost/test",
        langfuse_enabled=True,
        langfuse_public_key="public",
        langfuse_secret_key="secret-trace-key",
    )
    for rendered in (repr(configured), configured.model_dump_json()):
        assert "secret-db-password" not in rendered
        assert "secret-trace-key" not in rendered


def test_enabled_langfuse_requires_credentials(settings: Settings) -> None:
    with pytest.raises(ValidationError, match="Langfuse credentials"):
        Settings(
            _env_file=None,
            database_url=settings.database_url,
            langfuse_enabled=True,
            langfuse_public_key="",
            langfuse_secret_key="",
        )


def test_environment_can_configure_database(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:password@localhost/support")
    monkeypatch.setenv("LANGFUSE_ENABLED", "false")
    settings = Settings(_env_file=None)
    assert settings.database_url.get_secret_value().endswith("/support")

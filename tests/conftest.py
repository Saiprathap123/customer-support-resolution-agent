import pytest

from app.config import Settings


@pytest.fixture
def settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    # Independent of developer .env files and optional hosted-service credentials.
    monkeypatch.setenv("LANGFUSE_ENABLED", "false")
    return Settings(
        _env_file=None,
        environment="test",
        database_url="postgresql+psycopg://test:test@127.0.0.1:1/support_test",
        database_connect_timeout_seconds=1,
    )

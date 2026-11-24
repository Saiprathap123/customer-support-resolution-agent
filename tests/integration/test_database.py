import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.config import Settings
from app.main import create_app


@pytest.mark.postgres
def test_readiness_uses_real_postgres(settings: Settings) -> None:
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set TEST_DATABASE_URL to exercise a real PostgreSQL connection")
    settings = Settings(_env_file=None, database_url=url, langfuse_enabled=False)
    app = create_app(settings)
    with TestClient(app) as client:
        response = client.get("/ready")
        assert response.status_code == 200
        assert response.json() == {"status": "ready"}
        with app.state.engine.connect() as connection:
            version = connection.scalar(text("SELECT version()"))
            assert version.startswith("PostgreSQL")

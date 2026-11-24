from uuid import UUID

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def test_liveness_does_not_require_a_database(settings: Settings) -> None:
    with TestClient(create_app(settings)) as client:
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
        assert UUID(response.headers["x-request-id"]).version == 4


def test_database_outage_has_a_redacted_retryable_error(settings: Settings) -> None:
    with TestClient(create_app(settings)) as client:
        response = client.get("/ready")
        assert response.status_code == 503
        assert response.json() == {
            "success": False,
            "error_code": "DATABASE_UNAVAILABLE",
            "retryable": True,
            "message": "Database is unavailable",
        }
        assert "test:test" not in response.text
        assert client.get("/health").status_code == 200


def test_generated_request_id_does_not_trust_incoming_value(settings: Settings) -> None:
    with TestClient(create_app(settings)) as client:
        response = client.get("/health", headers={"x-request-id": "untrusted"})
        assert response.headers["x-request-id"] != "untrusted"

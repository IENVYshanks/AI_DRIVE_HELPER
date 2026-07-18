"""Application-level tests that do not require external services."""

from unittest import TestCase

from fastapi.testclient import TestClient

from src.app import create_app
from src.db.config import get_settings


class ApplicationTests(TestCase):
    def test_liveness_and_security_headers(self) -> None:
        settings = get_settings().model_copy(
            update={
                "ENVIRONMENT": "test",
                "AUTO_CREATE_TABLES": False,
                "TRUSTED_HOSTS": "localhost,testserver",
            }
        )
        with TestClient(create_app(settings)) as client:
            response = client.get(
                "/health/live",
                headers={"X-Request-ID": "test-request-id"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})
        self.assertEqual(response.headers["X-Request-ID"], "test-request-id")
        self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(response.headers["X-Frame-Options"], "DENY")

    def test_production_disables_interactive_api_docs(self) -> None:
        settings = get_settings().model_copy(
            update={
                "ENVIRONMENT": "production",
                "AUTO_CREATE_TABLES": False,
                "ENABLE_API_DOCS": False,
                "TRUSTED_HOSTS": "localhost,testserver",
            }
        )
        with TestClient(create_app(settings)) as client:
            response = client.get("/docs")

        self.assertEqual(response.status_code, 404)

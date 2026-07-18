"""Tests for safety-critical production configuration rules."""

from unittest import TestCase

from pydantic import ValidationError

from src.db.config import Settings


BASE_SETTINGS = {
    "DB_USERNAME": "app",
    "DB_PASSWORD": "database-secret",
    "DB_NAME": "app",
}


class ProductionSettingsTests(TestCase):
    def test_production_rejects_development_conveniences(self) -> None:
        with self.assertRaises(ValidationError) as context:
            Settings(
                **BASE_SETTINGS,
                ENVIRONMENT="production",
                AUTO_CREATE_TABLES=True,
                ALLOW_INSECURE_EMAIL_AUTH=True,
            )

        message = str(context.exception)
        self.assertIn("AUTO_CREATE_TABLES must be false", message)
        self.assertIn("ALLOW_INSECURE_EMAIL_AUTH must be false", message)

    def test_valid_production_configuration_is_accepted(self) -> None:
        settings = Settings(
            **BASE_SETTINGS,
            ENVIRONMENT="production",
            AUTO_CREATE_TABLES=False,
            ALLOW_INSECURE_EMAIL_AUTH=False,
            ENABLE_API_DOCS=False,
            TRUSTED_HOSTS="api.example.com",
            BACKEND_CORS_ORIGINS="https://app.example.com",
            SUPABASE_URL="https://project.supabase.co",
            SUPABASE_SERVICE_ROLE_KEY="service-role-secret",
            SUPABASE_STORAGE_BUCKET="images",
            TASK_QUEUE_MODE="celery",
            CELERY_BROKER_URL="redis://redis:6379/0",
        )

        self.assertTrue(settings.is_production)
        self.assertEqual(settings.trusted_hosts, ["api.example.com"])
        self.assertEqual(settings.cors_origins, ["https://app.example.com"])

    def test_invalid_environment_name_is_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            Settings(**BASE_SETTINGS, ENVIRONMENT="prod")

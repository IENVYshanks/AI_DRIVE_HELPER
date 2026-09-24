"""Tests for safety-critical production configuration rules."""

from unittest import TestCase

from pydantic import ValidationError

from src.db.config import Settings


BASE_SETTINGS = {
    "DB_USERNAME": "app",
    "DB_PASSWORD": "database-secret",
    "DB_NAME": "app",
}
OAUTH_ENCRYPTION_KEY = "11" * 32


class ProductionSettingsTests(TestCase):
    def test_production_rejects_development_conveniences(self) -> None:
        with self.assertRaises(ValidationError) as context:
            Settings(
                **BASE_SETTINGS,
                ENVIRONMENT="production",
                AUTO_CREATE_TABLES=True,
            )

        message = str(context.exception)
        self.assertIn("AUTO_CREATE_TABLES must be false", message)

    def test_valid_production_configuration_is_accepted(self) -> None:
        settings = Settings(
            **BASE_SETTINGS,
            ENVIRONMENT="production",
            AUTO_CREATE_TABLES=False,
            ENABLE_API_DOCS=False,
            TRUSTED_HOSTS="api.example.com",
            BACKEND_CORS_ORIGINS="https://app.example.com",
            SUPABASE_URL="https://project.supabase.co",
            SUPABASE_SERVICE_ROLE_KEY="service-role-secret",
            SUPABASE_STORAGE_BUCKET="images",
            TASK_QUEUE_MODE="celery",
            CELERY_BROKER_URL="redis://redis:6379/0",
            GOOGLE_CLIENT_ID="google-client-id",
            GOOGLE_CLIENT_SECRET="google-client-secret",
            GOOGLE_REDIRECT_URI="https://app.example.com",
            SESSION_COOKIE_SECURE=True,
            OAUTH_TOKEN_ENCRYPTION_KEYS=f"primary:{OAUTH_ENCRYPTION_KEY}",
            OAUTH_TOKEN_ACTIVE_KEY_ID="primary",
        )

        self.assertTrue(settings.is_production)
        self.assertEqual(settings.trusted_hosts, ["api.example.com"])
        self.assertEqual(settings.cors_origins, ["https://app.example.com"])

    def test_invalid_environment_name_is_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            Settings(**BASE_SETTINGS, ENVIRONMENT="prod")

    def test_rejects_invalid_oauth_encryption_key_material(self) -> None:
        settings = Settings(
            **BASE_SETTINGS,
            OAUTH_TOKEN_ENCRYPTION_KEYS="primary:not-a-32-byte-hex-key",
            OAUTH_TOKEN_ACTIVE_KEY_ID="primary",
        )

        with self.assertRaisesRegex(ValueError, "hexadecimal"):
            _ = settings.oauth_token_encryption_keys

    def test_rejects_non_positive_google_oauth_rate_limit(self) -> None:
        with self.assertRaises(ValidationError):
            Settings(
                **BASE_SETTINGS,
                MAX_GOOGLE_OAUTH_ATTEMPTS_PER_IP_PER_MINUTE=0,
            )

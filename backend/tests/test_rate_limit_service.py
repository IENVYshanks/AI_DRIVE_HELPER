"""Unit tests for shared and development OAuth rate limiting."""

from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch

import src.services.rate_limit_service as rate_limits
from src.services.rate_limit_service import (
    RateLimitExceededError,
    RateLimitUnavailableError,
    enforce_google_oauth_rate_limit,
)


class OAuthRateLimitTests(TestCase):
    def setUp(self) -> None:
        rate_limits._LOCAL_COUNTS.clear()
        rate_limits._LOCAL_WINDOW = None

    @patch("src.services.rate_limit_service.time.time", return_value=120)
    def test_local_limiter_rejects_attempt_over_limit(self, _time) -> None:
        settings = SimpleNamespace(
            CELERY_BROKER_URL=None,
            MAX_GOOGLE_OAUTH_ATTEMPTS_PER_IP_PER_MINUTE=2,
        )

        enforce_google_oauth_rate_limit("192.0.2.1", settings)
        enforce_google_oauth_rate_limit("192.0.2.1", settings)
        with self.assertRaises(RateLimitExceededError) as context:
            enforce_google_oauth_rate_limit("192.0.2.1", settings)

        self.assertEqual(context.exception.retry_after, 60)

    @patch("src.services.rate_limit_service._get_redis_client")
    @patch("src.services.rate_limit_service.time.time", return_value=125)
    def test_redis_limiter_uses_hashed_identity_and_atomic_script(
        self,
        _time,
        get_client,
    ) -> None:
        client = get_client.return_value
        client.eval.return_value = 1
        settings = SimpleNamespace(
            CELERY_BROKER_URL="redis://redis:6379/0",
            MAX_GOOGLE_OAUTH_ATTEMPTS_PER_IP_PER_MINUTE=2,
        )

        enforce_google_oauth_rate_limit("192.0.2.25", settings)

        args = client.eval.call_args.args
        self.assertEqual(args[1], 1)
        self.assertNotIn("192.0.2.25", args[2])
        self.assertEqual(args[3], 60)

    @patch("src.services.rate_limit_service._get_redis_client")
    def test_configured_redis_failure_fails_closed(self, get_client) -> None:
        from redis.exceptions import ConnectionError

        client = Mock()
        client.eval.side_effect = ConnectionError("unavailable")
        get_client.return_value = client
        settings = SimpleNamespace(
            CELERY_BROKER_URL="redis://redis:6379/0",
            MAX_GOOGLE_OAUTH_ATTEMPTS_PER_IP_PER_MINUTE=2,
        )

        with self.assertRaises(RateLimitUnavailableError):
            enforce_google_oauth_rate_limit("192.0.2.1", settings)

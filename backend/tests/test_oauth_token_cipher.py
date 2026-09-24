"""Tests for encrypted Google OAuth credential storage."""

from types import SimpleNamespace
from unittest import TestCase

from src.services.oauth_token_cipher import (
    OAuthTokenEncryptionError,
    decrypt_oauth_token,
    encrypt_oauth_token,
    is_encrypted_oauth_token,
    oauth_token_needs_rotation,
)


KEY_ONE = "11" * 32
KEY_TWO = "22" * 32


def encryption_settings(*, active_key_id: str = "primary"):
    return SimpleNamespace(
        OAUTH_TOKEN_ACTIVE_KEY_ID=active_key_id,
        oauth_token_encryption_keys={
            "primary": bytes.fromhex(KEY_ONE),
            "previous": bytes.fromhex(KEY_TWO),
        },
    )


class OAuthTokenCipherTests(TestCase):
    def test_round_trip_hides_plaintext_and_authenticates_value(self) -> None:
        settings = encryption_settings()

        encrypted = encrypt_oauth_token("google-secret-token", settings)

        self.assertTrue(is_encrypted_oauth_token(encrypted))
        self.assertNotIn("google-secret-token", encrypted)
        self.assertEqual(decrypt_oauth_token(encrypted, settings), "google-secret-token")

    def test_tampered_ciphertext_is_rejected(self) -> None:
        settings = encryption_settings()
        encrypted = encrypt_oauth_token("google-secret-token", settings)
        replacement = "A" if encrypted[-1] != "A" else "B"

        with self.assertRaises(OAuthTokenEncryptionError):
            decrypt_oauth_token(encrypted[:-1] + replacement, settings)

    def test_wrong_key_is_rejected(self) -> None:
        encrypted = encrypt_oauth_token("google-secret-token", encryption_settings())
        wrong_settings = SimpleNamespace(
            OAUTH_TOKEN_ACTIVE_KEY_ID="primary",
            oauth_token_encryption_keys={"primary": bytes.fromhex(KEY_TWO)},
        )

        with self.assertRaises(OAuthTokenEncryptionError):
            decrypt_oauth_token(encrypted, wrong_settings)

    def test_old_key_can_decrypt_and_is_marked_for_rotation(self) -> None:
        old_settings = encryption_settings(active_key_id="previous")
        encrypted = encrypt_oauth_token("google-secret-token", old_settings)
        current_settings = encryption_settings(active_key_id="primary")

        self.assertEqual(
            decrypt_oauth_token(encrypted, current_settings),
            "google-secret-token",
        )
        self.assertTrue(oauth_token_needs_rotation(encrypted, current_settings))

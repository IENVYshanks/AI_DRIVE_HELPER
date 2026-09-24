"""Authenticated encryption for persisted Google OAuth credentials."""

from __future__ import annotations

import base64
import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from src.db.config import Settings


ENVELOPE_PREFIX = "enc:v1"
NONCE_BYTES = 12


class OAuthTokenEncryptionError(ValueError):
    """Raised when an OAuth token cannot be encrypted or decrypted safely."""


def encrypt_oauth_token(token: str, settings: Settings) -> str:
    """Encrypt one token with the configured active AES-256-GCM key."""
    if not token:
        raise OAuthTokenEncryptionError("OAuth token cannot be empty")

    keys = validate_oauth_token_encryption(settings)
    key_id = settings.OAUTH_TOKEN_ACTIVE_KEY_ID.strip()
    key = keys[key_id]

    nonce = os.urandom(NONCE_BYTES)
    aad = _associated_data(key_id)
    ciphertext = AESGCM(key).encrypt(nonce, token.encode("utf-8"), aad)
    payload = base64.urlsafe_b64encode(nonce + ciphertext).decode("ascii")
    return f"{ENVELOPE_PREFIX}:{key_id}:{payload}"


def decrypt_oauth_token(envelope: str, settings: Settings) -> str:
    """Decrypt and authenticate one versioned OAuth token envelope."""
    key_id, payload = _parse_envelope(envelope)
    key = _configured_keys(settings).get(key_id)
    if key is None:
        raise OAuthTokenEncryptionError("OAuth token encryption key is unavailable")

    try:
        encrypted = base64.b64decode(payload, altchars=b"-_", validate=True)
    except (ValueError, TypeError) as exc:
        raise OAuthTokenEncryptionError("OAuth token envelope is invalid") from exc
    if len(encrypted) <= NONCE_BYTES:
        raise OAuthTokenEncryptionError("OAuth token envelope is invalid")

    nonce = encrypted[:NONCE_BYTES]
    ciphertext = encrypted[NONCE_BYTES:]
    try:
        plaintext = AESGCM(key).decrypt(
            nonce,
            ciphertext,
            _associated_data(key_id),
        )
        return plaintext.decode("utf-8")
    except (InvalidTag, UnicodeDecodeError) as exc:
        raise OAuthTokenEncryptionError("OAuth token decryption failed") from exc


def is_encrypted_oauth_token(value: str | None) -> bool:
    """Return whether a database value uses the supported envelope format."""
    return bool(value and value.startswith(f"{ENVELOPE_PREFIX}:"))


def oauth_token_needs_rotation(value: str, settings: Settings) -> bool:
    """Return whether an envelope was written with a non-active key."""
    key_id, _ = _parse_envelope(value)
    return key_id != settings.OAUTH_TOKEN_ACTIVE_KEY_ID.strip()


def validate_oauth_token_encryption(settings: Settings) -> dict[str, bytes]:
    """Validate encryption configuration and return all decryption keys."""
    keys = _configured_keys(settings)
    key_id = settings.OAUTH_TOKEN_ACTIVE_KEY_ID.strip()
    if not key_id or key_id not in keys:
        raise OAuthTokenEncryptionError(
            "Active OAuth token encryption key is unavailable"
        )
    return keys


def _configured_keys(settings: Settings) -> dict[str, bytes]:
    try:
        return settings.oauth_token_encryption_keys
    except ValueError as exc:
        raise OAuthTokenEncryptionError(str(exc)) from exc


def _parse_envelope(envelope: str) -> tuple[str, str]:
    parts = envelope.split(":", 3)
    if len(parts) != 4 or ":".join(parts[:2]) != ENVELOPE_PREFIX:
        raise OAuthTokenEncryptionError("OAuth token is not encrypted")
    key_id, payload = parts[2], parts[3]
    if not key_id or not payload:
        raise OAuthTokenEncryptionError("OAuth token envelope is invalid")
    return key_id, payload


def _associated_data(key_id: str) -> bytes:
    return f"ai-image-classifier:google-oauth:v1:{key_id}".encode("utf-8")

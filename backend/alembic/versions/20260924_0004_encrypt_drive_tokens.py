"""Encrypt existing Google Drive OAuth credentials.

Revision ID: 20260924_0004
Revises: 20260924_0003
"""

from alembic import op
import sqlalchemy as sa

from src.db.config import get_settings
from src.services.oauth_token_cipher import (
    decrypt_oauth_token,
    encrypt_oauth_token,
    is_encrypted_oauth_token,
    validate_oauth_token_encryption,
)


revision = "20260924_0004"
down_revision = "20260924_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Replace plaintext token values with authenticated ciphertext envelopes."""
    settings = get_settings()
    validate_oauth_token_encryption(settings)
    connection = op.get_bind()
    rows = connection.execute(
        sa.text(
            "SELECT id, drive_access_token, drive_refresh_token FROM users "
            "WHERE drive_access_token IS NOT NULL OR drive_refresh_token IS NOT NULL"
        )
    ).mappings()

    for row in rows:
        access_token = _plaintext_value(row["drive_access_token"], settings)
        refresh_token = _plaintext_value(row["drive_refresh_token"], settings)
        connection.execute(
            sa.text(
                "UPDATE users SET drive_access_token = :access_token, "
                "drive_refresh_token = :refresh_token WHERE id = :user_id"
            ),
            {
                "user_id": row["id"],
                "access_token": (
                    encrypt_oauth_token(access_token, settings)
                    if access_token is not None
                    else None
                ),
                "refresh_token": (
                    encrypt_oauth_token(refresh_token, settings)
                    if refresh_token is not None
                    else None
                ),
            },
        )


def downgrade() -> None:
    """Decrypt token envelopes for compatibility with the previous release."""
    settings = get_settings()
    validate_oauth_token_encryption(settings)
    connection = op.get_bind()
    rows = connection.execute(
        sa.text(
            "SELECT id, drive_access_token, drive_refresh_token FROM users "
            "WHERE drive_access_token IS NOT NULL OR drive_refresh_token IS NOT NULL"
        )
    ).mappings()

    for row in rows:
        connection.execute(
            sa.text(
                "UPDATE users SET drive_access_token = :access_token, "
                "drive_refresh_token = :refresh_token WHERE id = :user_id"
            ),
            {
                "user_id": row["id"],
                "access_token": _plaintext_value(
                    row["drive_access_token"],
                    settings,
                ),
                "refresh_token": _plaintext_value(
                    row["drive_refresh_token"],
                    settings,
                ),
            },
        )


def _plaintext_value(value: str | None, settings) -> str | None:
    if value is None:
        return None
    if is_encrypted_oauth_token(value):
        return decrypt_oauth_token(value, settings)
    return value

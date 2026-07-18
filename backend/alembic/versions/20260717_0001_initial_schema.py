"""Establish the initial schema from the registered SQLAlchemy metadata.

Revision ID: 20260717_0001
Revises:
"""

from alembic import op

from src import models  # noqa: F401 - populate Base.metadata
from src.db.config import Base


revision = "20260717_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create the initial application tables and enum types."""
    Base.metadata.create_all(bind=op.get_bind(), checkfirst=True)


def downgrade() -> None:
    """Remove the initial application schema."""
    Base.metadata.drop_all(bind=op.get_bind(), checkfirst=True)

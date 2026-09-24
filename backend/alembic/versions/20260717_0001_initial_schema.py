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
    initial_tables = [
        table for table in Base.metadata.tables.values() if table.name != "auth_sessions"
    ]
    Base.metadata.create_all(
        bind=op.get_bind(),
        tables=initial_tables,
        checkfirst=True,
    )


def downgrade() -> None:
    """Remove the initial application schema."""
    initial_tables = [
        table for table in Base.metadata.tables.values() if table.name != "auth_sessions"
    ]
    Base.metadata.drop_all(
        bind=op.get_bind(),
        tables=initial_tables,
        checkfirst=True,
    )

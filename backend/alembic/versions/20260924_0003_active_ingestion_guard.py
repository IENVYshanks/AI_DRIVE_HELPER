"""Prevent duplicate active ingestion jobs for one folder.

Revision ID: 20260924_0003
Revises: 20260923_0002
"""

from alembic import op
import sqlalchemy as sa


revision = "20260924_0003"
down_revision = "20260923_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "uq_ingestion_jobs_active_folder",
        "ingestion_jobs",
        ["user_id", "folder_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('queued', 'running')"),
    )


def downgrade() -> None:
    op.drop_index("uq_ingestion_jobs_active_folder", table_name="ingestion_jobs")

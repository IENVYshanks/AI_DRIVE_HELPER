import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Integer, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import relationship

from src.db import Base
from src.models.enums import JOB_STATUS


class IngestionJob(Base):
    __tablename__ = "ingestion_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    folder_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user_folders.id", ondelete="CASCADE"),
        nullable=True,
    )

    status = Column(JOB_STATUS, nullable=False, server_default="queued")
    job_type = Column(Text, nullable=False, server_default="full")

    total = Column(Integer, nullable=False, server_default="0")
    processed = Column(Integer, nullable=False, server_default="0")
    failed = Column(Integer, nullable=False, server_default="0")

    error_message = Column(Text, nullable=True)
    failed_file_ids = Column(ARRAY(Text), nullable=True)

    queued_at = Column(DateTime(timezone=True), server_default=func.now())
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    user = relationship("User", back_populates="ingestion_jobs")
    folder = relationship("UserFolder", back_populates="ingestion_jobs")

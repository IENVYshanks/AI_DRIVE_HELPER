import uuid

from sqlalchemy import Column, DateTime, Integer, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from src.db import Base
from src.models.enums import JOB_STATUS


class ClusteringJob(Base):
    __tablename__ = "clustering_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    status = Column(JOB_STATUS, nullable=False, server_default="queued")

    faces_processed = Column(Integer, nullable=False, server_default="0")
    clusters_created = Column(Integer, nullable=False, server_default="0")
    clusters_merged = Column(Integer, nullable=False, server_default="0")

    queued_at = Column(DateTime(timezone=True), server_default=func.now())
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    user = relationship("User", back_populates="clustering_jobs")

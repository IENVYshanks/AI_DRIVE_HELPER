import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Integer, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from src.db import Base
from src.models.enums import PROCESS_STATUS


class UserFolder(Base):
    __tablename__ = "user_folders"
    __table_args__ = (
        UniqueConstraint("user_id", "drive_folder_id", name="uq_user_folder_drive"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    drive_folder_id = Column(Text, nullable=False)
    folder_name = Column(Text, nullable=True)

    status = Column(PROCESS_STATUS, nullable=False, server_default="pending")
    total_images = Column(Integer, nullable=False, server_default="0")
    processed_images = Column(Integer, nullable=False, server_default="0")
    failed_images = Column(Integer, nullable=False, server_default="0")
    error_message = Column(Text, nullable=True)

    selected_at = Column(DateTime(timezone=True), server_default=func.now())
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    user = relationship("User", back_populates="folders")
    images = relationship("Image", back_populates="folder")
    ingestion_jobs = relationship("IngestionJob", back_populates="folder")

import uuid

from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Integer, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from src.db import Base
from src.models.enums import PROCESS_STATUS


class Image(Base):
    __tablename__ = "images"
    __table_args__ = (
        UniqueConstraint("user_id", "drive_file_id", name="uq_user_drive_file"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    folder_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user_folders.id", ondelete="SET NULL"),
        nullable=True,
    )

    drive_file_id = Column(Text, nullable=False)
    drive_file_name = Column(Text, nullable=True)

    storage_key = Column(Text, nullable=True)
    storage_bucket = Column(Text, nullable=True)
    file_size_bytes = Column(BigInteger, nullable=True)
    mime_type = Column(Text, nullable=True)

    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
    taken_at = Column(DateTime(timezone=True), nullable=True)

    status = Column(PROCESS_STATUS, nullable=False, server_default="pending")
    face_count = Column(Integer, nullable=False, server_default="0")
    error_message = Column(Text, nullable=True)

    ingested_at = Column(DateTime(timezone=True), server_default=func.now())
    processed_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    user = relationship("User", back_populates="images")
    folder = relationship("UserFolder", back_populates="images")
    faces = relationship("Face", back_populates="image", cascade="all, delete")
    search_results = relationship("SearchResult", back_populates="image")

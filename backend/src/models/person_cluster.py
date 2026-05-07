import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Integer, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from src.db import Base


class PersonCluster(Base):
    __tablename__ = "person_clusters"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    label = Column(Text, nullable=True)
    thumbnail_face_id = Column(
        UUID(as_uuid=True), ForeignKey("faces.id", ondelete="SET NULL"), nullable=True
    )

    face_count = Column(Integer, nullable=False, server_default="0")
    image_count = Column(Integer, nullable=False, server_default="0")

    last_clustered_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    user = relationship("User", back_populates="person_clusters")
    faces = relationship(
        "Face",
        back_populates="cluster",
        foreign_keys="Face.cluster_id",
    )
    thumbnail_face = relationship("Face", foreign_keys=[thumbnail_face_id])

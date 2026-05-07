import uuid

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from src.db import Base


class Face(Base):
    __tablename__ = "faces"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    image_id = Column(
        UUID(as_uuid=True), ForeignKey("images.id", ondelete="CASCADE"), nullable=False
    )

    person_idx = Column(Integer, nullable=False)

    bbox_x = Column(Float, nullable=True)
    bbox_y = Column(Float, nullable=True)
    bbox_w = Column(Float, nullable=True)
    bbox_h = Column(Float, nullable=True)

    detection_score = Column(Float, nullable=True)
    qdrant_point_id = Column(Text, nullable=True)
    cluster_id = Column(
        UUID(as_uuid=True),
        ForeignKey("person_clusters.id", ondelete="SET NULL"),
        nullable=True,
    )

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="faces")
    image = relationship("Image", back_populates="faces")
    cluster = relationship(
        "PersonCluster",
        back_populates="faces",
        foreign_keys=[cluster_id],
    )
    search_results = relationship("SearchResult", back_populates="face")

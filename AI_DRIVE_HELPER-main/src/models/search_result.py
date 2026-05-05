import uuid

from sqlalchemy import Column, Float, ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from src.db import Base


class SearchResult(Base):
    __tablename__ = "search_results"
    __table_args__ = (
        UniqueConstraint("query_id", "rank", name="uq_search_result_rank"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    query_id = Column(
        UUID(as_uuid=True),
        ForeignKey("search_queries.id", ondelete="CASCADE"),
        nullable=False,
    )
    image_id = Column(
        UUID(as_uuid=True), ForeignKey("images.id", ondelete="CASCADE"), nullable=False
    )
    face_id = Column(
        UUID(as_uuid=True), ForeignKey("faces.id", ondelete="SET NULL"), nullable=True
    )

    similarity_score = Column(Float, nullable=True)
    rank = Column(Integer, nullable=True)
    feedback = Column(Text, nullable=True)

    query = relationship("SearchQuery", back_populates="results")
    image = relationship("Image", back_populates="search_results")
    face = relationship("Face", back_populates="search_results")

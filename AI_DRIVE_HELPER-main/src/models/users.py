import uuid

from sqlalchemy import Column, DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from src.db import Base
from src.models.enums import USER_STATUS


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(Text, unique=True, nullable=False, index=True)
    name = Column(Text, nullable=True)
    avatar_url = Column(Text, nullable=True)

    google_id = Column(Text, unique=True, nullable=True)
    drive_access_token = Column(Text, nullable=True)
    drive_refresh_token = Column(Text, nullable=True)
    token_expires_at = Column(DateTime(timezone=True), nullable=True)

    status = Column(USER_STATUS, nullable=False, server_default="active")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    folders = relationship("UserFolder", back_populates="user", cascade="all, delete")
    images = relationship("Image", back_populates="user", cascade="all, delete")
    person_clusters = relationship(
        "PersonCluster", back_populates="user", cascade="all, delete"
    )
    faces = relationship("Face", back_populates="user", cascade="all, delete")
    search_queries = relationship(
        "SearchQuery", back_populates="user", cascade="all, delete"
    )
    ingestion_jobs = relationship(
        "IngestionJob", back_populates="user", cascade="all, delete"
    )
    clustering_jobs = relationship(
        "ClusteringJob", back_populates="user", cascade="all, delete"
    )

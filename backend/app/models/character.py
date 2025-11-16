from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship

from app.db.base import Base


class Character(Base):
    __tablename__ = "characters"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), index=True)

    name = Column(String(255), nullable=False)
    role = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)

    # NEW: reference image path (local or S3 URL)
    ref_image_path = Column(String(1024), nullable=True)

    # NEW: embeddings & palette stored as JSON strings for now
    face_embedding = Column(Text, nullable=True)     # JSON-encoded list[float]
    style_embedding = Column(Text, nullable=True)    # JSON-encoded list[float]
    dominant_colors = Column(Text, nullable=True)    # JSON-encoded list[[r,g,b], ...]

    created_at = Column(DateTime, default=datetime.utcnow)

    project = relationship("Project", back_populates="characters")

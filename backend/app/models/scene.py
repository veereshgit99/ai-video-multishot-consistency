from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship

from app.db.base import Base


class Scene(Base):
    __tablename__ = "scenes"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), index=True)

    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    # NEW: reference image path
    ref_image_path = Column(String(1024), nullable=True)

    # NEW: scene-level embeddings
    scene_embedding = Column(Text, nullable=True)    # JSON-encoded list[float]
    palette = Column(Text, nullable=True)           # JSON-encoded list[[r,g,b], ...]

    created_at = Column(DateTime, default=datetime.utcnow)

    project = relationship("Project", back_populates="scenes")
    shots = relationship("Shot", back_populates="scene")

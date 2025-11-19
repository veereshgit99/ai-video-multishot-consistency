from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship

from app.db.base import Base


class Shot(Base):
    __tablename__ = "shots"

    id = Column(Integer, primary_key=True, index=True)

    project_id = Column(
        Integer,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False
    )

    scene_id = Column(
        Integer,
        ForeignKey("scenes.id", ondelete="SET NULL"),
        nullable=True
    )

    index = Column(Integer, nullable=False)
    description = Column(Text, nullable=True)
    camera_type = Column(String(64), nullable=True)
    motion = Column(String(64), nullable=True)  # static, pan, zoom, etc.
    duration_seconds = Column(Integer, nullable=True)
    continuity_notes = Column(Text, nullable=True)  # LLM-generated continuity hints

    created_at = Column(DateTime, default=datetime.utcnow)

    project = relationship("Project", back_populates="shots")
    scene = relationship("Scene", back_populates="shots")

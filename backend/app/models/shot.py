from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text

from app.db.base import Base


class Shot(Base):
    __tablename__ = "shots"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    scene_id = Column(Integer, ForeignKey("scenes.id", ondelete="SET NULL"), nullable=True)

    index = Column(Integer, nullable=False)  # shot order in project

    description = Column(Text, nullable=True)  # short visual description
    camera_type = Column(String(64), nullable=True)  # "wide", "medium", "close"
    duration_seconds = Column(Integer, nullable=True)

    # later: generation status, model config, etc.

    created_at = Column(DateTime, default=datetime.utcnow)

    # relationships wired via strings in other files to avoid circular imports

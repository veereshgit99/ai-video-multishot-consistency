from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base

import enum


class RenderJobStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    done = "done"
    failed = "failed"


class RenderJob(Base):
    __tablename__ = "render_jobs"

    id = Column(Integer, primary_key=True, index=True)

    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"))
    shot_id = Column(Integer, ForeignKey("shots.id", ondelete="CASCADE"))

    status = Column(Enum(RenderJobStatus), default=RenderJobStatus.pending)

    # This stores prompt, embeddings, seed, ref frames, etc.
    payload = Column(Text, nullable=True)

    # Where the final video will be saved (later)
    output_path = Column(String(1024), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)

    project = relationship("Project")
    shot = relationship("Shot")
    
    updated_at = Column(
    DateTime,
    default=datetime.utcnow,
    onupdate=datetime.utcnow
)

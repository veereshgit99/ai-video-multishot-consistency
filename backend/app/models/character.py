from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship

from app.db.base import Base


class Character(Base):
    __tablename__ = "characters"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), index=True)

    name = Column(String(255), nullable=False)
    role = Column(String(255), nullable=True)  # e.g. "protagonist", "engineer"
    description = Column(Text, nullable=True)

    # later: URLs / keys for reference images, embeddings
    # ref_image_url = Column(String(1024), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    project = relationship("Project", back_populates="characters")

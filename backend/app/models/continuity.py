# backend/app/models/continuity.py

from sqlalchemy import Column, Integer, String, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship
from app.db.base import Base

class ContinuityState(Base):
    __tablename__ = "continuity_states"

    project_id = Column(
        Integer,
        ForeignKey("projects.id", ondelete="CASCADE"),
        primary_key=True
    )
    
    # Session ID from the external chat app (e.g., "chat_123")
    session_id = Column(String(255), index=True, nullable=False, unique=True)

    # TEMPORAL FLOW (The last frame)
    last_frame_path = Column(String(1024), nullable=True)
    
    # NARRATIVE STATE (Path A: The Inventory Problem)
    # Stores semantic facts about the scene, props, etc.
    # e.g. {"location": "rainy alley", "item_held": "glowing sword"}
    narrative_context = Column(JSON, default={})

    # CHARACTER ANCHORS (Path C will reference these)
    # Stores a list of character IDs currently active in this session
    # We will use a separate table for cleaner relationships later, but for now:
    active_character_ids = Column(Text, nullable=True) # Stores JSON list: [1, 5, 12]

    # Relationship to Project (optional, but good practice)
    project = relationship("Project")
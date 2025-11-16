from datetime import datetime
from pydantic import BaseModel
from typing import Optional


class CharacterBase(BaseModel):
    name: str
    role: Optional[str] = None
    description: Optional[str] = None


class CharacterCreate(CharacterBase):
    project_id: int


class Character(CharacterBase):
    id: int
    project_id: int
    created_at: datetime

    # NEW: simple flags
    ref_image_path: Optional[str] = None
    has_embeddings: bool = False

    class Config:
        from_attributes = True

from datetime import datetime
from pydantic import BaseModel
from typing import Optional


class ShotBase(BaseModel):
    index: int
    description: Optional[str] = None
    camera_type: Optional[str] = None
    duration_seconds: Optional[int] = 4  # default small duration


class ShotCreate(ShotBase):
    project_id: int
    scene_id: Optional[int] = None


class Shot(ShotBase):
    id: int
    project_id: int
    scene_id: Optional[int]
    created_at: datetime

    class Config:
        from_attributes = True

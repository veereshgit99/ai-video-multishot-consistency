from datetime import datetime
from pydantic import BaseModel
from typing import Optional


class SceneBase(BaseModel):
    name: str
    description: Optional[str] = None


class SceneCreate(SceneBase):
    project_id: int


class Scene(SceneBase):
    id: int
    project_id: int
    created_at: datetime

    class Config:
        from_attributes = True

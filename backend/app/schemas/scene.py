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

    ref_image_path: Optional[str] = None
    has_embeddings: bool = False

    class Config:
        from_attributes = True

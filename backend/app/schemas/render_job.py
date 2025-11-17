from datetime import datetime
from typing import Optional
from pydantic import BaseModel
from app.models.render_job import RenderJobStatus


class RenderJobBase(BaseModel):
    project_id: int
    shot_id: int


class RenderJob(RenderJobBase):
    id: int
    status: RenderJobStatus
    payload: Optional[str] = None
    output_path: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

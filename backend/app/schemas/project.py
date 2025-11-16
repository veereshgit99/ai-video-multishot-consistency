from datetime import datetime
from pydantic import BaseModel
from typing import Optional, List


class ProjectBase(BaseModel):
    name: str
    description: Optional[str] = None


class ProjectCreate(ProjectBase):
    script: Optional[str] = None


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    script: Optional[str] = None


class Project(ProjectBase):
    id: int
    created_at: datetime
    script: Optional[str] = None

    class Config:
        from_attributes = True

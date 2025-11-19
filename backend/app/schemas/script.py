# app/schemas/script.py

from typing import Optional
from pydantic import BaseModel, Field


class ScriptCreateRequest(BaseModel):
    script_text: str = Field(..., min_length=10)
    language: str = "en"
    max_scenes: int = 10
    max_shots_per_scene: int = 12
    target_shot_duration_seconds: int = 4
    overwrite_existing: bool = True


class ScriptCreateResponse(BaseModel):
    project_id: int
    scenes_created: int
    shots_created: int

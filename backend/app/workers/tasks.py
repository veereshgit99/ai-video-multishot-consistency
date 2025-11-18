# app/workers/tasks.py

import os
from typing import Dict

from app.db.session import SessionLocal
from app import models
from app.services.video.google_flow import GoogleFlowVideoService
from app.services.prompt_builder import PromptBuilder
from app.services.continuity.continuity_engine import (
    ContinuityEngine,
    ContinuityState,
)

from rq import get_current_job


video_service = GoogleFlowVideoService()
prompt_builder = PromptBuilder()
continuity_engine = ContinuityEngine()

# In-memory continuity, keyed by project_id
# For a single worker this is fine; for multi-worker you’d persist in DB.
_project_continuity: Dict[int, ContinuityState] = {}


def _get_or_create_continuity_state(project_id: int) -> ContinuityState:
    state = _project_continuity.get(project_id)
    if state is None:
        state = ContinuityState()
        _project_continuity[project_id] = state
    return state


def render_shot_task(render_job_id: int) -> str:
    """
    Worker entry point: render a single shot using Veo 3.1 Fast
    with continuity-aware prompting.
    """

    db = SessionLocal()

    job = db.query(models.RenderJob).filter(models.RenderJob.id == render_job_id).first()
    if not job:
        return f"render_job_id={render_job_id} not found"

    # Mark as running
    job.status = models.RenderJobStatus.running
    db.commit()

    shot = db.query(models.Shot).filter(models.Shot.id == job.shot_id).first()
    if not shot:
        job.status = models.RenderJobStatus.failed
        job.payload = "Shot not found"
        db.commit()
        return "shot not found"

    project = db.query(models.Project).filter(models.Project.id == job.project_id).first()
    if not project:
        job.status = models.RenderJobStatus.failed
        job.payload = "Project not found"
        db.commit()
        return "project not found"

    # All characters for project (we may later filter by scene)
    characters = (
        db.query(models.Character)
        .filter(models.Character.project_id == project.id)
        .all()
    )

    # --- 1) continuity state for this project ---
    c_state = _get_or_create_continuity_state(project.id)

    # --- 2) base shot prompt (scene + shot description) ---
    base_prompt = prompt_builder.build_shot_prompt(db, shot)

    # --- 3) continuity-aware final prompt ---
    final_prompt = continuity_engine.build_continuity_prompt(
        base_prompt=base_prompt,
        shot=shot,
        characters=characters,
        state=c_state,
    )

    # Decide number of frames: if you have a duration_seconds field, use it; else default
    duration_seconds = getattr(shot, "duration_seconds", 6) or 6
    num_frames = duration_seconds * 30  # ~30 fps

    try:
        # --- 4) Call Veo to generate the actual video bytes ---
        video_bytes = video_service.generate_video(final_prompt, num_frames=num_frames)

    except Exception as e:
        job.status = models.RenderJobStatus.failed
        job.payload = str(e)
        db.commit()
        return f"failed: {e}"

    # --- 5) Save output video ---
    out_dir = "media/generated"
    os.makedirs(out_dir, exist_ok=True)

    output_path = os.path.join(out_dir, f"shot_{shot.id}.mp4")
    with open(output_path, "wb") as f:
        f.write(video_bytes)

    # --- 6) Update continuity state AFTER shot ---
    new_state = continuity_engine.update_state_after_shot(
        shot=shot,
        characters=characters,
        state=c_state,
    )
    _project_continuity[project.id] = new_state

    # --- 7) Mark job as done in DB ---
    job.status = models.RenderJobStatus.done
    job.output_path = output_path
    db.commit()

    return f"rendered shot {shot.id} (project {project.id}) with continuity"

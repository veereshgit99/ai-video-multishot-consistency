# app/workers/tasks.py

import os
import base64
import subprocess
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
# For a single worker this is fine; for multi-worker you'd persist in DB.
_project_continuity: Dict[int, ContinuityState] = {}


def extract_frame(video_path: str, output_path: str):
    """Extract last frame from video using ffmpeg."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    cmd = [
        "ffmpeg", "-y",
        "-sseof", "-0.1",  # Seek to 0.1 seconds before end
        "-i", video_path,
        "-frames:v", "1",
        output_path
    ]
    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def to_ref(path: str, weight: float = 1.0) -> dict:
    """Convert image path to Veo reference image format."""
    if not os.path.exists(path):
        return None
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    
    # Determine mime type from file extension
    mime_type = "image/jpeg"
    if path.lower().endswith(".png"):
        mime_type = "image/png"
    elif path.lower().endswith((".jpg", ".jpeg")):
        mime_type = "image/jpeg"
    
    return {
        "referenceType": "asset",
        "image": {
            "bytesBase64Encoded": b64,
            "mimeType": mime_type
        },
        "weight": weight
    }


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

    # --- 4) Build reference images for visual conditioning ---
    reference_images = []

    print(f"\n{'='*60}")
    print(f"DEBUG: Shot {shot.id}, Project {project.id}")
    print(f"DEBUG: Continuity state - shot_index: {c_state.shot_index}")
    print(f"DEBUG: Number of characters: {len(characters)}")

    # 4a) Character reference images
    for ch in characters:
        print(f"DEBUG: Character {ch.id} - has image_path: {hasattr(ch, 'image_path')}")
        if hasattr(ch, 'image_path') and ch.image_path:
            print(f"DEBUG: Character {ch.id} image_path: {ch.image_path}")
            print(f"DEBUG: Image exists: {os.path.exists(ch.image_path)}")
            ref = to_ref(ch.image_path, weight=1.0)
            if ref:
                print(f"DEBUG: Added character reference image (weight=1.0)")
                reference_images.append(ref)
            else:
                print(f"DEBUG: Character image path does not exist: {ch.image_path}")

    # 4b) Last frame from previous shot
    print(f"DEBUG: Last frame path: {c_state.last_frame_path}")
    if c_state.last_frame_path:
        print(f"DEBUG: Last frame exists: {os.path.exists(c_state.last_frame_path)}")
    
    if c_state.last_frame_path and os.path.exists(c_state.last_frame_path):
        ref = to_ref(c_state.last_frame_path, weight=0.8)
        if ref:
            print(f"DEBUG: Added previous shot last frame reference (weight=0.8)")
            reference_images.append(ref)

    # 4c) Generate deterministic seed per project/shot
    seed = c_state.shot_index + project.id * 1000

    print(f"DEBUG: Total reference images: {len(reference_images)}")
    print(f"DEBUG: Seed: {seed}")
    print(f"DEBUG: Num frames: {num_frames}")
    
    if reference_images:
        for i, ref_img in enumerate(reference_images):
            print(f"DEBUG: Reference image {i+1}:")
            print(f"  - Type: {ref_img.get('referenceType')}")
            print(f"  - Weight: {ref_img.get('weight')}")
            print(f"  - Mime: {ref_img.get('image', {}).get('mimeType')}")
            print(f"  - Base64 length: {len(ref_img.get('image', {}).get('bytesBase64Encoded', ''))}")
    print(f"{'='*60}\n")

    try:
        # --- 5) Call Veo with reference images and seed ---
        video_bytes = video_service.generate_video(
            final_prompt,
            num_frames=num_frames,
            reference_images=reference_images if reference_images else None,
            seed=seed
        )

    except Exception as e:
        job.status = models.RenderJobStatus.failed
        job.payload = str(e)
        db.commit()
        return f"failed: {e}"

    # --- 6) Save output video ---
    out_dir = "media/generated"
    os.makedirs(out_dir, exist_ok=True)

    output_path = os.path.join(out_dir, f"shot_{shot.id}.mp4")
    with open(output_path, "wb") as f:
        f.write(video_bytes)

    # --- 7) Extract last frame for next shot's reference ---
    continuity_dir = "media/continuity"
    os.makedirs(continuity_dir, exist_ok=True)
    last_frame_path = os.path.join(continuity_dir, f"shot_{shot.id}_last_frame.jpg")
    
    try:
        extract_frame(output_path, last_frame_path)
        c_state.last_frame_path = last_frame_path
    except Exception as e:
        # Non-critical - continue even if frame extraction fails
        print(f"Warning: Failed to extract frame: {e}")

    # --- 8) Update continuity state AFTER shot ---
    new_state = continuity_engine.update_state_after_shot(
        shot=shot,
        characters=characters,
        state=c_state,
    )
    _project_continuity[project.id] = new_state

    # --- 9) Mark job as done in DB ---
    job.status = models.RenderJobStatus.done
    job.output_path = output_path
    db.commit()

    return f"rendered shot {shot.id} (project {project.id}) with visual continuity"

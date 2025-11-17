import os
import time
from app.db.session import SessionLocal
from app import models
from app.services.video.google_flow import GoogleFlowVideoService
from app.services.prompt_builder import PromptBuilder


video_service = GoogleFlowVideoService()


def render_shot_task(render_job_id: int):
    db = SessionLocal()

    job = db.query(models.RenderJob).filter(models.RenderJob.id == render_job_id).first()
    if not job:
        return "job not found"

    # Mark running
    job.status = models.RenderJobStatus.running
    db.commit()

    shot = db.query(models.Shot).filter(models.Shot.id == job.shot_id).first()
    if not shot:
        job.status = models.RenderJobStatus.failed
        db.commit()
        return "shot not found"

    # Build prompt
    prompt = PromptBuilder.build_shot_prompt(db, shot)

    # Run model
    try:
        video_bytes = video_service.generate_video(prompt, num_frames=shot.duration_seconds * 15)
    except Exception as e:
        job.status = models.RenderJobStatus.failed
        job.payload = str(e)
        db.commit()
        return f"failed: {e}"

    # Save output
    out_dir = "media/generated"
    os.makedirs(out_dir, exist_ok=True)

    output_path = os.path.join(out_dir, f"shot_{shot.id}.mp4")
    with open(output_path, "wb") as f:
        f.write(video_bytes)

    # Update job
    job.status = models.RenderJobStatus.done
    job.output_path = output_path
    db.commit()

    return f"rendered shot {shot.id}"

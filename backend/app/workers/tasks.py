import json
import time
from app.db.session import SessionLocal
from app import models


def render_shot_task(render_job_id: int):
    """
    Dummy worker. Later: call video model here.
    """

    db = SessionLocal()

    job = db.query(models.RenderJob).filter(models.RenderJob.id == render_job_id).first()
    if not job:
        return "job not found"

    # Mark running
    job.status = models.RenderJobStatus.running
    db.add(job)
    db.commit()

    # Fake processing
    time.sleep(2)  # simulate video generation

    # Write dummy output
    job.status = models.RenderJobStatus.done
    job.output_path = f"media/generated/shot_{job.shot_id}.mp4"
    db.add(job)
    db.commit()

    return f"rendered shot {job.shot_id}"

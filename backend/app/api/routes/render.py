from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from rq.job import Job

from app.api.dependencies import get_db
from app import models, schemas
from app.core.queue import render_queue
from app.workers.tasks import render_shot_task   # we will define next


router = APIRouter(prefix="/render", tags=["render"])


@router.post("/project/{project_id}")
def enqueue_project_render(project_id: int, db: Session = Depends(get_db)):

    project = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    shots = (
        db.query(models.Shot)
        .filter(models.Shot.project_id == project_id)
        .order_by(models.Shot.index.asc())
        .all()
    )

    if not shots:
        raise HTTPException(status_code=400, detail="No shots to render for this project")

    job_ids = []

    for shot in shots:
        # Store initial job record
        rj = models.RenderJob(
            project_id=project_id,
            shot_id=shot.id,
            status=models.RenderJobStatus.pending,
            payload="{}",  # placeholder
        )
        db.add(rj)
        db.commit()
        db.refresh(rj)

        # Enqueue worker job
        job = render_queue.enqueue(render_shot_task, rj.id)
        job_ids.append({"render_job_id": rj.id, "rq_job_id": job.get_id()})

    return {
        "status": "queued",
        "jobs": job_ids,
        "total_shots": len(shots),
    }

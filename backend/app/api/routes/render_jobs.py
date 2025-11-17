from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app import models, schemas

router = APIRouter(prefix="/render_jobs", tags=["render_jobs"])


# 1. List jobs for a project
@router.get("/project/{project_id}", response_model=list[schemas.RenderJob])
def list_jobs_for_project(project_id: int, db: Session = Depends(get_db)):
    jobs = (
        db.query(models.RenderJob)
        .filter(models.RenderJob.project_id == project_id)
        .order_by(models.RenderJob.created_at)
        .all()
    )
    return jobs


# 2. List jobs for a single shot
@router.get("/shot/{shot_id}", response_model=list[schemas.RenderJob])
def list_jobs_for_shot(shot_id: int, db: Session = Depends(get_db)):
    jobs = (
        db.query(models.RenderJob)
        .filter(models.RenderJob.shot_id == shot_id)
        .order_by(models.RenderJob.created_at)
        .all()
    )
    return jobs


# 3. Get a single render job
@router.get("/{render_job_id}", response_model=schemas.RenderJob)
def get_render_job(render_job_id: int, db: Session = Depends(get_db)):
    job = (
        db.query(models.RenderJob)
        .filter(models.RenderJob.id == render_job_id)
        .first()
    )
    if not job:
        raise HTTPException(status_code=404, detail="Render job not found")

    return job

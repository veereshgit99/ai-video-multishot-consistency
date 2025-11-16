from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app import models, schemas

router = APIRouter(prefix="/shots", tags=["shots"])


@router.get("/project/{project_id}", response_model=List[schemas.Shot])
def list_shots(project_id: int, db: Session = Depends(get_db)):
    project = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    shots = (
        db.query(models.Shot)
        .filter(models.Shot.project_id == project_id)
        .order_by(models.Shot.index.asc())
        .all()
    )

    return shots

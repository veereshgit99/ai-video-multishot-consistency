from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app import models, schemas

router = APIRouter(prefix="/scenes", tags=["scenes"])


@router.post("/", response_model=schemas.Scene, status_code=status.HTTP_201_CREATED)
def create_scene(scene_in: schemas.SceneCreate, db: Session = Depends(get_db)):
    project = (
        db.query(models.Project)
        .filter(models.Project.id == scene_in.project_id)
        .first()
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    scene = models.Scene(
        project_id=scene_in.project_id,
        name=scene_in.name,
        description=scene_in.description,
    )
    db.add(scene)
    db.commit()
    db.refresh(scene)
    return scene


@router.get("/project/{project_id}", response_model=List[schemas.Scene])
def list_scenes_for_project(project_id: int, db: Session = Depends(get_db)):
    return (
        db.query(models.Scene)
        .filter(models.Scene.project_id == project_id)
        .order_by(models.Scene.created_at)
        .all()
    )

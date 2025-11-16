from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app import models, schemas
from app.core.files import save_scene_image
from app.services.embedding import extract_scene_dna, to_json_str

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
    return _to_schema_scene(scene)


@router.get("/project/{project_id}", response_model=List[schemas.Scene])
def list_scenes_for_project(project_id: int, db: Session = Depends(get_db)):
    scenes = (
        db.query(models.Scene)
        .filter(models.Scene.project_id == project_id)
        .order_by(models.Scene.created_at)
        .all()
    )
    return [_to_schema_scene(s) for s in scenes]


@router.post("/{scene_id}/image", response_model=schemas.Scene)
def upload_scene_image(
    scene_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    scene = (
        db.query(models.Scene)
        .filter(models.Scene.id == scene_id)
        .first()
    )
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")

    path = save_scene_image(scene_id, file)
    scene.ref_image_path = path

    dna = extract_scene_dna(path)
    scene.scene_embedding = to_json_str(dna["scene_embedding"])
    scene.palette = to_json_str(dna["palette"])

    db.add(scene)
    db.commit()
    db.refresh(scene)

    return _to_schema_scene(scene)


def _to_schema_scene(s: models.Scene) -> schemas.Scene:
    has_embeddings = bool(s.scene_embedding)
    return schemas.Scene(
        id=s.id,
        project_id=s.project_id,
        name=s.name,
        description=s.description,
        created_at=s.created_at,
        ref_image_path=s.ref_image_path,
        has_embeddings=has_embeddings,
    )

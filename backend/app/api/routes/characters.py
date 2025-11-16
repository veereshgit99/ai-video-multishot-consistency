from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app import models, schemas
from app.core.files import save_character_image
from app.services.embedding import extract_character_dna, to_json_str

router = APIRouter(prefix="/characters", tags=["characters"])


@router.post("/", response_model=schemas.Character, status_code=status.HTTP_201_CREATED)
def create_character(
    character_in: schemas.CharacterCreate, db: Session = Depends(get_db)
):
    project = (
        db.query(models.Project)
        .filter(models.Project.id == character_in.project_id)
        .first()
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    character = models.Character(
        project_id=character_in.project_id,
        name=character_in.name,
        role=character_in.role,
        description=character_in.description,
    )
    db.add(character)
    db.commit()
    db.refresh(character)

    return _to_schema_character(character)


@router.get("/project/{project_id}", response_model=List[schemas.Character])
def list_characters_for_project(
    project_id: int, db: Session = Depends(get_db)
):
    characters = (
        db.query(models.Character)
        .filter(models.Character.project_id == project_id)
        .order_by(models.Character.created_at)
        .all()
    )
    return [_to_schema_character(c) for c in characters]


@router.post("/{character_id}/image", response_model=schemas.Character)
def upload_character_image(
    character_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    character = (
        db.query(models.Character)
        .filter(models.Character.id == character_id)
        .first()
    )
    if not character:
        raise HTTPException(status_code=404, detail="Character not found")

    # Save file
    path = save_character_image(character_id, file)
    character.ref_image_path = path

    # Extract embeddings
    dna = extract_character_dna(path)
    character.face_embedding = to_json_str(dna["face_embedding"])
    character.style_embedding = to_json_str(dna["style_embedding"])
    character.dominant_colors = to_json_str(dna["dominant_colors"])

    db.add(character)
    db.commit()
    db.refresh(character)

    return _to_schema_character(character)


def _to_schema_character(c: models.Character) -> schemas.Character:
    # derive flag
    has_embeddings = bool(c.face_embedding and c.style_embedding)
    return schemas.Character(
        id=c.id,
        project_id=c.project_id,
        name=c.name,
        role=c.role,
        description=c.description,
        created_at=c.created_at,
        ref_image_path=c.ref_image_path,
        has_embeddings=has_embeddings,
    )

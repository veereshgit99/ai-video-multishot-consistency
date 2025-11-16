from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app import models, schemas

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
    return character


@router.get("/project/{project_id}", response_model=List[schemas.Character])
def list_characters_for_project(
    project_id: int, db: Session = Depends(get_db)
):
    return (
        db.query(models.Character)
        .filter(models.Character.project_id == project_id)
        .order_by(models.Character.created_at)
        .all()
    )

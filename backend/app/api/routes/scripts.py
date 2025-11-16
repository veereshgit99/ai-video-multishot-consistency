from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app import models, schemas

router = APIRouter(prefix="/scripts", tags=["scripts"])


@router.post("/project/{project_id}", status_code=status.HTTP_200_OK)
def submit_script(project_id: int, script: str, db: Session = Depends(get_db)):
    project = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Store script
    project.script = script
    db.add(project)
    db.commit()

    # TEMP: generate dummy shots until LLM integration
    # (Later we call an LLM here)
    dummy_shots = [
        {
            "index": 1,
            "description": "Establishing shot of the environment.",
            "camera_type": "wide",
            "duration_seconds": 4,
            "scene_id": None,
        },
        {
            "index": 2,
            "description": "Medium shot focusing on the main character.",
            "camera_type": "medium",
            "duration_seconds": 4,
            "scene_id": None,
        }
    ]

    # remove old shots
    db.query(models.Shot).filter(models.Shot.project_id == project_id).delete()

    # insert new shots
    created_shots = []
    for s in dummy_shots:
        shot = models.Shot(
            project_id=project_id,
            index=s["index"],
            description=s["description"],
            camera_type=s["camera_type"],
            duration_seconds=s["duration_seconds"],
            scene_id=s["scene_id"],
        )
        db.add(shot)
        created_shots.append(shot)

    db.commit()

    return {"status": "ok", "shots_created": len(created_shots)}

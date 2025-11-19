from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app import models
from app.schemas.script import ScriptCreateRequest, ScriptCreateResponse
from app.services.script_analysis import ScriptAnalysisService

router = APIRouter(prefix="/scripts", tags=["scripts"])

script_analysis_service = ScriptAnalysisService()


@router.post("/project/{project_id}", response_model=ScriptCreateResponse)
def submit_script(
    project_id: int,
    payload: ScriptCreateRequest,
    db: Session = Depends(get_db),
):
    # 1. Validate project
    project = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project {project_id} not found",
        )

    # 2. Store script on project
    project.script = payload.script_text
    db.add(project)
    db.commit()

    # 3. Optionally wipe existing scenes & shots for a clean re-generation
    if payload.overwrite_existing:
        (
            db.query(models.Shot)
            .filter(models.Shot.project_id == project_id)
            .delete(synchronize_session=False)
        )
        (
            db.query(models.Scene)
            .filter(models.Scene.project_id == project_id)
            .delete(synchronize_session=False)
        )
        db.commit()

    # 4. Load characters for context
    characters = (
        db.query(models.Character)
        .filter(models.Character.project_id == project_id)
        .all()
    )

    # 5. Analyze script → scenes + shots
    structure = script_analysis_service.analyze_script(
        script_text=payload.script_text,
        characters=characters,
        language=payload.language,
        max_scenes=payload.max_scenes,
        max_shots_per_scene=payload.max_shots_per_scene,
        target_shot_duration_seconds=payload.target_shot_duration_seconds,
    )

    # 6. Persist scenes + shots
    scenes_created = 0
    shots_created = 0

    for scene_spec in structure.scenes:
        scene = models.Scene(
            project_id=project_id,
            index=scene_spec.index,
            name=scene_spec.title,  # Using title as name
            title=scene_spec.title,
            description=scene_spec.description,
        )
        db.add(scene)
        db.flush()  # get scene.id

        scenes_created += 1

        for shot_spec in scene_spec.shots:
            shot = models.Shot(
                project_id=project_id,
                scene_id=scene.id,
                index=shot_spec.index,
                description=shot_spec.description,
                camera_type=shot_spec.camera_type,
                motion=shot_spec.motion,
                duration_seconds=shot_spec.duration_seconds,
                continuity_notes=shot_spec.continuity_notes,
            )
            db.add(shot)
            shots_created += 1

    db.commit()

    return ScriptCreateResponse(
        project_id=project_id,
        scenes_created=scenes_created,
        shots_created=shots_created,
    )

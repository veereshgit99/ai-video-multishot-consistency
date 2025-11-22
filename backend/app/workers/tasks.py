# app/workers/tasks.py

import os
import base64
import subprocess
import tempfile

from app.db.session import SessionLocal
from app import models
from app.services.video.google_flow import GoogleFlowVideoService
from app.services.prompt_builder import PromptBuilder
from app.services.continuity.continuity_engine import ContinuityEngine
from app.services.embedding import extract_character_dna, to_json_str
from app.services.s3_storage import download_from_uri, upload_video, upload_continuity_frame

from rq import get_current_job


video_service = GoogleFlowVideoService()
prompt_builder = PromptBuilder()
continuity_engine = ContinuityEngine()


def extract_dna_task(character_id: int):
    """
    RQ worker task to calculate and save character embeddings asynchronously.
    NOW SUPPORTS S3 URIS!
    This runs in the background to avoid blocking the user.
    """
    db = SessionLocal()
    
    try:
        char = db.query(models.Character).filter_by(id=character_id).first()
        if not char or not char.ref_image_path:
            return f"Character {character_id} not found or image path missing."

        # Check if path is S3 URI or local file
        if char.ref_image_path.startswith("s3://"):
            # Download from S3 to temp file for DNA extraction
            print(f"[DNA] Downloading from S3: {char.ref_image_path}")
            image_bytes = download_from_uri(char.ref_image_path)
            
            # Write to temp file for CLIP/FaceNet processing
            with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
                tmp.write(image_bytes)
                temp_path = tmp.name
            
            try:
                # Extract DNA from temp file
                dna = extract_character_dna(temp_path)
            finally:
                # Clean up temp file
                try:
                    os.unlink(temp_path)
                except:
                    pass
        else:
            # Legacy local file support
            dna = extract_character_dna(char.ref_image_path)
        
        # Save the results back to the database
        char.face_embedding = to_json_str(dna["face_embedding"])
        char.style_embedding = to_json_str(dna["style_embedding"])
        char.dominant_colors = to_json_str(dna["dominant_colors"])
        
        db.commit()
        print(f"[DNA] Completed extraction for Character {character_id} ({char.name})")
        return f"DNA extracted and saved for Character {character_id}."
        
    except Exception as e:
        db.rollback()
        print(f"[DNA ERROR] Failed for Character {character_id}: {e}")
        return f"Error extracting DNA for {character_id}: {e}"
    finally:
        db.close()


def extract_frame(video_path: str, output_path: str):
    """Extract last frame from video using ffmpeg."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    cmd = [
        "ffmpeg", "-y",
        "-sseof", "-0.1",  # Seek to 0.1 seconds before end
        "-i", video_path,
        "-frames:v", "1",
        output_path
    ]
    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def to_ref(path: str, weight: float = 1.0) -> dict:
    """Convert image path to Veo reference image format."""
    if not os.path.exists(path):
        return None
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    
    # Determine mime type from file extension
    mime_type = "image/jpeg"
    if path.lower().endswith(".png"):
        mime_type = "image/png"
    elif path.lower().endswith((".jpg", ".jpeg")):
        mime_type = "image/jpeg"
    
    return {
        "referenceType": "asset",
        "image": {
            "bytesBase64Encoded": b64,
            "mimeType": mime_type
        },
        "weight": weight
    }


# Removed: _get_or_create_continuity_state - now handled by ContinuityEngine


def render_shot_task(render_job_id: int) -> str:
    """
    Worker entry point: render a single shot using Veo 3.1 Fast
    with continuity-aware prompting.
    """

    db = SessionLocal()

    job = db.query(models.RenderJob).filter(models.RenderJob.id == render_job_id).first()
    if not job:
        return f"render_job_id={render_job_id} not found"

    # Mark as running
    job.status = models.RenderJobStatus.running
    db.commit()

    shot = db.query(models.Shot).filter(models.Shot.id == job.shot_id).first()
    if not shot:
        job.status = models.RenderJobStatus.failed
        job.payload = "Shot not found"
        db.commit()
        return "shot not found"

    project = db.query(models.Project).filter(models.Project.id == job.project_id).first()
    if not project:
        job.status = models.RenderJobStatus.failed
        job.payload = "Project not found"
        db.commit()
        return "project not found"

    # --- 1) Build base prompt (scene + shot description) ---
    base_prompt = prompt_builder.build_shot_prompt(db, shot)

    print(f"\n{'='*60}")
    print(f"DEBUG: Shot {shot.id}, Project {project.id}")
    print(f"DEBUG: Base prompt: {base_prompt[:100]}...")
    print(f"{'='*60}\n")

    # Decide number of frames: if you have a duration_seconds field, use it; else default
    duration_seconds = getattr(shot, "duration_seconds", 6) or 6
    num_frames = duration_seconds * 30  # ~30 fps

    try:
        # --- 2) Use ContinuityEngine to generate with Anchor + Flow ---
        # The engine handles: state lookup, reference images, prompt enhancement, and Veo call
        video_bytes = continuity_engine.generate_segment(
            db=db,
            project_id=project.id,
            prompt=base_prompt
        )

    except Exception as e:
        job.status = models.RenderJobStatus.failed
        job.payload = str(e)
        db.commit()
        return f"failed: {e}"

    # --- 3) Save output video to S3 ---
    session_id = f"job_{render_job_id}"
    output_s3_uri = upload_video(video_bytes, session_id, shot_number=shot.id)
    print(f"[S3] Video uploaded: {output_s3_uri}")

    # --- 4) Extract last frame and upload to S3 for next shot's reference ---
    try:
        # Extract frame bytes from video
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp_video:
            tmp_video.write(video_bytes)
            tmp_video_path = tmp_video.name
        
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp_frame:
            tmp_frame_path = tmp_frame.name
        
        try:
            cmd = [
                "ffmpeg", "-y",
                "-sseof", "-0.1",
                "-i", tmp_video_path,
                "-frames:v", "1",
                tmp_frame_path
            ]
            subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
            
            with open(tmp_frame_path, "rb") as f:
                frame_bytes = f.read()
            
            # Upload continuity frame to S3
            continuity_s3_uri = upload_continuity_frame(frame_bytes, session_id)
            
            # Update continuity state with S3 URI
            c_state = continuity_engine.get_or_create_state(db, project.id)
            c_state.last_frame_path = continuity_s3_uri
            db.commit()
            print(f"[S3] Updated continuity state: {continuity_s3_uri}")
        finally:
            try:
                os.unlink(tmp_video_path)
                os.unlink(tmp_frame_path)
            except:
                pass
    except Exception as e:
        # Non-critical - continue even if frame extraction fails
        print(f"Warning: Failed to extract/upload frame: {e}")

    # --- 5) Mark job as done in DB ---
    job.status = models.RenderJobStatus.done
    job.output_path = output_s3_uri  # Store S3 URI instead of local path
    db.commit()

    return f"rendered shot {shot.id} (project {project.id}) with visual continuity - S3: {output_s3_uri}"

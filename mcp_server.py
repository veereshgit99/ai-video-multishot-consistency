# mcp_server.py
import os
import sys
import json
import base64
import subprocess
import uuid
from pathlib import Path
from typing import List
from datetime import datetime

# Add backend directory to Python path
backend_dir = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_dir))

# Generate unique session ID for this MCP server instance (this Claude chat)
INSTANCE_SESSION_ID = f"chat_{uuid.uuid4().hex[:12]}"

# Change working directory to backend so database path is correct
os.chdir(str(backend_dir))

# CRITICAL: Load environment variables AFTER changing to backend directory
from dotenv import load_dotenv
load_dotenv()  # Load .env file from backend directory

from mcp.server.fastmcp import FastMCP
from app.db.session import SessionLocal, engine
from app.db.base import Base
from app import models
from app.services.continuity.continuity_engine import ContinuityEngine
from app.services.embedding import extract_character_dna, to_json_str
from app.services.s3_storage import (
    upload_character_image, upload_video, upload_continuity_frame,
    download_from_uri, get_public_url, upload_bytes
)
from app.core.queue import render_queue
from app.workers.tasks import extract_dna_task

# Ensure all tables are created
Base.metadata.create_all(bind=engine)

# Initialize the MCP Server with Tool-Calling Enforcement
mcp = FastMCP(
    "VideoMemoryLayer",
    instructions=f"""
    YOU ARE AN API ORCHESTRATOR FOR VIDEO GENERATION - NOT A CONVERSATIONAL ASSISTANT.
    
    *** CRITICAL SESSION MANAGEMENT RULE ***
    This MCP server instance has a unique session: "{INSTANCE_SESSION_ID}"
    ALL video generation requests in THIS CHAT must use session_id="{INSTANCE_SESSION_ID}"
    
    FOR EVERY generate_video_segment CALL:
    - YOU MUST pass session_id="{INSTANCE_SESSION_ID}" 
    - DO NOT generate new session IDs
    - DO NOT use generic names like "chat_dog_video" or "chat_cafe_scene"
    - REUSE THE SAME SESSION ID: "{INSTANCE_SESSION_ID}"
    
    *** CRITICAL TOOL USAGE ***
    PRODUCTION WORKFLOW (S3-Based - No Base64!):
    
    1. Image Upload:
       - User uploads via POST /api/v1/upload → Returns s3_uri
    
    2. FIRST SHOT: Call generate_video_segment(prompt=..., session_id="{INSTANCE_SESSION_ID}", s3_uri=..., characters_in_shot=...)
       → Tool downloads from S3 and injects into Veo
    
    3. CONTINUATION: Call generate_video_segment(prompt=..., session_id="{INSTANCE_SESSION_ID}", characters_in_shot=...)
       → Uses stored character DNA + flow continuity
    
    DO NOT respond conversationally without executing the tools.
    DO NOT hallucinate responses like "video generated" or "character registered".
    DO NOT claim instant completion - video generation takes 2-3 minutes.
    ALWAYS wait for tool response before confirming to user.
    
    Your role is to translate user intent into precise tool calls and report actual results.
    """
)
continuity_engine = ContinuityEngine()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- Utility Functions for Production-Grade Character Management ---


def _extract_last_frame_bytes(video_bytes: bytes) -> bytes:
    """Extract last frame from video bytes using ffmpeg, return as JPEG bytes."""
    import tempfile
    
    # Create temp files for input video and output frame
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp_video:
        tmp_video.write(video_bytes)
        tmp_video_path = tmp_video.name
    
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp_frame:
        tmp_frame_path = tmp_frame.name
    
    try:
        cmd = [
            "ffmpeg", "-y",
            "-sseof", "-0.1",  # Seek to 0.1 seconds before end
            "-i", tmp_video_path,
            "-frames:v", "1",
            tmp_frame_path
        ]
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        
        # Read the extracted frame
        with open(tmp_frame_path, "rb") as f:
            frame_bytes = f.read()
        
        return frame_bytes
    finally:
        # Cleanup temp files
        try:
            os.unlink(tmp_video_path)
            os.unlink(tmp_frame_path)
        except:
            pass


def _handle_character_logic(db, project_id: int, name: str, desc: str, is_new: bool, video_path: str):
    """
    Production-grade logic to handle character identity.
    The LLM tells us who the character is - we just execute.
    
    This is the "YC Grade" approach:
    - No guessing or heuristics
    - Explicit intent from the LLM
    - Zero-shot character creation
    - Automatic DNA anchoring on first appearance
    """
    if not name:
        return None  # No character specified, pure scene/flow generation
    
    # 1. Check if character exists
    char = db.query(models.Character).filter(
        models.Character.project_id == project_id,
        models.Character.name == name
    ).first()
    
    # 2. Logic Branch: Create vs. Reuse
    if not char:
        # Case A: New Character (The "Anchor" Creation)
        # We use the FIRST frame of this new video as their permanent DNA.
        
        # Note: video_path is now an S3 URI
        anchor_s3_uri = None
        
        # Extract anchor frame and upload to S3
        try:
            # Download video from S3
            video_bytes = download_from_uri(video_path)
            # Extract frame as bytes
            frame_bytes = _extract_last_frame_bytes(video_bytes)
            # Upload to S3
            session_id = video_path.split("/")[3] if "/" in video_path else "unknown"
            anchor_s3_uri = upload_character_image(0, frame_bytes, session_id=session_id)
            print(f"[S3] Uploaded anchor frame: {anchor_s3_uri}")
        except Exception as e:
            print(f"Warning: Failed to extract/upload anchor frame: {e}")
        
        # Note: DNA extraction now handled by background worker
        char = models.Character(
            project_id=project_id,
            name=name,
            description=desc or f"{name} - auto-created from video",
            ref_image_path=anchor_s3_uri,
            face_embedding=None,  # Background worker fills this
            style_embedding=None,
            dominant_colors=None,
        )
        db.add(char)
        db.flush()
        print(f"[+] Created new Anchor: {name} with S3 URI: {anchor_s3_uri}")
    
    else:
        # Case B: Existing Character
        # We don't overwrite their DNA. We just confirm they are active.
        print(f"[~] Reusing existing Anchor: {name}")
    
    return char

@mcp.tool()
def generate_video_segment(
    prompt: str,
    session_id: str = INSTANCE_SESSION_ID,
    s3_uri: str = None,
    characters_in_shot: list = None
):
    """
    **CRITICAL: YOU MUST CALL THIS TOOL - DO NOT SIMULATE OR DESCRIBE THE ACTION.**
    
    Generates a video segment with intelligent multi-character tracking.
    PRODUCTION WORKFLOW: S3-based uploads (NO BASE64!)
    
    MANDATORY EXECUTION RULE:
    - When user uploads image + requests video, YOU MUST INVOKE THIS TOOL with s3_uri
    - DO NOT respond conversationally like "I've generated the video" or "video created in 2 seconds"
    - DO NOT hallucinate success messages without executing the tool
    - EXECUTE the tool call and wait for the actual response
    - Video generation takes 2-3 MINUTES (not seconds) - be honest with the user
    - Only after receiving the tool's response with file path should you confirm success
    
    PRODUCTION ARCHITECTURE (S3-First):
    
    Step 1: Upload Image to S3
    - User uploads via POST /api/v1/upload?session_id={session_id}
    - Backend returns s3_uri: s3://bucket/uploads/{session_id}/{uuid}.jpg
    - OR use presigned URL for client-direct upload
    
    Step 2: Generate First Shot
    - Call this tool with s3_uri parameter
    - Tool downloads from S3 internally (base64 conversion happens server-side)
    - Injects into Veo with weight 1.0
    
    Step 3: Generate Continuations
    - Call this tool WITHOUT s3_uri (uses stored character DNA)
    - Automatic multi-anchor injection (0.8 weight)
    - Flow continuity from last frame (0.5 weight)
    
    This tool handles:
    - First-shot: Raw image injection from S3 (no pre-registration needed)
    - Multi-character zero-shot creation (first mention = auto-anchor from video output)
    - Multi-shot identity consistency (character DNA reuse with 0.8 weight)
    - Flow continuity (last frame → next shot with 0.5 weight)
    - Complete shot history logging
    
    Args:
        prompt: The visual description for the video model (e.g. "Woman doing yoga in a park").
        session_id: Session ID for this conversation. Defaults to unique instance ID (same for all videos in this chat).
                   CRITICAL: Claude MUST pass the same session_id for all videos in this conversation.
        s3_uri: [FIRST SHOT ONLY] Pre-uploaded S3 URI from POST /upload endpoint.
                Format: s3://bucket-name/uploads/{session_id}/{uuid}.jpg
                Leave empty for continuation shots (uses stored DNA).
        characters_in_shot: A list of characters present in this shot, e.g.,
                           [{"name": "Sarah", "desc": "Woman in yoga outfit"}].
                           Each dict should have "name" and optionally "desc" keys.
                           If a character is new, they will be auto-anchored from video output.
    
    Returns:
        Status message with shot number, file path, and character info.
    
    Example Usage (from LLM perspective):
        # First shot with uploaded image:
        generate_video_segment(
            prompt="Woman doing yoga in a peaceful park at sunrise",
            session_id="chat_abc123",
            s3_uri="s3://ai-video-consistency/uploads/chat_abc123/a1b2c3d4.jpg",
            characters_in_shot=[{"name": "Sarah", "desc": "Yoga instructor"}]
        )
        
        # Second shot (continuation, no image needed):
        generate_video_segment(
            prompt="Sarah transitions into tree pose",
            session_id="chat_abc123",
            characters_in_shot=[{"name": "Sarah"}]
        )
        
        # Third shot (new character appears):
        generate_video_segment(
            prompt="Sarah and her instructor practice together",
            session_id="chat_abc123",
            characters_in_shot=[
                {"name": "Sarah"},
                {"name": "Instructor", "desc": "Older woman in purple outfit"}
            ]
        )
    """
    db = next(get_db())
    
    # --- STEP 0: Resolve Session & State ---
    # Find or Create Project (Session)
    project = db.query(models.Project).filter(
        models.Project.description == f"Session: {session_id}"
    ).first()
    
    if not project:
        project = models.Project(
            name=f"Chat {session_id}", 
            description=f"Session: {session_id}"
        )
        db.add(project)
        db.flush()  # Get ID
    
    # Get/Create Continuity State
    state = continuity_engine.get_or_create_state(db, project.id, session_id)
    
    # --- STEP 1: Handle Multi-Character Logic (LLM-Driven Intelligence) ---
    active_ids = []
    new_characters = []
    existing_characters = []
    
    # Iterate through every character the LLM identified in the current shot
    for char_data in characters_in_shot or []:
        char_name = char_data.get("name")
        char_desc = char_data.get("desc")
        
        if not char_name:
            continue
        
        # Check if character already exists
        existing_char = db.query(models.Character).filter(
            models.Character.project_id == project.id,
            models.Character.name == char_name
        ).first()
        
        if existing_char:
            # Existing character - add to active list
            active_ids.append(existing_char.id)
            existing_characters.append(char_name)
            print(f"[~] Reusing existing Anchor: {char_name}")
        else:
            # New character - we'll create after video generation
            new_characters.append({"name": char_name, "desc": char_desc})
    
    # Update state with ALL active characters (existing + newly created)
    if active_ids:
        state.active_character_ids = json.dumps(active_ids)
        db.commit()
    
    # --- STEP 1.5: FIRST-SHOT IMAGE HANDLING (S3-Only Production Architecture) ---
    raw_image_reference = None
    uploaded_image_s3_uri = None  # Track the S3 URI for character creation
    
    # Handle S3 URI for first shot
    if s3_uri and not active_ids:
        # This is a first shot with an uploaded image from S3
        print(f"[FIRST SHOT] Processing image from S3: {s3_uri}")
        uploaded_image_s3_uri = s3_uri
        
        try:
            # Download from S3 and convert to base64 for Veo (internal use only)
            print("Downloading image from S3...")
            image_bytes = download_from_uri(s3_uri)
            
            # Convert to base64 for Veo API (backend-only, not exposed to user)
            image_base64_encoded = base64.b64encode(image_bytes).decode()
            
            raw_image_reference = {
                "referenceType": "asset",
                "image": {
                    "bytesBase64Encoded": image_base64_encoded,
                    "mimeType": "image/jpeg"
                },
                "weight": 1.0  # Highest priority for first shot
            }
            print("[VEO] Image ready for injection (base64 conversion done server-side)")
        except Exception as e:
            return f"[ERROR] Failed to process S3 image: {e}"
    
    # --- STEP 2: Generate Video (with Multi-Anchor + Flow OR Raw Image) ---
    video_bytes = continuity_engine.generate_segment(
        db, project.id, prompt, session_id,
        raw_image_ref=raw_image_reference  # Pass raw image if first shot
    )

    # --- STEP 3: Save Video Output to S3 ---
    shot_index = db.query(models.Shot).filter(
        models.Shot.project_id == project.id
    ).count() + 1
    
    output_s3_uri = upload_video(video_bytes, session_id, shot_number=shot_index)
    print(f"[S3] Video uploaded: {output_s3_uri}")
    
    # Generate public URL for sharing (expires in 24 hours)
    public_url = get_public_url(output_s3_uri, expiration=86400)
    
    # --- STEP 4: POST-GENERATION CHARACTER CREATION (The Auto-Anchor Logic) ---
    # If this was a first shot with uploaded image, create character from the UPLOADED image (not video frame)
    if uploaded_image_s3_uri and not active_ids and new_characters:
        print("[POST-GEN] Creating character anchors from uploaded image...")
        
        for char_data in new_characters:
            try:
                char_name = char_data["name"]
                char_desc = char_data.get("desc", "Auto-created from uploaded image")
                
                # Use the uploaded image as the character anchor (DNA source)
                # This is better than extracting from video output
                character = models.Character(
                    project_id=project.id,
                    name=char_name,
                    description=char_desc,
                    ref_image_path=uploaded_image_s3_uri,  # Use uploaded image, not video frame
                    face_embedding=None,  # Background worker fills this
                    style_embedding=None,  # Background worker fills this
                    dominant_colors=None,  # Background worker fills this
                )
                db.add(character)
                db.flush()  # Get ID
                
                # Enqueue async DNA extraction from the uploaded image
                print(f"[DNA] Enqueuing extraction for {char_name} from uploaded image...")
                job = render_queue.enqueue(extract_dna_task, character.id)
                print(f"[DNA] Job {job.id} enqueued for character {character.id}")
                
                active_ids.append(character.id)
                print(f"[+] Created character '{char_name}' from uploaded image: {uploaded_image_s3_uri}")
                
            except Exception as e:
                print(f"Warning: Failed to create character {char_data['name']}: {e}")
    
    # --- STEP 4.5: Handle Multi-Character DNA Anchoring (for continuation shots with new characters) ---
    # If new characters appear in non-first shots (no s3_uri), extract from video output
    elif new_characters and not uploaded_image_s3_uri:
        for char_data in new_characters:
            try:
                character = _handle_character_logic(
                    db, project.id,
                    char_data["name"],
                    char_data["desc"],
                    True,  # is_new = True
                    output_s3_uri  # Pass S3 URI instead of local path
                )
                
                if character:
                    active_ids.append(character.id)
            except Exception as e:
                print(f"Warning: Failed to handle character {char_data['name']}: {e}")
    
    # Update state with ALL active characters (existing + newly created)
    if active_ids:
        state.active_character_ids = json.dumps(active_ids)
        # For new characters, set their anchor frame as the flow reference
        if new_characters:
            first_new_char = db.query(models.Character).get(active_ids[-1])
            if first_new_char and first_new_char.ref_image_path:
                state.last_frame_path = first_new_char.ref_image_path
        db.commit()
    
    # --- STEP 5: Update Flow Continuity (extract last frame for next shot) ---
    # Only extract new flow frame if we didn't just create new characters
    if not new_characters:
        try:
            # Extract frame bytes and upload to S3
            frame_bytes = _extract_last_frame_bytes(video_bytes)
            continuity_s3_uri = upload_continuity_frame(frame_bytes, session_id)
            state.last_frame_path = continuity_s3_uri
            db.commit()
            print(f"[S3] Updated Flow: {continuity_s3_uri}")
        except Exception as e:
            print(f"Warning: Failed to extract/upload last frame: {e}")

    # --- STEP 6: Log Shot History ---
    shot_record = models.Shot(
        project_id=project.id,
        index=shot_index,
        description=prompt,
        duration_seconds=6,  # Default duration (Veo doesn't return actual duration)
        created_at=datetime.utcnow(),
    )
    db.add(shot_record)
    db.commit()
    
    print(f"[>] Logged Shot #{shot_index}: {prompt[:50]}...")

    # Build response message with character info
    char_info = ""
    if characters_in_shot:
        char_names = [c.get("name") for c in characters_in_shot if c.get("name")]
        if char_names:
            char_info = f" | Characters: {', '.join(char_names)}"
    
    new_anchor_info = f" ({len(new_characters)} NEW ANCHOR{'S' if len(new_characters) != 1 else ''})" if new_characters else ""
    
    return f"[OK] Video generated! Shot #{shot_index}\n\nS3 URI: {output_s3_uri}\nPublic URL (24h): {public_url}{char_info}{new_anchor_info}\n\nMemory updated."

@mcp.tool()
def update_narrative_state(session_id: str, fact_key: str, fact_value: str):
    """
    Updates a key semantic fact in the session's memory (e.g., 'item_held'='sword'). 
    Args:
        session_id: The chat ID.
        fact_key: The narrative aspect being tracked (e.g., 'location', 'outfit', 'item_held').
        fact_value: The new description (e.g., 'dark forest', 'blue cloak', 'empty hand').
    """
    db = next(get_db())
    
    project = db.query(models.Project).filter(models.Project.description == f"Session: {session_id}").first()
    if not project:
        return f"Error: Session {session_id} not found."
    
    state = continuity_engine.get_or_create_state(db, project.id, session_id)
    
    # Load JSON, update key, save JSON
    context = state.narrative_context or {}
    context[fact_key] = fact_value
    state.narrative_context = context
    
    db.commit()
    return f"Narrative Memory Updated: {fact_key} is now '{fact_value}'."

@mcp.tool()
def set_active_characters(session_id: str, character_names: List[str]):
    """
    Sets the active character Anchors for the current session. 
    Use this when multiple known characters are in a scene.
    Args:
        session_id: The chat ID.
        character_names: List of character names that are currently in the scene.
    """
    db = next(get_db())
    
    project = db.query(models.Project).filter(models.Project.description == f"Session: {session_id}").first()
    if not project:
        return f"Error: Session {session_id} not found."

    state = continuity_engine.get_or_create_state(db, project.id, session_id)
    
    active_ids = []
    
    for name in character_names:
        char = db.query(models.Character).filter(
            models.Character.project_id == project.id, 
            models.Character.name == name
        ).first()
        
        if char:
            active_ids.append(char.id)
            
    # Save the list of IDs as JSON string
    state.active_character_ids = json.dumps(active_ids)
    db.commit()
    
    return f"Active characters set: {', '.join(character_names)}. {len(active_ids)} anchors ready for injection."

if __name__ == "__main__":
    mcp.run()
# mcp_server.py
import os
import sys
import json
import base64
import subprocess
from pathlib import Path
from typing import List
from datetime import datetime

# Add backend directory to Python path
backend_dir = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_dir))

# Change working directory to backend so database path is correct
os.chdir(str(backend_dir))

from mcp.server.fastmcp import FastMCP
from app.db.session import SessionLocal, engine
from app.db.base import Base
from app import models
from app.services.continuity.continuity_engine import ContinuityEngine
from app.services.embedding import extract_character_dna, to_json_str
from app.core.files import save_character_image_bytes
from app.core.queue import render_queue
from app.workers.tasks import extract_dna_task

# Ensure all tables are created
Base.metadata.create_all(bind=engine)

# Initialize the MCP Server
mcp = FastMCP("VideoMemoryLayer")
continuity_engine = ContinuityEngine()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- Utility Functions for Production-Grade Character Management ---


def _extract_last_frame(video_path: str, output_path: str):
    """Extract last frame from video using ffmpeg."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    cmd = [
        "ffmpeg", "-y",
        "-sseof", "-0.1",  # Seek to 0.1 seconds before end
        "-i", video_path,
        "-frames:v", "1",
        output_path
    ]
    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)


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
        
        os.makedirs("media/characters", exist_ok=True)
        anchor_frame_path = f"media/characters/{os.path.basename(video_path).replace('.mp4', '_anchor.jpg')}"
        
        # Extract anchor frame
        try:
            _extract_last_frame(video_path, anchor_frame_path)
        except Exception as e:
            print(f"Warning: Failed to extract anchor frame: {e}")
            anchor_frame_path = None
        
        # Extract DNA
        dna = None
        if anchor_frame_path and os.path.exists(anchor_frame_path):
            try:
                dna = extract_character_dna(anchor_frame_path)
            except Exception as e:
                print(f"Warning: Failed to extract character DNA: {e}")
        
        char = models.Character(
            project_id=project_id,
            name=name,
            description=desc or f"{name} - auto-created from video",
            ref_image_path=anchor_frame_path,
            face_embedding=to_json_str(dna["face_embedding"]) if dna else None,
            style_embedding=to_json_str(dna["style_embedding"]) if dna else None,
            dominant_colors=to_json_str(dna["dominant_colors"]) if dna else None,
        )
        db.add(char)
        db.flush()
        print(f"[+] Created new Anchor: {name}")
    
    else:
        # Case B: Existing Character
        # We don't overwrite their DNA. We just confirm they are active.
        print(f"[~] Reusing existing Anchor: {name}")
    
    return char

@mcp.tool()
def register_character_anchor(
    session_id: str,
    character_name: str,
    image_base64: str,
    character_desc: str = "Primary subject from uploaded image."
) -> str:
    """
    Registers an uploaded image as the permanent DNA Anchor for a character.
    
    INSTANT REGISTRATION: < 500ms response time!
    - Only performs fast operations: decode, file write, DB insert, queue job
    - DNA extraction happens in background worker (invisible to user)
    
    This is the "Setup" phase that separates Anchor registration from video generation,
    ensuring the exact face/style from the uploaded image is used consistently.
    
    Args:
        session_id: The unique chat session ID (e.g. 'chat_123').
        character_name: The name of the character (e.g. "Sarah", "The Detective").
        image_base64: The uploaded image encoded as base64 string.
        character_desc: Optional description of the character's appearance/role.
    
    Returns:
        Confirmation message that the anchor is registered and ready for video generation.
    
    Example Usage (from LLM perspective):
        # User uploads an image of a woman
        register_character_anchor(
            session_id="story_001",
            character_name="Sarah",
            image_base64="/9j/4AAQSkZJRg...",  # Base64 encoded JPEG
            character_desc="Woman with red hair, green eyes, professional attire"
        )
        
        # Now generate videos using this character
        generate_video_segment(
            prompt="Sarah walks into the office building",
            session_id="story_001",
            characters_in_shot=[{"name": "Sarah"}]
        )
    """
    db = next(get_db())
    
    # --- FAST OPERATION 1: Resolve Project (Session) ---
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
    
    # --- FAST OPERATION 2: Check if Character Already Exists ---
    existing_char = db.query(models.Character).filter(
        models.Character.project_id == project.id,
        models.Character.name == character_name
    ).first()
    
    if existing_char:
        return f"[!] Character '{character_name}' already exists with anchor image. Use generate_video_segment to create videos."
    
    # --- FAST OPERATION 3: Decode Base64 (~50ms) ---
    try:
        image_bytes = base64.b64decode(image_base64)
    except Exception as e:
        return f"[ERROR] Failed to decode image: {e}"
    
    # --- FAST OPERATION 4: Write File to Disk (~100ms) ---
    # Use placeholder ID of 0 for initial file naming
    image_path = save_character_image_bytes(0, image_bytes, extension=".jpg")
    
    # --- FAST OPERATION 5: Create Character Record (~50ms) ---
    # NOTE: Embeddings are NULL - filled by background worker!
    character = models.Character(
        project_id=project.id,
        name=character_name,
        description=character_desc,
        ref_image_path=image_path,
        face_embedding=None,  # Background worker fills this
        style_embedding=None,  # Background worker fills this
        dominant_colors=None,  # Background worker fills this
    )
    db.add(character)
    db.flush()  # Get the character ID
    
    # --- FAST OPERATION 6: Rename File with Correct ID (~50ms) ---
    final_image_path = image_path.replace("/0_", f"/{character.id}_")
    try:
        os.rename(image_path, final_image_path)
        character.ref_image_path = final_image_path
    except Exception as e:
        # If rename fails, keep original path (not critical)
        print(f"[WARN] Failed to rename file: {e}")
    
    # --- FAST OPERATION 7: Update Continuity State (~50ms) ---
    state = db.query(models.ContinuityState).filter_by(project_id=project.id).first()
    if not state:
        state = models.ContinuityState(
            project_id=project.id,
            session_id=session_id,
            active_character_ids=json.dumps([character.id])
        )
        db.add(state)
    else:
        # Add to existing active characters
        active_ids = json.loads(state.active_character_ids or "[]")
        if character.id not in active_ids:
            active_ids.append(character.id)
        state.active_character_ids = json.dumps(active_ids)
    
    # --- FAST OPERATION 8: Enqueue Background Job (~50ms) ---
    # This is where the magic happens - offload slow work to worker
    job = render_queue.enqueue(extract_dna_task, character.id)
    
    # --- FAST OPERATION 9: Commit Transaction (~50ms) ---
    db.commit()
    
    # Total time: ~400-500ms (INSTANT!)
    print(f"[+] Registered Anchor: {character_name} (ID: {character.id})")
    print(f"[DNA] Background job enqueued: {job.id}")
    return f"[OK] Anchor '{character_name}' registered instantly! DNA extraction started in background (Job {job.id}). You can now generate videos with this character."


@mcp.tool()
def generate_video_segment(
    prompt: str,
    session_id: str,
    characters_in_shot: list = None
):
    """
    Generates a video segment with intelligent multi-character tracking.
    
    * The LLM identifies ALL characters - we execute with precision.
    
    This tool handles:
    - Multi-character zero-shot creation (first mention = auto-anchor for EACH character)
    - Multi-shot identity consistency (character DNA reuse with 0.8 weight)
    - Flow continuity (last frame → next shot with 0.5 weight)
    - Complete shot history logging
    
    Args:
        prompt: The visual description for the video model (e.g. "She walks through the neon-lit street").
        session_id: The unique chat session ID (e.g. 'chat_123').
        characters_in_shot: A list of characters present in this shot, e.g.,
                           [{"name": "The Man", "desc": "Grey suit, distinguished"}, 
                            {"name": "The Woman", "desc": "Blue dress, blonde hair"}].
                           Each dict should have "name" and optionally "desc" keys.
                           If a character is new, they will be auto-anchored from this shot.
    
    Returns:
        Status message with shot number, file path, and character info.
    
    Example Usage (from LLM perspective):
        # First shot with two characters:
        generate_video_segment(
            prompt="A man in a grey suit and a woman in a blue dress sit at a café table",
            session_id="story_001",
            characters_in_shot=[
                {"name": "The Man", "desc": "Grey suit, distinguished, salt-and-pepper hair"},
                {"name": "The Woman", "desc": "Blue dress, blonde hair, elegant"}
            ]
        )
        
        # Second shot (both characters continue):
        generate_video_segment(
            prompt="The man leans forward as the woman laughs",
            session_id="story_001",
            characters_in_shot=[
                {"name": "The Man"},
                {"name": "The Woman"}
            ]
        )
        
        # Third shot (only one character):
        generate_video_segment(
            prompt="The woman walks away down the street",
            session_id="story_001",
            characters_in_shot=[
                {"name": "The Woman"}
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
    
    # Update active characters (existing ones for now)
    if active_ids:
        state.active_character_ids = json.dumps(active_ids)
        db.commit()
    
    # --- STEP 2: Generate Video (with Multi-Anchor + Flow) ---
    video_bytes = continuity_engine.generate_segment(db, project.id, prompt, session_id)

    # --- STEP 3: Save Video Output ---
    os.makedirs("media/generated", exist_ok=True)
    output_filename = f"media/generated/{session_id}_{os.urandom(4).hex()}.mp4"
    with open(output_filename, "wb") as f:
        f.write(video_bytes)
    
    # --- STEP 4: Multi-Character DNA Anchoring (for new characters) ---
    # Create anchor for each new character from the generated video
    for char_data in new_characters:
        try:
            character = _handle_character_logic(
                db, project.id,
                char_data["name"],
                char_data["desc"],
                True,  # is_new = True
                output_filename
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
        os.makedirs("media/continuity", exist_ok=True)
        last_frame_path = f"media/continuity/{session_id}_last_frame.jpg"
        
        try:
            _extract_last_frame(output_filename, last_frame_path)
            state.last_frame_path = last_frame_path
            db.commit()
            print(f"[*] Updated Flow: {last_frame_path}")
        except Exception as e:
            print(f"Warning: Failed to extract last frame: {e}")

    # --- STEP 6: Log Shot History ---
    shot_index = db.query(models.Shot).filter(
        models.Shot.project_id == project.id
    ).count() + 1
    
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
    
    return f"[OK] Video generated! Shot #{shot_index} saved at {output_filename}{char_info}{new_anchor_info}. Memory updated."

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
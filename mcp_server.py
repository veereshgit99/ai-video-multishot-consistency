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
    This MCP server instance has a unique session: "{INSTANCE_SESSION_ID} (example: chat_7f3a9b2e4c1d)"
    ALL video generation requests in THIS CHAT must use session_id="{INSTANCE_SESSION_ID}"
    
    FOR EVERY generate_video_segment CALL:
    - YOU MUST pass session_id="{INSTANCE_SESSION_ID}" 
    - DO NOT generate new session IDs
    - REUSE THE SAME SESSION ID: "{INSTANCE_SESSION_ID}"
    
    *** CRITICAL TOOL USAGE ***
    PRODUCTION WORKFLOW (Link-Based - No Base64!)
    
    IMAGE IS OPTIONAL - Only needed for first shots with new characters.
    
    *** SECURITY RULES ***
    - NEVER upload images to S3 yourself
    - NEVER describe character appearance from attached images (confuses video model)
    - NEVER expose S3 URIs, bucket names, or file paths in responses
    - If user attaches image: Ask "Please provide a public HTTPS link instead"
    - Only accept: s3:// URIs (from backend API) or public https:// links
    
    *** MODEL SELECTION ***
    - Ask user: "Which model? (veo-2.0, veo-3.1, gen4_turbo, minimax, seedance, seedance-pro-fast, seedance-pro, kling-2.5-turbo-pro-image, or kling-2.5-turbo-pro-text)"
    - veo-2.0: Google Veo 2.0 (6s, $2.40/shot, image-to-video, multi-character support)
    - veo-3.1: Google Veo 3.1 (6s, text-to-video ONLY, highest quality, first shot only)
    - gen4_turbo: Runway Gen4 (5s, $0.30/shot, 8x cheaper!)
    - minimax: MiniMax Hailuo-2.3 (6s, 1080P, competitive pricing)
    - seedance: Bytedance Seedance 1.0 Lite (2-12s configurable, multi-character support via 1-4 reference images)
    - seedance-pro-fast: Bytedance Seedance 1.0 Pro Fast (2-12s, text-to-video ONLY, 1080p, fast generation, first shot only)
    - seedance-pro: Bytedance Seedance 1.0 Pro (2-12s, text-to-video ONLY, 1080p, higher quality, first shot only)
    - kling-2.5-turbo-pro-image: Kling Video v2.5 Turbo Pro Image (10s, image-to-video, cinematic camera moves, fluid motion)
    - kling-2.5-turbo-pro-text: Kling Video v2.5 Turbo Pro Text (10s, text-to-video ONLY, top-tier motion fluidity, exceptional prompt precision)
    - Default to veo-2.0 if not specified (cheaper + faster)
    
    1. For First Shot WITH Image:
       - Ask: "Image link for first shot?" (s3:// or https:// only)
       - Call: generate_video_segment(prompt=..., session_id="{INSTANCE_SESSION_ID}", raw_image_references=[{{"url": "https://...", "weight": 1.0}}], model="gen4_turbo", characters_in_shot=...)
    
    2. For First Shot WITHOUT Image:
       - Call: generate_video_segment(prompt=..., session_id="{INSTANCE_SESSION_ID}", model="gen4_turbo", characters_in_shot=...)
    
    3. For Continuation Shots:
       - Call: generate_video_segment(prompt=..., session_id="{INSTANCE_SESSION_ID}", model="gen4_turbo", characters_in_shot=...)
    
    4. For Shots WITH Scene/Prop References:
       - Call: generate_video_segment(prompt=..., session_id="{INSTANCE_SESSION_ID}", raw_image_references=[{{"url": "https://sword.jpg", "weight": 0.7}}], model="veo-2.0", characters_in_shot=...)
    
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
    raw_image_references: list = None,
    characters_in_shot: list = None,
    model: str = "veo-2.0",
    continue_from_shot: int = None,
    duration: int = None
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
    - If you get "No result received" error, the video is likely still generating (timeout issue)
    - You can wait for some time or tell user: "Video is generating in background. Check database/S3 in a few minutes."
    - DO NOT retry automatically on errors - ask user first ("Generation may have failed or timed out. Retry?")
    - It's wasting resources to retry automatically without user confirmation.
    
    IMAGE USAGE (OPTIONAL):
    
    CRITICAL: If user attaches an image file, respond:
    "Please provide a public HTTPS link to the image instead. This tool only accepts URLs (s3:// or https://), not file uploads."
    
    DO NOT:
    - Upload images to S3 yourself (security risk)
    - Describe character appearance from attached images (confuses video model)
    - Expose S3 bucket names, paths, or URIs in responses
    
    When to Ask for Image:
    - ONLY for first shot to establish character from reference
    - NOT for continuation shots (uses stored DNA)
    
    Accepted Formats:
    - s3:// URIs (from backend upload API)
    - https:// public image URLs
    
    Workflow:
    - First shot WITH link: Downloads -> Veo (weight 1.0)
    - First shot WITHOUT: Generates -> extracts frame -> creates anchor
    - Continuation: Uses stored DNA (0.8) + flow (0.5)
    
    This tool handles:
    - First-shot: Raw image injection from S3 (no pre-registration needed)
    - Multi-character zero-shot creation (first mention = auto-anchor from video output)
    - Multi-shot identity consistency (character DNA reuse with 0.8 weight)
    - Flow continuity (last frame -> next shot with 0.5 weight)
    - Complete shot history logging
    
    Args:
        prompt: The visual description for the video model (e.g. "Woman doing yoga in a park").
        session_id: Session ID for this conversation. Defaults to unique instance ID (same for all videos in this chat).
                   CRITICAL: Claude MUST pass the same session_id for all videos in this conversation.
        raw_image_references: [OPTIONAL] List of external image references for ANY shot (first, continuation, or branching).
                             Each dict must contain:
                             - "url": S3 URI (s3://...) or public HTTPS URL
                             - "weight": [OPTIONAL] Float 0.0-1.0 (default varies by type)
                             - "is_end_frame": [OPTIONAL] Boolean (default: false). Marks this as the target end frame.
                             
                             Reference Types & Recommended Weights:
                             - User/Raw Character (Start Frame): 0.8-1.0 (Identity Lock - dictates beginning appearance)
                             - End Frame (Tail Image): 0.9 (Compositional Target - dictates final pose/composition)
                             - Scene/Prop Reference: 0.6-0.7 (Style enforcement without overpowering)
                             
                             Backend automatically applies fixed weights to internal references:
                             - Stored Character DNA: 0.8 (High priority, allows slight drift/correction)
                             - Flow Anchor (last frame): 0.5 (Medium priority for motion/lighting continuity)
                             
                             End Frame Support by Model:
                             - Kling Image: Uses tail_image_url (explicit start->end animation)
                             - Veo 2.0/Seedance Lite: Includes end frame in multi-ref list (scene bridging)
                             - Other models: Ignores end frame (single image or text-only)
                             
                             Example - Character with End Frame (Kling/Veo/Seedance):
                             [{{"url": "https://char-start.jpg", "weight": 1.0}},
                              {{"url": "https://char-end.jpg", "weight": 0.9, "is_end_frame": true}}]
                             
                             Example - Multi-image with props:
                             [{{"url": "https://character.jpg", "weight": 1.0}},
                              {{"url": "s3://bucket/sword.jpg", "weight": 0.7}}]
                             
                             Leave empty for text-only models (veo-3.1, seedance-pro, kling-text) or pure continuation shots.
        characters_in_shot: A list of characters present in this shot, e.g.,
                           [{"name": "Sarah", "desc": "Woman in yoga outfit"}].
                           Each dict should have "name" and optionally "desc" keys.
                           If a character is new, they will be auto-anchored from video output.
        model: [OPTIONAL] Video model to use. Options:
               - "veo-2.0" (default): Google Veo 2.0 (6s, $2.40/shot, image-to-video, multi-anchor strategy)
               - "veo-3.1": Google Veo 3.1 (6s, text-to-video ONLY, highest quality, first shot only)
               - "gen4_turbo": Runway Gen4 Turbo (5s, $0.30/shot, flow-only strategy with single last frame)
               - "minimax": MiniMax Hailuo-2.3 (6s, 1080P, flow-only strategy with single last frame)
               - "seedance": Bytedance Seedance 1.0 Lite (2-12s configurable, multi-anchor strategy like Veo, supports 1-4 reference images)
               - "seedance-pro-fast": Bytedance Seedance 1.0 Pro Fast (2-12s, text-to-video ONLY, 1080p, cheaper alternative to veo-3.1, first shot only)
               - "seedance-pro": Bytedance Seedance 1.0 Pro (2-12s, text-to-video ONLY, 1080p, higher quality, first shot only)
               - "kling-2.5-turbo-pro-image": Kling Video v2.5 Turbo Pro Image (10s, image-to-video, cinematic camera moves, fluid motion, flow-only strategy with single last frame)
               - "kling-2.5-turbo-pro-text": Kling Video v2.5 Turbo Pro Text (10s, text-to-video ONLY, top-tier motion fluidity, exceptional prompt precision, first shot only)
        continue_from_shot: [OPTIONAL] Shot index to continue from (e.g., 1, 2, 3).
                           If specified, uses that shot's last frame instead of the most recent shot.
                           Enables branching narratives from any previous shot.
        duration: [OPTIONAL] Video duration in seconds. Only applies to Seedance and Kling models.
                  If not specified, uses model defaults:
                  - Seedance (Lite/Pro/Pro Fast): 6s
                  - Kling (Image/Text): 5s
                  - Other models: Use their fixed durations
                  Valid ranges: Seedance (2-12s), Kling (5 or 10s)
    
    Returns:
        Status message with shot number, file path, and character info.
    
    Example Usage (from LLM perspective):
        # First shot with character reference (Veo 2.0 multi-anchor):
        generate_video_segment(
            prompt="Woman doing yoga in a peaceful park at sunrise",
            session_id="chat_abc123",
            raw_image_references=[{{"url": "https://example.com/woman.jpg", "weight": 1.0}}],
            characters_in_shot=[{{"name": "Sarah", "desc": "Yoga instructor"}}],
            model="veo-2.0"
        )
        
        # Second shot (continuation with stored character DNA + flow):
        generate_video_segment(
            prompt="Sarah transitions into tree pose",
            session_id="chat_abc123",
            characters_in_shot=[{{"name": "Sarah"}}],
            model="veo-2.0"
        )
        
        # Third shot with prop reference (multi-image):
        generate_video_segment(
            prompt="Sarah picks up a glowing crystal sword",
            session_id="chat_abc123",
            raw_image_references=[{{"url": "s3://bucket/sword.jpg", "weight": 0.7}}],
            characters_in_shot=[{{"name": "Sarah"}}],
            model="veo-2.0"
        )
        
        # Shot with start and end frame (scene bridging with Kling):
        generate_video_segment(
            prompt="Sarah morphs from warrior stance to meditation pose",
            session_id="chat_abc123",
            raw_image_references=[
                {{"url": "https://warrior-pose.jpg", "weight": 1.0}},
                {{"url": "https://meditation-pose.jpg", "weight": 0.9, "is_end_frame": true}}
            ],
            characters_in_shot=[{{"name": "Sarah"}}],
            model="kling-2.5-turbo-pro-image"
        )
        
        # Custom duration for Seedance:
        generate_video_segment(
            prompt="Epic battle sequence",
            session_id="chat_abc123",
            characters_in_shot=[{"name": "Sarah"}],
            model="seedance",
            duration=10
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
    
    # --- STEP 1.5: RAW IMAGE REFERENCES HANDLING (Multi-Image with Weights) ---
    processed_raw_references = []
    first_character_image_uri = None  # Track first image for character creation
    
    # Process raw_image_references list
    if raw_image_references:
        print(f"[RAW REFS] Processing {len(raw_image_references)} external image reference(s)")
        
        for idx, ref in enumerate(raw_image_references):
            # Validate structure
            if not isinstance(ref, dict):
                return f"[ERROR] raw_image_references[{idx}] must be a dict with 'url' and optional 'weight'"
            
            image_url = ref.get("url")
            if not image_url:
                return f"[ERROR] raw_image_references[{idx}] missing required 'url' field"
            
            # Check if this is an end frame
            is_end_frame = ref.get("is_end_frame", False)
            
            # Default weights based on reference type
            # User can override by providing explicit weight
            weight = ref.get("weight")
            if weight is None:
                if is_end_frame:
                    weight = 0.9  # End frame = compositional target
                elif idx == 0:
                    weight = 1.0  # First image = character anchor (start frame)
                else:
                    weight = 0.7  # Additional images = props/scene
            
            # Validate weight range
            if not (0.0 <= weight <= 1.0):
                return f"[ERROR] raw_image_references[{idx}] weight must be between 0.0 and 1.0, got {weight}"
            
            try:
                # Download from S3 or public URL
                if image_url.startswith("s3://"):
                    print(f"  [{idx+1}] Downloading from S3: {image_url}")
                    image_bytes = download_from_uri(image_url)
                elif image_url.startswith(("http://", "https://")):
                    print(f"  [{idx+1}] Downloading from public URL: {image_url}")
                    import requests
                    response = requests.get(image_url, timeout=30)
                    response.raise_for_status()
                    image_bytes = response.content
                else:
                    return f"[ERROR] raw_image_references[{idx}] invalid URL. Use S3 (s3://...) or public URL (https://...)"
                
                # Convert to base64 for video API
                image_base64_encoded = base64.b64encode(image_bytes).decode()
                
                # Build reference dict in Veo format with weight and is_end_frame flag
                processed_ref = {
                    "referenceType": "asset",
                    "image": {
                        "bytesBase64Encoded": image_base64_encoded,
                        "mimeType": "image/jpeg"
                    },
                    "weight": weight
                }
                
                # Preserve is_end_frame flag for backend routing
                if is_end_frame:
                    processed_ref["is_end_frame"] = True
                
                processed_raw_references.append(processed_ref)
                
                # Track first non-end-frame image for character creation (if needed)
                if not is_end_frame and not first_character_image_uri and not active_ids:
                    first_character_image_uri = image_url
                
                ref_type = "end frame" if is_end_frame else ("start frame" if idx == 0 else "prop/scene ref")
                print(f"  [{idx+1}] Processed as {ref_type} with weight: {weight}")
                
            except Exception as e:
                return f"[ERROR] Failed to download/process image {idx+1} from {image_url}: {e}"
        
        print(f"[RAW REFS] Successfully processed {len(processed_raw_references)} reference(s)")
    
    # --- STEP 2: Generate Video (with Multi-Anchor + Flow OR Raw Image) ---
    video_bytes = continuity_engine.generate_segment(
        db, project.id, prompt, session_id,
        raw_image_refs=processed_raw_references if processed_raw_references else None,  # Pass processed raw refs
        model=model,  # Pass model selection
        continue_from_shot=continue_from_shot,  # Pass branching parameter
        duration=duration  # Pass duration (only used by Seedance/Kling)
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
    if first_character_image_uri and not active_ids and new_characters:
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
                    ref_image_path=first_character_image_uri,  # Use first uploaded image, not video frame
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
                print(f"[+] Created character '{char_name}' from uploaded image: {first_character_image_uri}")
                
            except Exception as e:
                print(f"Warning: Failed to create character {char_data['name']}: {e}")
    
    # --- STEP 4.5: Handle Multi-Character DNA Anchoring (for continuation shots with new characters) ---
    # If new characters appear in non-first shots (no raw images), extract from video output
    elif new_characters and not first_character_image_uri:
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
    
    # --- STEP 5: Update Flow Continuity (extract last frame for THIS shot) ---
    # Extract and store per-shot last frame for branching support
    shot_last_frame_s3_uri = None
    try:
        # Extract frame bytes and upload to S3 with shot-specific naming
        frame_bytes = _extract_last_frame_bytes(video_bytes)
        shot_last_frame_s3_uri = upload_continuity_frame(frame_bytes, session_id, shot_number=shot_index)
        
        # Update global state for linear continuation (most recent shot)
        if not new_characters:
            state.last_frame_path = shot_last_frame_s3_uri
            db.commit()
        
        print(f"[S3] Saved shot #{shot_index} last frame: {shot_last_frame_s3_uri}")
    except Exception as e:
        print(f"Warning: Failed to extract/upload last frame for shot {shot_index}: {e}")

    # --- STEP 6: Log Shot History ---
    shot_record = models.Shot(
        project_id=project.id,
        index=shot_index,
        description=prompt,
        duration_seconds=6,  # Default duration (Veo doesn't return actual duration)
        last_frame_path=shot_last_frame_s3_uri,  # Store per-shot last frame
        video_path=output_s3_uri,  # Store video S3 URI
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
    
    new_anchor_info = f" ({len(new_characters)} NEW)" if new_characters else ""
    
    # Redact sensitive S3 details from user-facing response
    return f"[OK] Shot #{shot_index} generated{char_info}{new_anchor_info}"

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
# backend/app/services/continuity/continuity_engine.py

from sqlalchemy.orm import Session
from app import models
from app.services.video.google_flow import GoogleFlowVideoService
from app.services.s3_storage import download_from_uri
import base64
import json


class ContinuityEngine:
    
    def __init__(self):
        # Video service is now created per-request based on model parameter
        pass

    def get_or_create_state(self, db: Session, project_id: int, session_id: str = None):
        state = db.query(models.ContinuityState).filter_by(project_id=project_id).first()
        if not state:
            state = models.ContinuityState(project_id=project_id, session_id=session_id or f"session_{project_id}")
            db.add(state)
            db.commit()
        return state

    def generate_segment(self, db: Session, project_id: int, prompt: str, session_id: str = None, raw_image_ref: dict = None, model: str = "veo-2.0"):
        """
        The Core Logic: Multi-Anchor + Flow Generation (Path A + Path C)
        NOW WITH FIRST-SHOT RAW IMAGE INJECTION!
        
        Args:
            raw_image_ref: Optional pre-built reference image dict for first-shot scenarios.
                          If provided, this takes precedence over character anchors.
            model: Video model to use ("veo-2.0" or "gen4_turbo")
        """
        from app.services.video.base import get_video_service, create_composite_image
        
        # Create video service based on model selection
        video_service = get_video_service(model)
        is_runway = model.startswith("gen4") or model == "runway"
        state = self.get_or_create_state(db, project_id, session_id)
        
        # --- 1. Build Reference Images (The "Anchor + Flow" Strategy) ---
        reference_images = []

        # A. FIRST-SHOT RAW IMAGE (Simplified Workflow)
        if raw_image_ref:
            # User uploaded an image - inject it directly (weight 1.0)
            reference_images.append(raw_image_ref)
            print("[FIRST-SHOT] Using raw uploaded image (weight 1.0)")
        
        # B. MULTI-ANCHOR CHARACTERS (Path C Logic - Continuation Shots)
        active_ids = json.loads(state.active_character_ids or "[]")
        
        # Only inject character anchors if NOT a first-shot with raw image
        if not raw_image_ref:
            for char_id in active_ids:
                char = db.query(models.Character).get(char_id)
                if char and hasattr(char, 'ref_image_path') and char.ref_image_path:
                    # Download from S3 if it's an s3:// URI, otherwise load from local disk
                    if char.ref_image_path.startswith("s3://"):
                        anchor_blob = self._load_image_from_s3(char.ref_image_path)
                    else:
                        # Legacy local file support
                        import os
                        if os.path.exists(char.ref_image_path):
                            anchor_blob = self._load_image_as_base64(char.ref_image_path)
                        else:
                            continue
                    
                    if anchor_blob:
                        reference_images.append({
                            "referenceType": "asset",
                            "image": {"bytesBase64Encoded": anchor_blob, "mimeType": "image/jpeg"},
                            "weight": 0.8  # High confidence for identity
                        })

        # C. THE FLOW (Temporal Continuity)
        if state.last_frame_path:
            # Download from S3 if it's an s3:// URI
            if state.last_frame_path.startswith("s3://"):
                flow_blob = self._load_image_from_s3(state.last_frame_path)
            else:
                # Legacy local file support
                import os
                if os.path.exists(state.last_frame_path):
                    flow_blob = self._load_image_as_base64(state.last_frame_path)
                else:
                    flow_blob = None
            
            if flow_blob:
                reference_images.append({
                    "referenceType": "asset",
                    "image": {"bytesBase64Encoded": flow_blob, "mimeType": "image/jpeg"},
                    "weight": 0.5  # Medium confidence for motion/lighting
                })

        # --- RUNWAY LIMITATION: Merge multiple reference images into one ---
        if is_runway and len(reference_images) > 1:
            print(f"[Runway] Merging {len(reference_images)} reference images into composite...")
            
            # Extract all image bytes
            image_bytes_list = []
            for ref in reference_images:
                if "image" in ref and "bytesBase64Encoded" in ref["image"]:
                    img_bytes = base64.b64decode(ref["image"]["bytesBase64Encoded"])
                    image_bytes_list.append(img_bytes)
            
            # Create composite
            if image_bytes_list:
                composite_bytes = create_composite_image(image_bytes_list)
                composite_base64 = base64.b64encode(composite_bytes).decode()
                
                # Replace all references with single composite
                reference_images = [{
                    "referenceType": "asset",
                    "image": {"bytesBase64Encoded": composite_base64, "mimeType": "image/jpeg"},
                    "weight": 1.0  # Runway doesn't support weights
                }]
                print(f"[Runway] Using composite image with {len(image_bytes_list)} merged sources")

        # --- 2. Enhance Prompt (Path A Logic) ---
        final_prompt = f"{prompt}. Style: Consistent with previous shots."
        
        # Inject Factual Narrative Context
        if state.narrative_context:
            narrative_lines = []
            for key, value in state.narrative_context.items():
                narrative_lines.append(f"{key.replace('_', ' ').title()}: {value}.")

            final_prompt += "\n\nNARRATIVE FACTS TO ENFORCE:\n"
            final_prompt += " ".join(narrative_lines)

        # --- 3. Call Video Service (Google Veo or Runway) ---
        print(f"DEBUG: Generating with {model} using {len(reference_images)} refs ({len(active_ids)} anchors + flow)")
        print(f"DEBUG: Narrative context: {state.narrative_context}")
        video_bytes = video_service.generate_video(
            prompt=final_prompt,
            reference_images=reference_images if reference_images else None
        )
        
        return video_bytes

    def _load_image_as_base64(self, path: str) -> str:
        """Load image from local file system (legacy support)."""
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    
    def _load_image_from_s3(self, s3_uri: str) -> str:
        """Load image from S3 and return as base64."""
        image_bytes = download_from_uri(s3_uri)
        return base64.b64encode(image_bytes).decode()
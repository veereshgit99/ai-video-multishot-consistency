# backend/app/services/continuity/continuity_engine.py

from sqlalchemy.orm import Session
from app import models
from app.services.video.google_flow import GoogleFlowVideoService
import base64
import json
import os

class ContinuityEngine:
    
    def __init__(self):
        self.video_service = GoogleFlowVideoService()

    def get_or_create_state(self, db: Session, project_id: int, session_id: str = None):
        state = db.query(models.ContinuityState).filter_by(project_id=project_id).first()
        if not state:
            state = models.ContinuityState(project_id=project_id, session_id=session_id or f"session_{project_id}")
            db.add(state)
            db.commit()
        return state

    def generate_segment(self, db: Session, project_id: int, prompt: str, session_id: str = None):
        """
        The Core Logic: Multi-Anchor + Flow Generation (Path A + Path C)
        """
        state = self.get_or_create_state(db, project_id, session_id)
        
        # --- 1. Build Reference Images (The "Anchor + Flow" Strategy) ---
        reference_images = []

        # A. MULTI-ANCHOR CHARACTERS (Path C Logic)
        active_ids = json.loads(state.active_character_ids or "[]")
        
        for char_id in active_ids:
            char = db.query(models.Character).get(char_id)
            if char and hasattr(char, 'ref_image_path') and char.ref_image_path:
                if os.path.exists(char.ref_image_path):
                    # Character Anchors get a high, consistent weight
                    # NOTE: We use the raw image even if DNA hasn't been extracted yet
                    # The background worker will populate embeddings for future use
                    anchor_blob = self._load_image_as_base64(char.ref_image_path)
                    reference_images.append({
                        "referenceType": "asset",
                        "image": {"bytesBase64Encoded": anchor_blob, "mimeType": "image/jpeg"},
                        "weight": 0.8  # High confidence for identity
                    })

        # B. THE FLOW (Temporal Continuity)
        if state.last_frame_path and os.path.exists(state.last_frame_path):
            flow_blob = self._load_image_as_base64(state.last_frame_path)
            reference_images.append({
                "referenceType": "asset",
                "image": {"bytesBase64Encoded": flow_blob, "mimeType": "image/jpeg"},
                "weight": 0.5  # Medium confidence for motion/lighting
            })

        # --- 2. Enhance Prompt (Path A Logic) ---
        final_prompt = f"{prompt}. Style: Consistent with previous shots."
        
        # Inject Factual Narrative Context
        if state.narrative_context:
            narrative_lines = []
            for key, value in state.narrative_context.items():
                narrative_lines.append(f"{key.replace('_', ' ').title()}: {value}.")

            final_prompt += "\n\nNARRATIVE FACTS TO ENFORCE:\n"
            final_prompt += " ".join(narrative_lines)

        # --- 3. Call Veo ---
        print(f"DEBUG: Generating with {len(reference_images)} refs ({len(active_ids)} anchors + flow)")
        print(f"DEBUG: Narrative context: {state.narrative_context}")
        video_bytes = self.video_service.generate_video(
            prompt=final_prompt,
            reference_images=reference_images if reference_images else None
        )
        
        return video_bytes

    def _load_image_as_base64(self, path: str) -> str:
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode()
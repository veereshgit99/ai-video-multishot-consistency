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

    def generate_segment(self, db: Session, project_id: int, prompt: str, session_id: str = None, raw_image_ref: dict = None, model: str = "veo-2.0", continue_from_shot: int = None):
        """
        Multi-Model Video Generation with Separate Strategies:
        - Veo 2.0/Seedance: Multi-anchor (character DNA 0.8 + flow 0.5) for character consistency
        - Veo 3.1/Seedance Pro/Seedance Pro Fast: Text-only (prompt enhancement, no images)
        - Runway/MiniMax: Flow-only (last frame) for temporal continuity
        
        Args:
            raw_image_ref: Optional pre-built reference image dict for first-shot scenarios.
            model: Video model to use ("veo-2.0", "veo-3.1", "gen4_turbo", "minimax", "seedance", "seedance-pro-fast", "seedance-pro")
            continue_from_shot: Optional shot index to continue from (enables branching)
        """
        from app.services.video.base import get_video_service
        
        # Create video service based on model selection
        video_service = get_video_service(model)
        is_veo_2 = model == "veo-2.0"
        is_veo_3 = model == "veo-3.1"
        is_seedance = model == "seedance"
        is_seedance_pro_fast = model == "seedance-pro-fast"
        is_seedance_pro = model == "seedance-pro"
        is_runway = model.startswith("gen4") or model == "runway"
        is_minimax = model == "minimax" or model.startswith("MiniMax")
        state = self.get_or_create_state(db, project_id, session_id)
        
        # Route to appropriate generation strategy
        # Veo 3.1 / Seedance Pro / Seedance Pro Fast: Text-only (ignore reference images, use prompt enhancement only)
        if is_veo_3 or is_seedance_pro_fast or is_seedance_pro:
            final_prompt = self._enhance_prompt(prompt, state)
            video_bytes = video_service.generate_video(prompt=final_prompt, reference_images=None)
            return video_bytes
        
        # Veo 2.0 and Seedance: Multi-anchor strategy (character DNA + flow)
        elif is_veo_2 or is_seedance:
            model_name = "Seedance" if is_seedance else "Veo"
            return self._generate_multi_anchor_segment(db, video_service, state, project_id, prompt, raw_image_ref, model_name, continue_from_shot)
        elif is_runway or is_minimax:
            model_name = "MiniMax" if is_minimax else "Runway"
            return self._generate_flow_only_segment(db, video_service, state, project_id, prompt, raw_image_ref, model_name, continue_from_shot)
        else:
            raise ValueError(f"Unknown model: {model}")
    
    def _generate_multi_anchor_segment(self, db: Session, video_service, state, project_id: int, prompt: str, raw_image_ref: dict = None, model_name: str = "Veo", continue_from_shot: int = None):
        """
        Multi-Anchor Generation: For Veo and Seedance
        Uses character DNA anchors (0.8 weight) + flow frame (0.5 weight)
        Both models support 1-4 reference images natively.
        """
        reference_images = []

        # A. FIRST-SHOT RAW IMAGE
        if raw_image_ref:
            reference_images.append(raw_image_ref)
            print(f"[{model_name.upper()} FIRST-SHOT] Using raw uploaded image (weight 1.0)")
        
        # B. MULTI-ANCHOR CHARACTERS (Continuation Shots)
        active_ids = json.loads(state.active_character_ids or "[]")
        
        if not raw_image_ref:
            for char_id in active_ids:
                char = db.query(models.Character).get(char_id)
                if char and hasattr(char, 'ref_image_path') and char.ref_image_path:
                    if char.ref_image_path.startswith("s3://"):
                        anchor_blob = self._load_image_from_s3(char.ref_image_path)
                    else:
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

        # C. FLOW (Temporal Continuity) - support branching from specific shot
        flow_frame_path = self._get_flow_frame_path(db, state, project_id, continue_from_shot)
        
        if flow_frame_path:
            if flow_frame_path.startswith("s3://"):
                flow_blob = self._load_image_from_s3(flow_frame_path)
            else:
                import os
                if os.path.exists(flow_frame_path):
                    flow_blob = self._load_image_as_base64(flow_frame_path)
                else:
                    flow_blob = None
            
            if flow_blob:
                reference_images.append({
                    "referenceType": "asset",
                    "image": {"bytesBase64Encoded": flow_blob, "mimeType": "image/jpeg"},
                    "weight": 0.5  # Medium confidence for motion/lighting
                })

        # Enhance Prompt with Narrative Context
        final_prompt = self._enhance_prompt(prompt, state)
        
        # Call Video Service (Veo or Seedance)
        active_ids = json.loads(state.active_character_ids or "[]")
        print(f"[{model_name.upper()}] Generating with {len(reference_images)} refs ({len(active_ids)} character anchors + flow)")
        video_bytes = video_service.generate_video(
            prompt=final_prompt,
            reference_images=reference_images if reference_images else None
        )
        
        return video_bytes
    
    def _generate_flow_only_segment(self, db: Session, video_service, state, project_id: int, prompt: str, raw_image_ref: dict = None, model_name: str = "Runway", continue_from_shot: int = None):
        """
        Runway/MiniMax Generation: Flow-Only Strategy
        Prioritizes temporal continuity over character anchors.
        Uses ONLY last frame for continuation (no character DNA injection).
        """
        reference_images = []

        # A. FIRST-SHOT RAW IMAGE
        if raw_image_ref:
            reference_images.append(raw_image_ref)
            print(f"[{model_name} FIRST-SHOT] Using raw uploaded image (weight 1.0)")
        
        # B. FLOW-ONLY CONTINUATION (No character anchors) - support branching
        elif True:  # Always check for flow frame in continuation
            flow_frame_path = self._get_flow_frame_path(db, state, project_id, continue_from_shot)
            
            if flow_frame_path:
                if flow_frame_path.startswith("s3://"):
                    flow_blob = self._load_image_from_s3(flow_frame_path)
                else:
                    import os
                    if os.path.exists(flow_frame_path):
                        flow_blob = self._load_image_as_base64(flow_frame_path)
                    else:
                        flow_blob = None
                
                if flow_blob:
                    reference_images.append({
                        "referenceType": "asset",
                        "image": {"bytesBase64Encoded": flow_blob, "mimeType": "image/jpeg"},
                        "weight": 1.0  # Full weight on flow for temporal continuity
                    })
                    shot_info = f" from shot #{continue_from_shot}" if continue_from_shot else ""
                    print(f"[{model_name} CONTINUATION] Using flow-only{shot_info} (last frame, weight 1.0)")
        
        # Enhance Prompt with Narrative Context
        final_prompt = self._enhance_prompt(prompt, state)
        
        # Call Video Service
        print(f"[{model_name}] Generating with {len(reference_images)} ref (flow-only strategy)")
        video_bytes = video_service.generate_video(
            prompt=final_prompt,
            reference_images=reference_images if reference_images else None
        )
        
        return video_bytes
    
    def _enhance_prompt(self, prompt: str, state) -> str:
        """Add narrative context to prompt."""
        final_prompt = f"{prompt}. Style: Consistent with previous shots."
        
        if state.narrative_context:
            narrative_lines = []
            for key, value in state.narrative_context.items():
                narrative_lines.append(f"{key.replace('_', ' ').title()}: {value}.")

            final_prompt += "\n\nNARRATIVE FACTS TO ENFORCE:\n"
            final_prompt += " ".join(narrative_lines)
        
        return final_prompt
    
    def _get_flow_frame_path(self, db: Session, state, project_id: int, continue_from_shot: int = None) -> str:
        """
        Get the flow frame path for continuation.
        If continue_from_shot is specified, retrieve that shot's last frame.
        Otherwise, use the most recent shot's last frame from state.
        """
        if continue_from_shot is not None:
            # Branch from specific shot
            shot = db.query(models.Shot).filter(
                models.Shot.project_id == project_id,
                models.Shot.index == continue_from_shot
            ).first()
            
            if shot and shot.last_frame_path:
                print(f"[BRANCHING] Using shot #{continue_from_shot} last frame: {shot.last_frame_path}")
                return shot.last_frame_path
            else:
                print(f"[WARNING] Shot #{continue_from_shot} not found or has no last frame, using default")
        
        # Default: use most recent shot's last frame from state
        return state.last_frame_path

    def _load_image_as_base64(self, path: str) -> str:
        """Load image from local file system (legacy support)."""
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    
    def _load_image_from_s3(self, s3_uri: str) -> str:
        """Load image from S3 and return as base64."""
        image_bytes = download_from_uri(s3_uri)
        return base64.b64encode(image_bytes).decode()
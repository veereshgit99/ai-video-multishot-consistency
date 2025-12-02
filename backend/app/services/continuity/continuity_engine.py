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

    def generate_segment(self, db: Session, project_id: int, prompt: str, session_id: str = None, raw_image_refs: list = None, model: str = "veo-2.0", continue_from_shot: int = None, duration: int = None):
        """
        Multi-Model Video Generation with Separate Strategies:
        - Veo 2.0/Seedance: Multi-anchor (user raw refs + character DNA 0.8 + flow 0.5) for character consistency
        - Veo 3.1/Seedance Pro/Seedance Pro Fast/Kling Text: Text-only (prompt enhancement, no images)
        - Runway/MiniMax/Kling Image: Flow-only (last frame) for temporal continuity
        
        Args:
            raw_image_refs: Optional list of pre-built reference image dicts with user-specified weights
            model: Video model to use ("veo-2.0", "veo-3.1", "gen4_turbo", "minimax", "seedance", "seedance-pro-fast", "seedance-pro", "kling-2.5-turbo-pro-image", "kling-2.5-turbo-pro-text")
            continue_from_shot: Optional shot index to continue from (enables branching)
            duration: Optional duration in seconds (only for Seedance/Kling, defaults: Seedance=6s, Kling=5s)
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
        is_kling_image = model == "kling-2.5-turbo-pro-image"
        is_kling_text = model == "kling-2.5-turbo-pro-text"
        state = self.get_or_create_state(db, project_id, session_id)
        
        # Route to appropriate generation strategy
        # Veo 3.1 / Seedance Pro / Seedance Pro Fast / Kling Text: Text-only (ignore reference images, use prompt enhancement only)
        if is_veo_3 or is_seedance_pro_fast or is_seedance_pro or is_kling_text:
            final_prompt = self._enhance_prompt(prompt, state)
            # Pass duration only for Seedance/Kling models
            if duration and (is_seedance_pro_fast or is_seedance_pro or is_kling_text):
                video_bytes = video_service.generate_video(prompt=final_prompt, reference_images=None, duration=duration)
            else:
                video_bytes = video_service.generate_video(prompt=final_prompt, reference_images=None)
            return video_bytes
        
        # Veo 2.0 and Seedance: Multi-anchor strategy (character DNA + flow)
        elif is_veo_2 or is_seedance:
            model_name = "Seedance" if is_seedance else "Veo"
            return self._generate_multi_anchor_segment(db, video_service, state, project_id, prompt, raw_image_refs, model_name, continue_from_shot, duration)
        elif is_runway or is_minimax or is_kling_image:
            model_name = "MiniMax" if is_minimax else ("Kling" if is_kling_image else "Runway")
            return self._generate_flow_only_segment(db, video_service, state, project_id, prompt, raw_image_refs, model_name, continue_from_shot, duration)
        else:
            raise ValueError(f"Unknown model: {model}")
    
    def _generate_multi_anchor_segment(self, db: Session, video_service, state, project_id: int, prompt: str, raw_image_refs: list = None, model_name: str = "Veo", continue_from_shot: int = None, duration: int = None):
        """
        Multi-Anchor Generation: For Veo and Seedance
        Builds weighted reference list:
        1. User raw references (user-specified weights, typically 0.9-1.0 for characters, 0.6-0.7 for props)
        2. Stored character DNA anchors (0.8 weight - allows slight drift)
        3. Flow frame from last shot (0.5 weight - temporal continuity)
        Both models support 1-4 reference images natively.
        """
        reference_images = []

        # A. USER RAW IMAGE REFERENCES (with user-specified weights)
        has_end_frame = False
        end_frame_ref = None
        start_and_other_refs = []
        
        if raw_image_refs:
            # Separate end frame from other references
            for ref in raw_image_refs:
                if ref.get("is_end_frame"):
                    has_end_frame = True
                    end_frame_ref = ref
                else:
                    start_and_other_refs.append(ref)
            
            # Add start/other frames first
            reference_images.extend(start_and_other_refs)
            print(f"[{model_name.upper()}] Added {len(start_and_other_refs)} user raw reference(s) with custom weights")
            
            if has_end_frame:
                print(f"[{model_name.upper()}] End frame detected - will position as LAST reference")
        
        # B. STORED CHARACTER DNA ANCHORS (0.8 weight - for continuation shots)
        active_ids = json.loads(state.active_character_ids or "[]")
        
        # Only add character DNA if no raw refs (avoid duplication)
        if not start_and_other_refs and not has_end_frame and active_ids:
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

        # D. ADD END FRAME AS LAST REFERENCE (if provided)
        # This ensures the model sees it in a consistent position
        if has_end_frame and end_frame_ref:
            reference_images.append(end_frame_ref)
            print(f"[{model_name.upper()}] Added end frame as LAST reference (position #{len(reference_images)})")

        # Enhance Prompt with Narrative Context
        final_prompt = self._enhance_prompt(prompt, state)
        
        # Add end frame instruction if detected - specify exact position
        if has_end_frame:
            total_refs = len(reference_images)
            final_prompt += f"\n\nCRITICAL INSTRUCTION: Reference image #{total_refs} (THE LAST ONE) is the TARGET END FRAME showing exactly how this shot must end. Animate a smooth transition from the starting state to precisely match that final reference image's pose, composition, camera angle, and positioning. The last moment of the video must look identical to reference image #{total_refs}."
        
        # Call Video Service (Veo or Seedance)
        active_ids = json.loads(state.active_character_ids or "[]")
        print(f"[{model_name.upper()}] Generating with {len(reference_images)} refs ({len(active_ids)} character anchors + flow)")
        # Pass duration only for Seedance
        if duration and model_name == "Seedance":
            video_bytes = video_service.generate_video(
                prompt=final_prompt,
                reference_images=reference_images if reference_images else None,
                duration=duration
            )
        else:
            video_bytes = video_service.generate_video(
                prompt=final_prompt,
                reference_images=reference_images if reference_images else None
            )
        
        return video_bytes
    
    def _generate_flow_only_segment(self, db: Session, video_service, state, project_id: int, prompt: str, raw_image_refs: list = None, model_name: str = "Runway", continue_from_shot: int = None, duration: int = None):
        """
        Runway/MiniMax/Kling Generation: Flow-Only Strategy
        Prioritizes temporal continuity over character anchors.
        Uses ONLY last frame for continuation (no character DNA injection).
        Kling is ideal for cinematic camera moves and fluid motion.
        If user provides raw_image_refs, uses first one only (flow-only models = single image).
        
        For Kling: Supports tail_image_url (end frame) for start->end animation.
        """
        reference_images = []
        tail_image_url = None  # For Kling end frame

        # A. USER RAW IMAGE REFERENCE (detect start and end frames)
        if raw_image_refs and len(raw_image_refs) > 0:
            start_frame = None
            end_frame = None
            
            # Separate start and end frames
            for ref in raw_image_refs:
                if ref.get("is_end_frame"):
                    end_frame = ref
                else:
                    start_frame = ref
            
            # Add start frame to reference list
            if start_frame:
                reference_images.append(start_frame)
                print(f"[{model_name}] Using user raw reference as start frame")
            
            # Handle end frame (Kling only)
            if end_frame and model_name == "Kling":
                # For Kling, we need to upload the end frame and get URL
                # Extract image data and prepare for tail_image_url
                if "image" in end_frame and "bytesBase64Encoded" in end_frame["image"]:
                    # We need to upload this to fal.ai storage
                    # For now, we'll use the _prepare_image helper (same as start frame)
                    # This will be passed as tail_image_url parameter
                    tail_image_url = self._prepare_tail_image_for_kling(end_frame, video_service)
                    print(f"[{model_name}] Using end frame for start->end animation (tail_image_url)")
            elif end_frame and model_name != "Kling":
                print(f"[{model_name}] WARNING: End frame provided but {model_name} doesn't support tail images. Ignoring.")
            
            # Warn if multiple non-end-frame images provided
            non_end_frames = [r for r in raw_image_refs if not r.get("is_end_frame")]
            if len(non_end_frames) > 1:
                print(f"[{model_name}] WARNING: Flow-only model ignoring {len(non_end_frames)-1} additional reference(s)")
        
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
        
        # Generate Video (Flow-Only)
        print(f"[{model_name}] Generating flow-only with {len(reference_images)} reference(s)")
        # Pass duration only for Kling
        if duration and model_name == "Kling":
            video_bytes = video_service.generate_video(
                prompt=final_prompt,
                reference_images=reference_images if reference_images else None,
                duration=duration,
                tail_image_url=tail_image_url  # Pass end frame URL for Kling
            )
        elif model_name == "Kling" and tail_image_url:
            # Kling with tail image but no custom duration
            video_bytes = video_service.generate_video(
                prompt=final_prompt,
                reference_images=reference_images if reference_images else None,
                tail_image_url=tail_image_url
            )
        else:
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
    
    def _prepare_tail_image_for_kling(self, end_frame_ref: dict, video_service) -> str:
        """
        Prepare end frame for Kling's tail_image_url parameter.
        Delegates to Kling service's _prepare_image method.
        """
        if hasattr(video_service, '_prepare_image'):
            return video_service._prepare_image(end_frame_ref)
        else:
            raise ValueError("Video service does not support tail image preparation")
"""
Kling Video v2.5 Turbo Pro Image-to-Video Service via fal.ai

Kling 2.5 Turbo Pro is an image-to-video model:
- Single image input (flow-only strategy)
- Top-tier motion fluidity and cinematic visuals
- Better for camera moves and cinematic motion
- 5 or 10 second duration support

API: fal-ai/kling-video/v2.5-turbo/pro/image-to-video
Docs: https://fal.ai/models/fal-ai/kling-video/v2.5-turbo/pro/image-to-video/api
"""

import os
import requests
from typing import Optional, List, Dict
from app.services.video.base import BaseVideoService
import fal_client


class KlingVideoService(BaseVideoService):
    
    def __init__(self):
        self.api_key = os.getenv("FAL_API_KEY")
        if not self.api_key:
            raise ValueError("FAL_API_KEY not found in environment variables")
        
        # Set FAL_KEY for fal_client library
        os.environ["FAL_KEY"] = self.api_key
        
        self.endpoint = "fal-ai/kling-video/v2.5-turbo/pro/image-to-video"
    
    def generate_video(
        self,
        prompt: str,
        reference_images: Optional[List[Dict]] = None,
        duration: int = 8,
        negative_prompt: str = "blur, distort, and low quality",
        cfg_scale: float = 0.5,
        num_frames: int = 60
    ) -> bytes:
        """
        Generate video using Kling v2.5 Turbo Pro (image-to-video).
        
        Args:
            prompt: Text description for video generation
            reference_images: Single image in Veo format (base64)
                             Only first image is used (Kling supports single image only)
            duration: Video duration in seconds (5 or 10, default: 10)
            negative_prompt: Things to avoid in generation
            cfg_scale: Classifier Free Guidance scale (0-1, default: 0.5)
            num_frames: Ignored (kept for interface compatibility)
        
        Returns:
            Video bytes
        """
        # Extract first reference image
        if not reference_images or len(reference_images) == 0:
            raise ValueError("[KLING] At least one reference image required for image-to-video generation")
        
        # Kling only supports single image
        if len(reference_images) > 1:
            print(f"[KLING] WARNING: Kling supports single image only, using first image (ignoring {len(reference_images)-1} others)")
        
        # Upload image to fal.ai storage
        image_url = self._prepare_image(reference_images[0])
        
        # Ensure duration is valid (5 or 10)
        if duration not in [5, 10]:
            print(f"[KLING] WARNING: Duration must be 5 or 10, got {duration}. Using 10.")
            duration = 10
        
        # Build request payload
        payload = {
            "prompt": prompt,
            "image_url": image_url,
            "duration": str(duration),  # API expects string
            "negative_prompt": negative_prompt,
            "cfg_scale": cfg_scale
        }
        
        print(f"[KLING] Generating video with single image")
        print(f"[KLING] Duration: {duration}s, CFG Scale: {cfg_scale}")
        
        # Submit request to queue
        video_url = self._submit_and_wait(payload)
        
        # Download video from result URL
        print(f"[KLING] Downloading video from: {video_url}")
        response = requests.get(video_url, timeout=120)
        response.raise_for_status()
        
        return response.content
    
    def _prepare_image(self, reference_image: Dict) -> str:
        """
        Convert Veo-format reference image to URL for Kling.
        
        Veo format: {"image": {"bytesBase64Encoded": "...", "mimeType": "..."}, "weight": 0.8}
        Kling format: URL string
        
        Strategy: Upload base64 image to fal.ai storage, get URL
        """
        try:
            # Extract base64 data
            if "image" not in reference_image or "bytesBase64Encoded" not in reference_image["image"]:
                raise ValueError("Reference image missing base64 data")
            
            base64_data = reference_image["image"]["bytesBase64Encoded"]
            mime_type = reference_image["image"].get("mimeType", "image/jpeg")
            
            # Upload to fal.ai storage
            url = self._upload_to_fal_storage(base64_data, mime_type)
            
            print(f"[KLING] Uploaded reference image (weight: {reference_image.get('weight', 1.0)})")
            return url
            
        except Exception as e:
            raise Exception(f"[KLING ERROR] Failed to upload reference image: {e}")
    
    def _upload_to_fal_storage(self, base64_data: str, mime_type: str) -> str:
        """
        Upload base64 image to fal.ai storage using official client.
        """
        import base64
        import tempfile
        
        # Decode base64 to bytes
        image_bytes = base64.b64decode(base64_data)
        
        # Write to temp file
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            tmp.write(image_bytes)
            tmp_path = tmp.name
        
        try:
            # Upload using fal_client
            file_url = fal_client.upload_file(tmp_path)
            return file_url
        finally:
            # Cleanup
            try:
                os.unlink(tmp_path)
            except:
                pass
    
    def _submit_and_wait(self, payload: dict) -> str:
        """
        Submit request to Kling using official fal_client.
        
        Returns:
            Video URL from result
        """
        print(f"[KLING] Submitting request via fal_client...")
        print(f"[KLING] Waiting for video generation (this may take 2-3 minutes)...")
        
        # Use fal_client.subscribe for queue-based API
        result = fal_client.subscribe(
            self.endpoint,
            arguments=payload
        )
        
        video_url = result["video"]["url"]
        
        print(f"[KLING] Video generated successfully!")
        return video_url

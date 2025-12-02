"""
Seedance 1.0 Lite Video Generation Service via fal.ai

Seedance supports 1-4 reference images natively, making it perfect for:
- Multi-anchor character consistency (character DNA + flow)
- Better than single-image models (Runway/MiniMax)
- Comparable to Veo but potentially cheaper/faster

API: fal-ai/bytedance/seedance/v1/lite/reference-to-video
Docs: https://fal.ai/models/fal-ai/bytedance/seedance/v1/lite/reference-to-video/api
"""

import os
import requests
from typing import Optional, List, Dict
from app.services.video.base import BaseVideoService
import fal_client


class SeedanceVideoService(BaseVideoService):
    
    def __init__(self):
        self.api_key = os.getenv("FAL_API_KEY")
        if not self.api_key:
            raise ValueError("FAL_API_KEY not found in environment variables")
        
        # Set FAL_KEY for fal_client library
        os.environ["FAL_KEY"] = self.api_key
        
        self.endpoint = "fal-ai/bytedance/seedance/v1/lite/reference-to-video"
        self.base_url = "https://queue.fal.run"
    
    def generate_video(
        self,
        prompt: str,
        reference_images: Optional[List[Dict]] = None,
        duration: int = 6,
        resolution: str = "720p",
        aspect_ratio: str = "auto",
        seed: int = -1,
        camera_fixed: bool = False,
        num_frames: int = 60
    ) -> bytes:
        """
        Generate video using Seedance with 1-4 reference images.
        
        Args:
            prompt: Text description for video generation
            reference_images: List of reference image dicts (Veo format with base64)
                             Seedance supports 1-4 images natively!
            duration: Video duration in seconds (2-12, default: 6)
            resolution: "480p" or "720p" (default: 720p)
            aspect_ratio: "21:9", "16:9", "4:3", "1:1", "3:4", "9:16", "auto"
            seed: Random seed (-1 for random)
            camera_fixed: Whether to fix camera position
            num_frames: Ignored (kept for interface compatibility)
        
        Returns:
            Video bytes
        """
        # Convert reference images from Veo format to Seedance format
        reference_urls = self._prepare_reference_images(reference_images)
        
        if not reference_urls:
            print("[SEEDANCE WARNING] No reference images provided - generating from prompt only")
        
        # Validate we don't exceed 4 image limit
        if len(reference_urls) > 4:
            print(f"[SEEDANCE WARNING] Seedance supports max 4 reference images, got {len(reference_urls)}. Using first 4.")
            reference_urls = reference_urls[:4]
        
        # Build request payload
        payload = {
            "prompt": prompt,
            "reference_image_urls": reference_urls,
            "duration": str(duration),  # API expects string
            "resolution": resolution,
            "aspect_ratio": aspect_ratio,
            "seed": seed,
            "camera_fixed": camera_fixed,
            "enable_safety_checker": True
        }
        
        print(f"[SEEDANCE] Generating video with {len(reference_urls)} reference images")
        print(f"[SEEDANCE] Duration: {duration}s, Resolution: {resolution}")
        
        # Submit request to queue
        video_url = self._submit_and_wait(payload)
        
        # Download video from result URL
        print(f"[SEEDANCE] Downloading video from: {video_url}")
        response = requests.get(video_url, timeout=120)
        response.raise_for_status()
        
        return response.content
    
    def _prepare_reference_images(self, reference_images: Optional[List[Dict]]) -> List[str]:
        """
        Convert Veo-format reference images to Seedance format.
        
        Veo format: [{"image": {"bytesBase64Encoded": "...", "mimeType": "..."}, "weight": 0.8}]
        Seedance format: ["https://url1", "https://url2", ...]
        
        Strategy: Upload base64 images to fal.ai storage, get URLs
        """
        if not reference_images:
            return []
        
        reference_urls = []
        
        for idx, ref in enumerate(reference_images):
            try:
                # Extract base64 data
                if "image" not in ref or "bytesBase64Encoded" not in ref["image"]:
                    print(f"[SEEDANCE WARNING] Reference image {idx} missing base64 data, skipping")
                    continue
                
                base64_data = ref["image"]["bytesBase64Encoded"]
                mime_type = ref["image"].get("mimeType", "image/jpeg")
                
                # Upload to fal.ai storage
                url = self._upload_to_fal_storage(base64_data, mime_type)
                reference_urls.append(url)
                
                print(f"[SEEDANCE] Uploaded reference image {idx+1} (weight: {ref.get('weight', 1.0)})")
                
            except Exception as e:
                print(f"[SEEDANCE ERROR] Failed to upload reference image {idx}: {e}")
                continue
        
        return reference_urls
    
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
        Submit request to Seedance using official fal_client.
        
        Returns:
            Video URL from result
        """
        print(f"[SEEDANCE] Submitting request via fal_client...")
        print(f"[SEEDANCE] Waiting for video generation (this may take 2-3 minutes)...")
        
        # Use fal_client.subscribe for queue-based API
        result = fal_client.subscribe(
            self.endpoint,
            arguments=payload
        )
        
        video_url = result["video"]["url"]
        seed_used = result.get("seed")
        
        print(f"[SEEDANCE] Video generated successfully! Seed: {seed_used}")
        return video_url

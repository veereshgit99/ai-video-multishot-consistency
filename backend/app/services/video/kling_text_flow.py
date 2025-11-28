"""
Kling Video v2.5 Turbo Pro Text-to-Video Service via fal.ai

Kling 2.5 Turbo Pro Text-to-Video is a pure text-to-video model:
- NO image input (text-only generation)
- Top-tier motion fluidity and cinematic visuals
- Exceptional prompt precision
- Best for first shots or creative generation

API: fal-ai/kling-video/v2.5-turbo/pro/text-to-video
Docs: https://fal.ai/models/fal-ai/kling-video/v2.5-turbo/pro/text-to-video/api
"""

import os
import requests
from typing import Optional, List, Dict
from app.services.video.base import BaseVideoService
import fal_client


class KlingTextVideoService(BaseVideoService):
    
    def __init__(self):
        self.api_key = os.getenv("FAL_API_KEY")
        if not self.api_key:
            raise ValueError("FAL_API_KEY not found in environment variables")
        
        # Set FAL_KEY for fal_client library
        os.environ["FAL_KEY"] = self.api_key
        
        self.endpoint = "fal-ai/kling-video/v2.5-turbo/pro/text-to-video"
    
    def generate_video(
        self,
        prompt: str,
        reference_images: Optional[List[Dict]] = None,
        duration: int = 10,
        aspect_ratio: str = "16:9",
        negative_prompt: str = "blur, distort, and low quality",
        cfg_scale: float = 0.5,
        num_frames: int = 60
    ) -> bytes:
        """
        Generate video using Kling v2.5 Turbo Pro (text-to-video ONLY).
        
        Args:
            prompt: Text description for video generation
            reference_images: IGNORED (text-to-video does not accept images)
            duration: Video duration in seconds (5 or 10, default: 10)
            aspect_ratio: "16:9", "9:16", or "1:1" (default: 16:9)
            negative_prompt: Things to avoid in generation
            cfg_scale: Classifier Free Guidance scale (0-1, default: 0.5)
            num_frames: Ignored (kept for interface compatibility)
        
        Returns:
            Video bytes
        """
        # Warn if reference images are provided (they will be ignored)
        if reference_images:
            print(f"[KLING TEXT] WARNING: Text-to-video model does not use reference images (ignoring {len(reference_images)} images)")
        
        # Ensure duration is valid (5 or 10)
        if duration not in [5, 10]:
            print(f"[KLING TEXT] WARNING: Duration must be 5 or 10, got {duration}. Using 10.")
            duration = 10
        
        # Validate aspect ratio
        valid_ratios = ["16:9", "9:16", "1:1"]
        if aspect_ratio not in valid_ratios:
            print(f"[KLING TEXT] WARNING: Invalid aspect ratio {aspect_ratio}. Using 16:9.")
            aspect_ratio = "16:9"
        
        # Build request payload
        payload = {
            "prompt": prompt,
            "duration": str(duration),  # API expects string
            "aspect_ratio": aspect_ratio,
            "negative_prompt": negative_prompt,
            "cfg_scale": cfg_scale
        }
        
        print(f"[KLING TEXT] Generating text-to-video")
        print(f"[KLING TEXT] Duration: {duration}s, Aspect Ratio: {aspect_ratio}, CFG Scale: {cfg_scale}")
        
        # Submit request to queue
        video_url = self._submit_and_wait(payload)
        
        # Download video from result URL
        print(f"[KLING TEXT] Downloading video from: {video_url}")
        response = requests.get(video_url, timeout=120)
        response.raise_for_status()
        
        return response.content
    
    def _submit_and_wait(self, payload: dict) -> str:
        """
        Submit request to Kling using official fal_client.
        
        Returns:
            Video URL from result
        """
        print(f"[KLING TEXT] Submitting request via fal_client...")
        print(f"[KLING TEXT] Waiting for video generation (this may take 2-3 minutes)...")
        
        # Use fal_client.subscribe for queue-based API
        result = fal_client.subscribe(
            self.endpoint,
            arguments=payload
        )
        
        video_url = result["video"]["url"]
        
        print(f"[KLING TEXT] Video generated successfully!")
        return video_url

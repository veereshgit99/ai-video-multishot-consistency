"""
Seedance 1.0 Pro Fast Text-to-Video Service via fal.ai

Seedance Pro Fast is a text-to-video model (NO reference images):
- Text-only generation (like Veo 3.1)
- For first shot only (no continuation)
- Cheaper alternative to Veo 3.1
- Supports up to 1080p resolution

API: fal-ai/bytedance/seedance/v1/pro/fast/text-to-video
Docs: https://fal.ai/models/fal-ai/bytedance/seedance/v1/pro/fast/text-to-video/api
"""

import os
import requests
from typing import Optional, List, Dict
from app.services.video.base import BaseVideoService
import fal_client


class SeedanceProFastVideoService(BaseVideoService):
    
    def __init__(self):
        self.api_key = os.getenv("FAL_API_KEY")
        if not self.api_key:
            raise ValueError("FAL_API_KEY not found in environment variables")
        
        # Set FAL_KEY for fal_client library
        os.environ["FAL_KEY"] = self.api_key
        
        self.endpoint = "fal-ai/bytedance/seedance/v1/pro/fast/text-to-video"
    
    def generate_video(
        self,
        prompt: str,
        reference_images: Optional[List[Dict]] = None,
        duration: int = 6,
        resolution: str = "1080p",
        aspect_ratio: str = "16:9",
        seed: int = -1,
        camera_fixed: bool = False,
        num_frames: int = 60
    ) -> bytes:
        """
        Generate video using Seedance Pro Fast (text-to-video ONLY).
        
        Args:
            prompt: Text description for video generation
            reference_images: IGNORED - this model is text-only
            duration: Video duration in seconds (2-12, default: 6)
            resolution: "480p", "720p", or "1080p" (default: 1080p)
            aspect_ratio: "21:9", "16:9", "4:3", "1:1", "3:4", "9:16" (default: 16:9)
            seed: Random seed (-1 for random)
            camera_fixed: Whether to fix camera position
            num_frames: Ignored (kept for interface compatibility)
        
        Returns:
            Video bytes
        """
        # Ignore reference images - this is text-to-video only
        if reference_images:
            print("[SEEDANCE PRO FAST] WARNING: Reference images ignored - text-to-video only")
        
        # Build request payload
        payload = {
            "prompt": prompt,
            "duration": duration,  # API expects integer, not string
            "resolution": resolution,
            "aspect_ratio": aspect_ratio,
            "seed": seed,
            "camera_fixed": camera_fixed,
            "enable_safety_checker": True
        }
        
        print(f"[SEEDANCE PRO FAST] Generating text-to-video")
        print(f"[SEEDANCE PRO FAST] Duration: {duration}s, Resolution: {resolution}")
        
        # Submit request to queue
        video_url = self._submit_and_wait(payload)
        
        # Download video from result URL
        print(f"[SEEDANCE PRO FAST] Downloading video from: {video_url}")
        response = requests.get(video_url, timeout=120)
        response.raise_for_status()
        
        return response.content
    
    def _submit_and_wait(self, payload: dict) -> str:
        """
        Submit request to Seedance Pro Fast using official fal_client.
        
        Returns:
            Video URL from result
        """
        print(f"[SEEDANCE PRO FAST] Submitting request via fal_client...")
        print(f"[SEEDANCE PRO FAST] Waiting for video generation (this may take 2-3 minutes)...")
        
        # Use fal_client.subscribe for queue-based API
        result = fal_client.subscribe(
            self.endpoint,
            arguments=payload
        )
        
        video_url = result["video"]["url"]
        seed_used = result.get("seed")
        
        print(f"[SEEDANCE PRO FAST] Video generated successfully! Seed: {seed_used}")
        return video_url

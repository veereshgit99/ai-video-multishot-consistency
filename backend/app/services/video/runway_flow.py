import time
import base64
from typing import Any, Dict, List, Optional

import requests

from app.core.config_video import RUNWAY_API_KEY, RUNWAY_BASE_URL, RUNWAY_DURATION
from app.services.video.base import BaseVideoService


class RunwayVideoService(BaseVideoService):
    """
    Video generation via Runway ML Gen4 Turbo API.
    Supports text-to-video and image-to-video generation.
    """

    def __init__(self):
        if not RUNWAY_API_KEY:
            raise ValueError("RUNWAY_API_KEY not configured in .env")
        self.api_key = RUNWAY_API_KEY
        self.base_url = RUNWAY_BASE_URL
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "X-Runway-Version": "2024-11-06",
        }

    def generate_video(
        self,
        prompt: str,
        num_frames: int = 60,
        reference_images: Optional[List[Dict[str, Any]]] = None,
        seed: Optional[int] = None
    ) -> bytes:
        """
        Generate video using Runway Gen4 Turbo.
        
        Args:
            prompt: Text description for the video
            num_frames: Ignored (Runway uses duration instead)
            reference_images: Optional list of reference images (Runway supports single image)
            seed: Optional seed for reproducibility
            
        Returns:
            Video bytes (MP4)
        """
        # Step 1: Prepare request payload
        payload: Dict[str, Any] = {
            "promptText": prompt,
            "model": "gen4_turbo",
            "ratio": "1280:720",
            "duration": RUNWAY_DURATION,
        }

        # Handle single image input (Runway limitation)
        if reference_images and len(reference_images) > 0:
            # Runway only accepts one image via promptImage
            # Take the first reference image
            first_ref = reference_images[0]
            
            # Extract base64 image data
            if "image" in first_ref and "bytesBase64Encoded" in first_ref["image"]:
                image_base64 = first_ref["image"]["bytesBase64Encoded"]
                
                # Convert base64 to data URL format required by Runway
                mime_type = first_ref["image"].get("mimeType", "image/jpeg")
                data_url = f"data:{mime_type};base64,{image_base64}"
                payload["promptImage"] = data_url
                
                print(f"[Runway] Using reference image (weight ignored, Runway doesn't support weights)")
            
            # Warn if multiple images provided
            if len(reference_images) > 1:
                print(f"[Runway] WARNING: {len(reference_images)} images provided, but Runway only supports 1. Using first image only.")

        if seed is not None:
            payload["seed"] = seed

        print(f"[Runway] Starting generation with duration={RUNWAY_DURATION}s")
        print(f"[Runway] Payload keys: {list(payload.keys())}")

        # Step 2: Submit generation request
        create_url = f"{self.base_url}/image_to_video"
        
        resp = requests.post(create_url, headers=self.headers, json=payload)
        
        if resp.status_code != 200:
            print(f"[Runway] Error response: {resp.text}")
            raise Exception(f"Runway API error: {resp.status_code} - {resp.text}")

        data = resp.json()
        task_id = data.get("id")
        
        if not task_id:
            raise Exception(f"No task ID returned from Runway: {resp.text}")

        print(f"[Runway] Task created: {task_id}")

        # Step 3: Poll for completion
        status_url = f"{self.base_url}/tasks/{task_id}"
        
        max_polls = 120  # 10 minutes max (5s polling interval)
        poll_count = 0
        
        while poll_count < max_polls:
            time.sleep(5)  # Poll every 5 seconds
            poll_count += 1
            
            poll_resp = requests.get(status_url, headers=self.headers)
            
            if poll_resp.status_code != 200:
                raise Exception(f"Failed to poll Runway task: {poll_resp.status_code} - {poll_resp.text}")

            poll_data = poll_resp.json()
            status = poll_data.get("status")
            
            print(f"[Runway] Poll {poll_count}: status={status}")
            
            if status == "SUCCEEDED":
                # Step 4: Download video from URL
                # Response format: {"status": "SUCCEEDED", "output": ["https://..."]} or {"output": "https://..."}
                output = poll_data.get("output")
                
                if not output:
                    raise Exception(f"No output in completed task: {poll_data}")
                
                # Handle both list and string formats
                if isinstance(output, list):
                    video_url = output[0] if output else None
                else:
                    video_url = output
                
                if not video_url:
                    raise Exception(f"No valid video URL in output: {output}")
                
                print(f"[Runway] Downloading video from CDN: {video_url}")
                
                # Download video bytes
                video_resp = requests.get(video_url, timeout=60)
                
                if video_resp.status_code != 200:
                    raise Exception(f"Failed to download video: {video_resp.status_code}")
                
                print(f"[Runway] Video downloaded successfully ({len(video_resp.content)} bytes)")
                return video_resp.content
            
            elif status == "FAILED":
                error_msg = poll_data.get("error", "Unknown error")
                raise Exception(f"Runway generation failed: {error_msg}")
            
            elif status in ["PENDING", "RUNNING"]:
                # Continue polling
                continue
            
            else:
                print(f"[Runway] Unknown status: {status}, continuing to poll...")
                continue

        raise Exception(f"Runway generation timed out after {max_polls * 5} seconds")

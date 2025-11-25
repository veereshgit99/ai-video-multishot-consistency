import time
from typing import Any, Dict, List, Optional

import requests

from app.core.config_video import MINIMAX_API_KEY, MINIMAX_BASE_URL, MINIMAX_DEFAULT_MODEL
from app.services.video.base import BaseVideoService


class MinimaxVideoService(BaseVideoService):
    """
    Video generation via MiniMax Hailuo API (I2V - Image to Video).
    Supports text-to-video and image-to-video generation.
    API Docs: https://platform.minimax.io/docs/api-reference/video-generation-i2v
    """

    def __init__(self):
        if not MINIMAX_API_KEY:
            raise ValueError("MINIMAX_API_KEY not configured in .env")
        self.api_key = MINIMAX_API_KEY
        self.base_url = MINIMAX_BASE_URL
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def generate_video(
        self,
        prompt: str,
        num_frames: int = 60,
        reference_images: Optional[List[Dict[str, Any]]] = None,
        seed: Optional[int] = None
    ) -> bytes:
        """
        Generate video using MiniMax Hailuo-2.3 (I2V).
        
        Args:
            prompt: Text description for the video
            num_frames: Ignored (MiniMax uses duration instead)
            reference_images: Optional list of reference images (MiniMax supports single image)
            seed: Optional seed for reproducibility
            
        Returns:
            Video bytes (MP4)
        """
        # Step 1: Prepare request payload
        payload: Dict[str, Any] = {
            "prompt": prompt,
            "model": MINIMAX_DEFAULT_MODEL,
            "duration": 6,  # 6 seconds (MiniMax supports 6s)
            "resolution": "1080P",  # Options: "720P", "1080P"
        }

        # Handle single image input (MiniMax accepts one image via first_frame_image)
        if reference_images and len(reference_images) > 0:
            # MiniMax only accepts one image via first_frame_image
            # Take the first reference image
            first_ref = reference_images[0]
            
            # Extract base64 image data
            if "image" in first_ref and "bytesBase64Encoded" in first_ref["image"]:
                image_base64 = first_ref["image"]["bytesBase64Encoded"]
                
                # Convert base64 to data URL format
                mime_type = first_ref["image"].get("mimeType", "image/jpeg")
                data_url = f"data:{mime_type};base64,{image_base64}"
                payload["first_frame_image"] = data_url
                
                print(f"[MiniMax] Using reference image as first frame")
            
            # Warn if multiple images provided
            if len(reference_images) > 1:
                print(f"[MiniMax] WARNING: {len(reference_images)} images provided, but MiniMax only supports 1. Using first image only.")

        # MiniMax doesn't support seed parameter in API docs
        if seed is not None:
            print(f"[MiniMax] WARNING: Seed parameter not supported by MiniMax API, ignoring seed={seed}")

        print(f"[MiniMax] Starting generation with duration=6s, resolution=1080P")
        print(f"[MiniMax] Payload keys: {list(payload.keys())}")

        # Step 2: Submit generation request
        create_url = f"{self.base_url}/video_generation"
        
        resp = requests.post(create_url, headers=self.headers, json=payload)
        
        if resp.status_code != 200:
            print(f"[MiniMax] Error response: {resp.text}")
            raise Exception(f"MiniMax API error: {resp.status_code} - {resp.text}")

        data = resp.json()
        
        # MiniMax returns task_id in response
        task_id = data.get("task_id")
        
        if not task_id:
            raise Exception(f"No task_id returned from MiniMax: {resp.text}")

        print(f"[MiniMax] Task created: {task_id}")

        # Step 3: Poll for completion
        # Query with task_id as query parameter
        max_polls = 120  # 10 minutes max (5s polling interval)
        poll_count = 0
        
        while poll_count < max_polls:
            time.sleep(5)  # Poll every 5 seconds
            poll_count += 1
            
            # Query task status with task_id as query param
            status_url = f"{self.base_url}/query/video_generation?task_id={task_id}"
            poll_resp = requests.get(status_url, headers=self.headers)
            
            if poll_resp.status_code != 200:
                raise Exception(f"Failed to poll MiniMax task: {poll_resp.status_code} - {poll_resp.text}")

            poll_data = poll_resp.json()
            status = poll_data.get("status")
            
            print(f"[MiniMax] Poll {poll_count}: status={status}")
            
            if status == "Success":
                # Step 4: Get download URL from file_id
                file_id = poll_data.get("file_id")
                
                if not file_id:
                    raise Exception(f"No file_id in completed task: {poll_data}")
                
                # Use files/retrieve endpoint to get download URL
                retrieve_url = f"{self.base_url}/files/retrieve?file_id={file_id}"
                print(f"[MiniMax] Retrieving download URL for file_id: {file_id}")
                
                retrieve_resp = requests.get(retrieve_url, headers=self.headers, timeout=30)
                
                if retrieve_resp.status_code != 200:
                    raise Exception(f"Failed to retrieve file: {retrieve_resp.status_code} - {retrieve_resp.text}")
                
                retrieve_data = retrieve_resp.json()
                download_url = retrieve_data.get("file", {}).get("download_url")
                
                if not download_url:
                    raise Exception(f"No download_url in retrieve response: {retrieve_data}")
                
                print(f"[MiniMax] Downloading video from CDN...")
                
                # Download video bytes
                video_resp = requests.get(download_url, timeout=120)
                
                if video_resp.status_code != 200:
                    raise Exception(f"Failed to download video: {video_resp.status_code}")
                
                print(f"[MiniMax] Video downloaded successfully ({len(video_resp.content)} bytes)")
                return video_resp.content
            
            elif status == "Failed":
                error_msg = poll_data.get("error", "Unknown error")
                raise Exception(f"MiniMax generation failed: {error_msg}")
            
            elif status in ["Queueing", "Processing"]:
                # Continue polling
                continue
            
            else:
                print(f"[MiniMax] Unknown status: {status}, continuing to poll...")
                continue

        raise Exception(f"MiniMax generation timed out after {max_polls * 5} seconds")

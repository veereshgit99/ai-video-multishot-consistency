import time
import base64
from typing import Any, Dict, List, Optional

import requests
from google.oauth2 import service_account
import google.auth.transport.requests

from app.core.config_video import (
    GOOGLE_CLOUD_PROJECT_ID,
    GOOGLE_CLOUD_LOCATION,
    VEO_MODEL_ID,
)
from app.services.video.base import BaseVideoService


class GoogleFlowVideoService(BaseVideoService):
    """
    Video generation via Vertex AI Veo 3.1 Fast (predictLongRunning).
    """

    CREDENTIALS_PATH = "app/keys/veo.json"

    def _get_access_token(self) -> str:
        """Generate OAuth2 access token via service account."""
        scopes = ["https://www.googleapis.com/auth/cloud-platform"]
        credentials = service_account.Credentials.from_service_account_file(
            self.CREDENTIALS_PATH, scopes=scopes
        )
        req = google.auth.transport.requests.Request()
        credentials.refresh(req)
        return credentials.token

    def generate_video(self, prompt: str, num_frames: int = 60, reference_images=None, seed=None) -> bytes:
        access_token = self._get_access_token()

        # Veo 2 models only support 720p, Veo 3 supports 1080p
        resolution = "720p" if VEO_MODEL_ID.startswith("veo-2") else "1080p"
        sample_count = 1

        # -----------------------------------------------------
        # STEP 1 — Submit predictLongRunning request
        # -----------------------------------------------------
        url = (
            f"https://{GOOGLE_CLOUD_LOCATION}-aiplatform.googleapis.com/v1/"
            f"projects/{GOOGLE_CLOUD_PROJECT_ID}/locations/{GOOGLE_CLOUD_LOCATION}"
            f"/publishers/google/models/{VEO_MODEL_ID}:predictLongRunning"
        )

        # Build parameters
        params: Dict[str, Any] = {
            "sampleCount": sample_count,
            "resolution": resolution,
        }
        if seed is not None:
            params["seed"] = seed

        # Build instance with optional reference images
        instance: Dict[str, Any] = {"prompt": prompt}
        if reference_images:
            instance["referenceImages"] = reference_images
            print(f"\nDEBUG google_flow: Adding {len(reference_images)} reference images to request")
            for i, ref in enumerate(reference_images):
                print(f"  Ref {i+1}: type={ref.get('referenceType')}, weight={ref.get('weight')}")

        payload: Dict[str, Any] = {
            "instances": [instance],
            "parameters": params,
        }

        print(f"DEBUG google_flow: Payload structure:")
        print(f"  - instances[0] keys: {list(payload['instances'][0].keys())}")
        print(f"  - parameters: {params}")
        if reference_images:
            print(f"  - referenceImages count: {len(reference_images)}")

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        resp = requests.post(url, headers=headers, json=payload)

        print(f"DEBUG google_flow: Response status: {resp.status_code}")
        if resp.status_code != 200:
            print(f"DEBUG google_flow: Error response: {resp.text}")
            raise Exception(f"Veo LRO error: {resp.status_code} - {resp.text}")

        data = resp.json()
        operation_name = data.get("name")
        if not operation_name:
            raise Exception(f"No operation name returned: {resp.text}")

        # -----------------------------------------------------
        # STEP 2 — Poll using :fetchPredictOperation endpoint
        # Reference: https://docs.cloud.google.com/vertex-ai/generative-ai/docs/video/generate-videos-from-text#rest
        # -----------------------------------------------------
        fetch_url = (
            f"https://{GOOGLE_CLOUD_LOCATION}-aiplatform.googleapis.com/v1/"
            f"projects/{GOOGLE_CLOUD_PROJECT_ID}/locations/{GOOGLE_CLOUD_LOCATION}"
            f"/publishers/google/models/{VEO_MODEL_ID}:fetchPredictOperation"
        )
        
        fetch_payload = {"operationName": operation_name}

        while True:
            poll_resp = requests.post(fetch_url, headers=headers, json=fetch_payload)

            if poll_resp.status_code != 200:
                raise Exception(
                    f"Failed to poll Veo operation: {poll_resp.status_code} - {poll_resp.text}"
                )

            poll_data = poll_resp.json()

            if poll_data.get("done"):
                break

            time.sleep(5)  # delay between polls

        # -----------------------------------------------------
        # STEP 3 — Extract predictions from completed operation
        # -----------------------------------------------------
        response = poll_data.get("response", {})
        
        # Check for videos (new Veo API format)
        videos = response.get("videos", [])
        if videos:
            video = videos[0]
            if "bytesBase64Encoded" in video:
                return base64.b64decode(video["bytesBase64Encoded"])
            if "gcsUri" in video:
                from google.cloud import storage
                uri = video["gcsUri"]
                if not uri.startswith("gs://"):
                    raise Exception(f"Invalid gcsUri: {uri}")
                _, bucket, *path_parts = uri.split("/")
                blob_path = "/".join(path_parts)
                client = storage.Client(project=GOOGLE_CLOUD_PROJECT_ID)
                blob = client.bucket(bucket).blob(blob_path)
                return blob.download_as_bytes()
        
        # Fallback: check for predictions (old format)
        predictions = response.get("predictions", [])
        if not predictions:
            raise Exception(f"No videos or predictions found: {poll_data}")

        pred = predictions[0]

        # -----------------------------------------------------
        # STEP 4 — Extract inline base64 video if available
        # -----------------------------------------------------
        if "bytesBase64Encoded" in pred:
            return base64.b64decode(pred["bytesBase64Encoded"])

        # -----------------------------------------------------
        # STEP 5 — Fallback: download from GCS
        # -----------------------------------------------------
        if "gcsUri" in pred:
            uri = pred["gcsUri"]

            from google.cloud import storage

            if not uri.startswith("gs://"):
                raise Exception(f"Invalid gcsUri: {uri}")

            _, bucket, *path_parts = uri.split("/")
            blob_path = "/".join(path_parts)

            client = storage.Client(project=GOOGLE_CLOUD_PROJECT_ID)
            blob = client.bucket(bucket).blob(blob_path)
            return blob.download_as_bytes()

        raise Exception(f"Unknown Veo response format: {pred}")

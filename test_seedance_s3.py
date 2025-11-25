"""
Quick test of Seedance with real S3 image
"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

from dotenv import load_dotenv
load_dotenv("backend/.env")

from app.services.s3_storage import download_from_uri
from app.services.video.seedance_flow import SeedanceVideoService
import base64

# S3 image
s3_uri = "s3://ai-video-consistency/anchors/generated/0_a0e475016eba4c2e9f796de90e7021c7.jpg"
prompt = "Woman playing badminton, executing a powerful smash shot with intense focus"

print(f"Downloading image from S3: {s3_uri}")
image_bytes = download_from_uri(s3_uri)
image_base64 = base64.b64encode(image_bytes).decode('utf-8')

# Prepare reference image in Veo format
reference_images = [{
    "image": {
        "bytesBase64Encoded": image_base64,
        "mimeType": "image/jpeg"
    },
    "weight": 1.0
}]

print(f"\nPrompt: {prompt}")
print("Generating video with Seedance...")

service = SeedanceVideoService()
video_bytes = service.generate_video(
    prompt=prompt,
    reference_images=reference_images,
    duration=5,
    resolution="720p"
)

output_path = "seedance_badminton_test.mp4"
with open(output_path, "wb") as f:
    f.write(video_bytes)

print(f"\n✅ Video saved to: {output_path}")
print(f"Size: {len(video_bytes):,} bytes")

"""
Test script for Veo 3.1 with reference images (asset type).

Based on official documentation:
https://docs.cloud.google.com/vertex-ai/generative-ai/docs/video/use-reference-images-to-guide-video-generation

Key findings:
- Veo 3.1 (veo-3.1-generate-001) DOES support reference images with referenceType="asset"
- Supports up to 3 reference images per request
- Does NOT support referenceType="style" (Veo 2.0 only)
- Reference images go in instances[0]["referenceImages"] array, NOT in parameters
- Default duration: 8 seconds (can be configured in parameters.durationSeconds)
"""

import os
import sys
import base64
import time
from pathlib import Path

# Add backend directory to Python path
backend_dir = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_dir))
os.chdir(str(backend_dir))

from dotenv import load_dotenv
load_dotenv()

from app.services.video.google_flow import GoogleFlowVideoService
from app.core.config import settings
from app.services.s3_storage import download_from_uri


def load_test_image(image_path: str) -> str:
    """Load image from S3 or local file and convert to base64."""
    if image_path.startswith("s3://"):
        # Download from S3
        print(f"  Downloading from S3: {image_path}")
        image_bytes = download_from_uri(image_path)
        return base64.b64encode(image_bytes).decode()
    else:
        # Load from local file
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode()


def test_veo_3_1_with_single_reference():
    """
    Test Veo 3.1 with a single reference image (asset type).
    This should preserve the subject's appearance in the output video.
    """
    print("\n=== Test 1: Veo 3.1 with Single Reference Image ===")
    
    # Initialize service with Veo 3.1 model
    service = GoogleFlowVideoService(model_id="veo-3.1-generate-001")
    
    # Load a test image (you'll need to provide your own test image path)
    test_image_path = "test_character.jpg"  # Replace with your actual image path
    
    if not os.path.exists(test_image_path):
        print(f"ERROR: Test image not found at {test_image_path}")
        print("Please provide a test image path in the script.")
        return
    
    image_base64 = load_test_image(test_image_path)
    
    # Build reference images array (Veo 3.1 format from docs)
    reference_images = [
        {
            "image": {
                "bytesBase64Encoded": image_base64,
                "mimeType": "image/jpeg"
            },
            "referenceType": "asset"  # Preserve subject appearance
        }
    ]
    
    prompt = "A person walking through a beautiful forest at golden hour, cinematic lighting"
    
    print(f"Prompt: {prompt}")
    print(f"Model: veo-3.1-generate-001")
    print(f"Reference images: 1 (asset type)")
    print("Starting video generation...")
    
    try:
        start_time = time.time()
        video_bytes = service.generate_video(
            prompt=prompt,
            reference_images=reference_images
        )
        elapsed = time.time() - start_time
        
        # Save output
        output_path = f"test_veo3_1_single_ref_{int(time.time())}.mp4"
        with open(output_path, "wb") as f:
            f.write(video_bytes)
        
        print(f"\n✓ SUCCESS!")
        print(f"  Generation time: {elapsed:.1f}s")
        print(f"  Video size: {len(video_bytes) / 1024 / 1024:.2f} MB")
        print(f"  Saved to: {output_path}")
        
    except Exception as e:
        print(f"\n✗ FAILED: {e}")
        import traceback
        traceback.print_exc()


def test_veo_3_1_with_multiple_references():
    """
    Test Veo 3.1 with multiple reference images (up to 3).
    This tests the multi-anchor capability of Veo 3.1.
    """
    print("\n=== Test 2: Veo 3.1 with Multiple Reference Images ===")
    
    # Initialize service with Veo 3.1 model
    service = GoogleFlowVideoService(model_id="veo-3.1-generate-001")
    
    # Load multiple test images (provide your own paths)
    test_images = [
        "test_character_1.jpg",  # Character front view
        "test_character_2.jpg",  # Character side view
        "test_character_3.jpg",  # Character with props
    ]
    
    # Check if images exist
    existing_images = [img for img in test_images if os.path.exists(img)]
    
    if len(existing_images) == 0:
        print("ERROR: No test images found.")
        print("Please provide test image paths in the script.")
        print("You can use 1-3 images for this test.")
        return
    
    print(f"Found {len(existing_images)} test images")
    
    # Build reference images array
    reference_images = []
    for img_path in existing_images:
        image_base64 = load_test_image(img_path)
        reference_images.append({
            "image": {
                "bytesBase64Encoded": image_base64,
                "mimeType": "image/jpeg"
            },
            "referenceType": "asset"
        })
    
    prompt = "A person performing a martial arts kata in slow motion, dramatic lighting, professional cinematography"
    
    print(f"Prompt: {prompt}")
    print(f"Model: veo-3.1-generate-001")
    print(f"Reference images: {len(reference_images)} (asset type)")
    print("Starting video generation...")
    
    try:
        start_time = time.time()
        video_bytes = service.generate_video(
            prompt=prompt,
            reference_images=reference_images
        )
        elapsed = time.time() - start_time
        
        # Save output
        output_path = f"test_veo3_1_multi_ref_{int(time.time())}.mp4"
        with open(output_path, "wb") as f:
            f.write(video_bytes)
        
        print(f"\n✓ SUCCESS!")
        print(f"  Generation time: {elapsed:.1f}s")
        print(f"  Video size: {len(video_bytes) / 1024 / 1024:.2f} MB")
        print(f"  Saved to: {output_path}")
        
    except Exception as e:
        print(f"\n✗ FAILED: {e}")
        import traceback
        traceback.print_exc()


def test_veo_3_1_with_custom_duration():
    """
    Test Veo 3.1 with reference image and custom duration.
    Note: Veo 3.1 supports durationSeconds parameter.
    """
    print("\n=== Test 3: Veo 3.1 with Reference Image + Custom Duration ===")
    
    # Initialize service
    service = GoogleFlowVideoService(model_id="veo-3.1-generate-001")
    
    test_image_path = "test_character.jpg"
    
    if not os.path.exists(test_image_path):
        print(f"ERROR: Test image not found at {test_image_path}")
        return
    
    image_base64 = load_test_image(test_image_path)
    
    reference_images = [
        {
            "image": {
                "bytesBase64Encoded": image_base64,
                "mimeType": "image/jpeg"
            },
            "referenceType": "asset"
        }
    ]
    
    prompt = "A person dancing gracefully in an empty ballroom, elegant movements, soft lighting"
    
    # Note: The current google_flow.py doesn't expose duration parameter
    # This is just to document the API capability
    print(f"Prompt: {prompt}")
    print(f"Model: veo-3.1-generate-001")
    print(f"Reference images: 1 (asset type)")
    print("Note: Duration parameter would be set in parameters.durationSeconds")
    print("      Current implementation uses default (8s)")
    print("Starting video generation...")
    
    try:
        start_time = time.time()
        video_bytes = service.generate_video(
            prompt=prompt,
            reference_images=reference_images
        )
        elapsed = time.time() - start_time
        
        # Save output
        output_path = f"test_veo3_1_duration_{int(time.time())}.mp4"
        with open(output_path, "wb") as f:
            f.write(video_bytes)
        
        print(f"\n✓ SUCCESS!")
        print(f"  Generation time: {elapsed:.1f}s")
        print(f"  Video size: {len(video_bytes) / 1024 / 1024:.2f} MB")
        print(f"  Saved to: {output_path}")
        
    except Exception as e:
        print(f"\n✗ FAILED: {e}")
        import traceback
        traceback.print_exc()


def print_api_format_example():
    """Print the correct API format for Veo 3.1 with reference images."""
    print("\n=== Veo 3.1 Reference Image API Format (from official docs) ===")
    print("""
Request Format:
POST https://us-central1-aiplatform.googleapis.com/v1/projects/PROJECT_ID/locations/us-central1/publishers/google/models/veo-3.1-generate-001:predictLongRunning

Request Body:
{
  "instances": [
    {
      "prompt": "Your text prompt here",
      "referenceImages": [
        {
          "image": {
            "bytesBase64Encoded": "BASE64_ENCODED_IMAGE",
            "mimeType": "image/jpeg"
          },
          "referenceType": "asset"
        }
        // Can repeat for up to 3 total images
      ]
    }
  ],
  "parameters": {
    "durationSeconds": 8,
    "storageUri": "gs://bucket/output/",  // Optional
    "sampleCount": 1
  }
}

Key Points:
- Veo 3.1 model ID: "veo-3.1-generate-001"
- Reference images go in instances[0]["referenceImages"] (NOT in parameters)
- Each image needs: bytesBase64Encoded, mimeType, and referenceType
- referenceType: "asset" (preserves subject) - supported by Veo 3.1
- referenceType: "style" (applies style) - NOT supported by Veo 3.1 (Veo 2.0 only)
- Max 3 reference images per request
- Default duration: 8 seconds
- Response contains operation name for polling
    """)


def test_custom_s3_image():
    """
    Test Veo 3.1 with custom S3 image and prompt.
    Image: s3://ai-video-consistency/Pics/alex-k-arabi-final.jpg
    """
    print("\n=== Custom Test: Veo 3.1 with S3 Image (OLD KENZO Scene) ===")
    
    # Initialize service with Veo 3.1 model
    service = GoogleFlowVideoService(model_id="veo-3.1-generate-001")
    
    # S3 image path
    s3_image_uri = "s3://ai-video-consistency/Pics/alex-k-arabi-final.jpg"
    
    print(f"Loading image from S3...")
    image_base64 = load_test_image(s3_image_uri)
    print(f"  Image loaded successfully ({len(image_base64)} chars base64)")
    
    # Build reference images array (Veo 3.1 format)
    reference_images = [
        {
            "image": {
                "bytesBase64Encoded": image_base64,
                "mimeType": "image/jpeg"
            },
            "referenceType": "asset"  # Preserve subject appearance
        }
    ]
    
    prompt = "START VIDEO WITH COMPOSITION AND STYLE OF THE REFERENCE IMAGE. The video then performs a slow, gentle camera push-in on the lone figure of OLD KENZO (sitting on the right). A small, red, worn fabric talisman is tied to the top of his spear. The surrounding prayer flags are fluttering subtly in a cold breeze. 16:9 aspect ratio, dark fantasy style, highly detailed."
    
    print(f"\nPrompt: {prompt}")
    print(f"Model: veo-3.1-generate-001")
    print(f"Reference images: 1 (asset type)")
    print(f"Source: {s3_image_uri}")
    print("\nStarting video generation (this may take 2-3 minutes)...")
    
    try:
        start_time = time.time()
        video_bytes = service.generate_video(
            prompt=prompt,
            reference_images=reference_images
        )
        elapsed = time.time() - start_time
        
        # Save output to backend directory
        output_path = f"test_veo3_1_kenzo_{int(time.time())}.mp4"
        with open(output_path, "wb") as f:
            f.write(video_bytes)
        
        print(f"\n✓ SUCCESS!")
        print(f"  Generation time: {elapsed:.1f}s")
        print(f"  Video size: {len(video_bytes) / 1024 / 1024:.2f} MB")
        print(f"  Saved to: {output_path}")
        
    except Exception as e:
        print(f"\n✗ FAILED: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    print("=" * 80)
    print("VEO 3.1 REFERENCE IMAGE TEST SUITE")
    print("=" * 80)
    
    # Check configuration
    print("\n=== Configuration Check ===")
    print(f"Project ID: {settings.GOOGLE_CLOUD_PROJECT_ID}")
    print(f"Location: {settings.GOOGLE_CLOUD_LOCATION}")
    print(f"Veo 3.1 Model: veo-3.1-generate-001")
    print(f"S3 Bucket: {settings.S3_BUCKET_NAME}")
    
    # Run tests
    print("\n" + "=" * 80)
    print("RUNNING CUSTOM TEST")
    print("=" * 80)
    
    # Run the custom test with your S3 image
    test_custom_s3_image()
    
    print("\n" + "=" * 80)
    print("TEST COMPLETE")
    print("=" * 80)

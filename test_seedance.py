"""
Seedance Integration Test

This script helps test the Seedance integration step-by-step.
Run each test individually to verify functionality before production use.

BEFORE RUNNING:
1. Get FAL_API_KEY from fal.ai and add to backend/.env
2. Research pricing on fal.ai website
3. Run tests in order (don't skip steps)
"""

import os
import sys

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

from app.services.video.seedance_flow import SeedanceVideoService
from app.services.video.base import get_video_service
import argparse


def test_api_key():
    """Test 1: Verify FAL_API_KEY is configured"""
    print("\n=== TEST 1: API Key Configuration ===")
    
    fal_key = os.getenv("FAL_API_KEY")
    if not fal_key:
        print("❌ FAILED: FAL_API_KEY not found in environment")
        print("   Add to backend/.env: FAL_API_KEY=your_key_here")
        return False
    
    print(f"✅ PASSED: FAL_API_KEY found (length: {len(fal_key)})")
    return True


def test_service_creation():
    """Test 2: Verify SeedanceVideoService can be instantiated"""
    print("\n=== TEST 2: Service Creation ===")
    
    try:
        service = SeedanceVideoService()
        print("✅ PASSED: SeedanceVideoService created successfully")
        print(f"   Endpoint: {service.endpoint}")
        print(f"   Base URL: {service.base_url}")
        return True
    except Exception as e:
        print(f"❌ FAILED: {e}")
        return False


def test_factory_function():
    """Test 3: Verify factory function recognizes 'seedance' model"""
    print("\n=== TEST 3: Factory Function ===")
    
    try:
        service = get_video_service("seedance")
        print("✅ PASSED: get_video_service('seedance') returns SeedanceVideoService")
        print(f"   Service type: {type(service).__name__}")
        return True
    except Exception as e:
        print(f"❌ FAILED: {e}")
        return False


def test_image_upload():
    """Test 4: Test uploading a simple test image to fal.ai storage"""
    print("\n=== TEST 4: Image Upload to fal.ai Storage ===")
    print("⚠️  WARNING: This will use API credits!")
    
    response = input("Continue? (yes/no): ")
    if response.lower() != "yes":
        print("Skipped by user")
        return None
    
    try:
        service = SeedanceVideoService()
        
        # Create a simple test image (1x1 red pixel)
        import base64
        from PIL import Image
        import io
        
        # Create 100x100 red square
        img = Image.new('RGB', (100, 100), color='red')
        buffer = io.BytesIO()
        img.save(buffer, format='JPEG')
        img_bytes = buffer.getvalue()
        img_base64 = base64.b64encode(img_bytes).decode('utf-8')
        
        # Upload to fal.ai storage
        url = service._upload_to_fal_storage(img_base64, "image/jpeg")
        
        print(f"✅ PASSED: Image uploaded successfully")
        print(f"   URL: {url}")
        return True
        
    except Exception as e:
        print(f"❌ FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_single_generation():
    """Test 5: Generate a simple 2-second test video"""
    print("\n=== TEST 5: Single Video Generation ===")
    print("⚠️  WARNING: This will use API credits and take 2-3 minutes!")
    print("⚠️  COST: Check fal.ai pricing before proceeding!")
    
    response = input("Continue? (yes/no): ")
    if response.lower() != "yes":
        print("Skipped by user")
        return None
    
    try:
        service = SeedanceVideoService()
        
        # Simple test: text-to-video (no reference images)
        print("\nGenerating test video...")
        print("Prompt: 'A red ball bouncing on a white surface'")
        print("Duration: 2 seconds (shortest option to minimize cost)")
        print("Resolution: 480p (faster/cheaper)")
        
        video_bytes = service.generate_video(
            prompt="A red ball bouncing on a white surface",
            reference_images=None,  # No reference images for simplest test
            duration=2,              # Shortest duration
            resolution="480p"        # Lower resolution
        )
        
        # Save test video
        output_path = "test_seedance_output.mp4"
        with open(output_path, "wb") as f:
            f.write(video_bytes)
        
        print(f"✅ PASSED: Video generated successfully")
        print(f"   Output: {output_path}")
        print(f"   Size: {len(video_bytes):,} bytes")
        return True
        
    except Exception as e:
        print(f"❌ FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_multi_image_generation():
    """Test 6: Generate video with 2 reference images"""
    print("\n=== TEST 6: Multi-Image Generation ===")
    print("⚠️  WARNING: This will use API credits and take 2-3 minutes!")
    
    response = input("Continue? (yes/no): ")
    if response.lower() != "yes":
        print("Skipped by user")
        return None
    
    try:
        service = SeedanceVideoService()
        
        # Create two test images
        import base64
        from PIL import Image
        import io
        
        def create_test_image(color, size=100):
            img = Image.new('RGB', (size, size), color=color)
            buffer = io.BytesIO()
            img.save(buffer, format='JPEG')
            img_bytes = buffer.getvalue()
            return base64.b64encode(img_bytes).decode('utf-8')
        
        # Create Veo-format reference images
        reference_images = [
            {
                "image": {
                    "bytesBase64Encoded": create_test_image('blue'),
                    "mimeType": "image/jpeg"
                },
                "weight": 0.8
            },
            {
                "image": {
                    "bytesBase64Encoded": create_test_image('green'),
                    "mimeType": "image/jpeg"
                },
                "weight": 0.5
            }
        ]
        
        print("\nGenerating video with 2 reference images...")
        print("Image 1: Blue square (weight 0.8)")
        print("Image 2: Green square (weight 0.5)")
        
        video_bytes = service.generate_video(
            prompt="Smooth transition between colors",
            reference_images=reference_images,
            duration=2,
            resolution="480p"
        )
        
        output_path = "test_seedance_multi_image.mp4"
        with open(output_path, "wb") as f:
            f.write(video_bytes)
        
        print(f"✅ PASSED: Multi-image video generated")
        print(f"   Output: {output_path}")
        return True
        
    except Exception as e:
        print(f"❌ FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    parser = argparse.ArgumentParser(description="Test Seedance Integration")
    parser.add_argument(
        "--test",
        choices=["all", "api_key", "service", "factory", "upload", "single", "multi"],
        default="all",
        help="Which test to run"
    )
    args = parser.parse_args()
    
    print("=" * 60)
    print("SEEDANCE INTEGRATION TEST SUITE")
    print("=" * 60)
    
    tests = {
        "api_key": ("API Key Configuration", test_api_key),
        "service": ("Service Creation", test_service_creation),
        "factory": ("Factory Function", test_factory_function),
        "upload": ("Image Upload", test_image_upload),
        "single": ("Single Generation", test_single_generation),
        "multi": ("Multi-Image Generation", test_multi_image_generation)
    }
    
    if args.test == "all":
        results = {}
        for key, (name, func) in tests.items():
            result = func()
            results[key] = result
            
            # Stop if critical test fails
            if result is False and key in ["api_key", "service", "factory"]:
                print(f"\n❌ Critical test failed. Fix this before continuing.")
                break
        
        # Print summary
        print("\n" + "=" * 60)
        print("TEST SUMMARY")
        print("=" * 60)
        for key, (name, _) in tests.items():
            if key in results:
                status = "✅ PASSED" if results[key] else ("⚠️  SKIPPED" if results[key] is None else "❌ FAILED")
                print(f"{status}: {name}")
    
    else:
        # Run single test
        name, func = tests[args.test]
        func()


if __name__ == "__main__":
    main()

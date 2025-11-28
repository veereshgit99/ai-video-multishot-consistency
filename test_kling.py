"""
Test Kling Video v2.5 Turbo Pro Image-to-Video Generation

Single test case - Ghost Short Movie scene
Image: s3://ai-video-consistency/Pics/GhostShortMovie.jpg
COST: ~$0.30-0.50 per run
"""

import os
import sys
import base64
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_dir))

# Load environment variables BEFORE changing directory
from dotenv import load_dotenv
env_path = backend_dir / ".env"
load_dotenv(dotenv_path=env_path)

# Change to backend directory
os.chdir(str(backend_dir))

from app.services.video.kling_flow import KlingVideoService
from app.services.s3_storage import download_from_uri


def test_kling_ghost_scene():
    """
    Test: Ghost Short Movie - Staircase Scene
    COST: ~$0.30-0.50 per run
    
    Image: s3://ai-video-consistency/Pics/GhostShortMovie.jpg
    Duration: 10s
    Focus: Cinematic camera movement and tense atmosphere
    """
    print("\n" + "="*60)
    print("KLING TEST: Ghost Short Movie - Staircase Scene")
    print("="*60)
    
    # Check if FAL_API_KEY is set
    if not os.getenv("FAL_API_KEY"):
        print("[ERROR] FAL_API_KEY not found in environment")
        print("Set it in backend/.env file")
        return
    
    # Test configuration
    s3_uri = "s3://ai-video-consistency/Pics/GhostShortMovie.jpg"
    prompt = (
        "Continue this scene. The camera stays in the same high, top-down position above the staircase. "
        "The girl slowly climbs the stairs, moving cautiously. As she walks past the camera and reaches "
        "the upper landing, camera goes forward, close to the straight door - there will be a small creepy "
        "looking, girl standing and peeking from behind the door there. Keep the atmosphere tense, "
        "realistic 4K and cinematic."
    )
    
    print(f"\n📷 Image: {s3_uri}")
    print(f"🎬 Prompt: {prompt[:80]}...")
    print(f"⏱️  Duration: 10s")
    
    # Confirm before spending money
    confirm = input(f"\n⚠️  This will cost ~$0.30-0.50. Continue? (yes/no): ").strip().lower()
    if confirm != "yes":
        print("[SKIP] Test cancelled to save money.")
        return
    
    try:
        # Create service
        service = KlingVideoService()
        
        # Download image from S3 and convert to base64
        print(f"\n[1/3] Downloading image from S3...")
        image_bytes = download_from_uri(s3_uri)
        image_base64 = base64.b64encode(image_bytes).decode()
        
        reference_images = [{
            "referenceType": "asset",
            "image": {
                "bytesBase64Encoded": image_base64,
                "mimeType": "image/jpeg"
            },
            "weight": 1.0
        }]
        
        print(f"[2/3] Generating video with Kling...")
        print(f"      This may take 2-3 minutes...")
        print(f"      Testing: Camera movement, tense atmosphere, cinematic quality")
        
        # Generate video
        video_bytes = service.generate_video(
            prompt=prompt,
            reference_images=reference_images,
            duration=10  # 10s default
        )
        
        # Save output
        output_path = Path(__file__).parent / "media" / "generated" / "kling_ghost_staircase.mp4"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, "wb") as f:
            f.write(video_bytes)
        
        print(f"\n[3/3] ✅ SUCCESS!")
        print(f"      Video saved: {output_path}")
        print(f"      Size: {len(video_bytes) / 1024 / 1024:.2f} MB")
        print(f"\n💡 Review the video for:")
        print(f"   - Camera movement from top-down to forward push")
        print(f"   - Girl climbing stairs (motion quality)")
        print(f"   - Creepy atmosphere maintained")
        print(f"   - 4K cinematic quality")
        print(f"   - Compare with Runway/MiniMax results if available")
        
    except Exception as e:
        print(f"\n[ERROR] Test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    print("="*60)
    print("KLING VIDEO v2.5 TURBO PRO - GHOST SCENE TEST")
    print("="*60)
    print("\n⚠️  WARNING: This test costs real money!")
    print("   - Cost: ~$0.30-0.50 per run")
    print("   - Single test case (Ghost staircase scene)")
    print("   - 10 second duration")
    
    test_kling_ghost_scene()

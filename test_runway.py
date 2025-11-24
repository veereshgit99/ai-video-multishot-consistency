"""
Test script for Runway Gen4 Turbo API
"""
import os
import sys
import time
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv("backend/.env")

RUNWAY_API_KEY = os.getenv("RUNWAY_ML_API_KEY")
RUNWAY_BASE_URL = "https://api.dev.runwayml.com/v1"

def test_runway_text_to_video():
    """Test text-to-video generation (no image)"""
    print("\n=== Testing Runway Text-to-Video ===")
    
    headers = {
        "Authorization": f"Bearer {RUNWAY_API_KEY}",
        "Content-Type": "application/json",
        "X-Runway-Version": "2024-11-06",
    }
    
    payload = {
        "promptText": "A woman practicing yoga in a peaceful park at sunrise, cinematic lighting",
        "model": "gen4_turbo",
        "duration": 5,
        "ratio": "1280:720",
    }
    
    print(f"Payload: {payload}")
    
    # Step 1: Create task
    print("\n[1] Creating task...")
    create_url = f"{RUNWAY_BASE_URL}/image_to_video"
    resp = requests.post(create_url, headers=headers, json=payload)
    
    print(f"Status: {resp.status_code}")
    print(f"Response: {resp.text}")
    
    if resp.status_code != 200:
        print(f"ERROR: {resp.status_code} - {resp.text}")
        return
    
    data = resp.json()
    print(f"Response type: {type(data)}")
    print(f"Response data: {data}")
    
    # Extract task ID
    if isinstance(data, list):
        task_id = data[0].get("id") if len(data) > 0 else None
    else:
        task_id = data.get("id")
    
    if not task_id:
        print(f"ERROR: No task ID in response")
        return
    
    print(f"Task ID: {task_id}")
    
    # Step 2: Poll for completion
    print("\n[2] Polling for completion...")
    status_url = f"{RUNWAY_BASE_URL}/tasks/{task_id}"
    
    for i in range(60):  # 5 minutes max
        time.sleep(5)
        
        poll_resp = requests.get(status_url, headers=headers)
        print(f"\nPoll {i+1}: Status {poll_resp.status_code}")
        
        if poll_resp.status_code != 200:
            print(f"ERROR: {poll_resp.status_code} - {poll_resp.text}")
            return
        
        poll_data = poll_resp.json()
        print(f"Poll response type: {type(poll_data)}")
        print(f"Poll response: {poll_data}")
        
        # Handle list or dict
        if isinstance(poll_data, list):
            poll_data = poll_data[0] if len(poll_data) > 0 else {}
        
        status = poll_data.get("status")
        print(f"Status: {status}")
        
        if status == "SUCCEEDED":
            print("\n[3] Task succeeded!")
            
            output = poll_data.get("output")
            print(f"Output type: {type(output)}")
            print(f"Output: {output}")
            
            # Extract video URL
            if isinstance(output, list):
                video_url = output[0] if len(output) > 0 else None
            elif isinstance(output, dict):
                video_url = output.get("url")
            else:
                video_url = output
            
            print(f"Video URL: {video_url}")
            
            if video_url:
                print("\n[4] Downloading video...")
                video_resp = requests.get(video_url, timeout=60)
                
                if video_resp.status_code == 200:
                    # Save video
                    output_path = "test_runway_output.mp4"
                    with open(output_path, "wb") as f:
                        f.write(video_resp.content)
                    
                    print(f"✅ Video saved to {output_path} ({len(video_resp.content)} bytes)")
                else:
                    print(f"ERROR downloading: {video_resp.status_code}")
            
            return
        
        elif status == "FAILED":
            error = poll_data.get("error", "Unknown error")
            print(f"❌ Task failed: {error}")
            return
        
        elif status in ["PENDING", "RUNNING"]:
            print(f"⏳ Task {status.lower()}...")
            continue
        
        else:
            print(f"⚠️ Unknown status: {status}")

    print("❌ Timeout after 5 minutes")


def test_runway_image_to_video():
    """Test image-to-video generation"""
    print("\n=== Testing Runway Image-to-Video ===")
    
    # First, download image from S3 and convert to base64
    import base64
    import boto3
    
    s3_uri = "s3://ai-video-consistency/anchors/generated/0_051193d1b9bd40b59b5c30bf0caab17f.jpg"
    bucket = "ai-video-consistency"
    key = "anchors/generated/0_051193d1b9bd40b59b5c30bf0caab17f.jpg"
    
    print(f"\n[0] Downloading image from S3: {s3_uri}")
    
    # Download from S3
    s3_client = boto3.client(
        's3',
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
        region_name=os.getenv("AWS_REGION", "us-east-2")
    )
    
    try:
        response = s3_client.get_object(Bucket=bucket, Key=key)
        image_bytes = response['Body'].read()
        print(f"✅ Downloaded {len(image_bytes)} bytes from S3")
        
        # Convert to base64
        image_base64 = base64.b64encode(image_bytes).decode()
        data_url = f"data:image/jpeg;base64,{image_base64}"
        print(f"✅ Converted to base64 ({len(image_base64)} chars)")
        
    except Exception as e:
        print(f"❌ Failed to download from S3: {e}")
        return
    
    headers = {
        "Authorization": f"Bearer {RUNWAY_API_KEY}",
        "Content-Type": "application/json",
        "X-Runway-Version": "2024-11-06",
    }
    
    # Use the S3 image
    payload = {
        "promptText": "Woman doing yoga, smooth camera movement",
        "promptImage": data_url,
        "model": "gen4_turbo",
        "duration": 5,
        "ratio": "1280:720",
    }
    
    print(f"Payload keys: {list(payload.keys())}")
    print(f"Image data URL length: {len(payload['promptImage'])}")
    
    # Step 1: Create task
    print("\n[1] Creating task...")
    create_url = f"{RUNWAY_BASE_URL}/image_to_video"
    resp = requests.post(create_url, headers=headers, json=payload)
    
    print(f"Status: {resp.status_code}")
    print(f"Response: {resp.text}")
    
    if resp.status_code != 200:
        print(f"ERROR: {resp.status_code} - {resp.text}")
        return
    
    data = resp.json()
    
    # Extract task ID
    if isinstance(data, list):
        task_id = data[0].get("id") if len(data) > 0 else None
    else:
        task_id = data.get("id")
    
    print(f"Task ID: {task_id}")
    
    # Step 2: Poll (same as text-to-video)
    print("\n[2] Polling for completion...")
    status_url = f"{RUNWAY_BASE_URL}/tasks/{task_id}"
    
    for i in range(60):
        time.sleep(5)
        
        poll_resp = requests.get(status_url, headers=headers)
        
        if poll_resp.status_code != 200:
            print(f"ERROR: {poll_resp.status_code}")
            return
        
        poll_data = poll_resp.json()
        if isinstance(poll_data, list):
            poll_data = poll_data[0] if len(poll_data) > 0 else {}
        
        status = poll_data.get("status")
        print(f"Poll {i+1}: {status}")
        
        if status == "SUCCEEDED":
            output = poll_data.get("output")
            
            if isinstance(output, list):
                video_url = output[0]
            elif isinstance(output, dict):
                video_url = output.get("url")
            else:
                video_url = output
            
            print(f"\n✅ Video URL: {video_url}")
            
            # Download
            video_resp = requests.get(video_url, timeout=60)
            if video_resp.status_code == 200:
                with open("test_runway_image_output.mp4", "wb") as f:
                    f.write(video_resp.content)
                print(f"✅ Saved to test_runway_image_output.mp4")
            
            return
        
        elif status == "FAILED":
            print(f"❌ Failed: {poll_data.get('error')}")
            return


if __name__ == "__main__":
    print(f"Runway API Key: {RUNWAY_API_KEY[:20]}..." if RUNWAY_API_KEY else "NO API KEY")
    
    # Test image-to-video with S3 image
    test_runway_image_to_video()
    
    # Uncomment to test text-to-video
    # test_runway_text_to_video()

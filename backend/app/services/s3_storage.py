"""
S3 Storage Service
Handles all file uploads/downloads to AWS S3, replacing local disk storage.
"""
import os
import uuid
import boto3
from botocore.exceptions import ClientError
from typing import Optional

# Initialize S3 client using environment variables
s3_client = boto3.client(
    's3',
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    region_name=os.getenv("AWS_REGION", "us-east-2")
)

BUCKET_NAME = os.getenv("S3_BUCKET_NAME", "ai-video-consistency")


def upload_bytes(file_bytes: bytes, key: str, content_type: str = 'image/jpeg') -> str:
    """
    Uploads file bytes to S3 and returns the S3 URI.
    
    Args:
        file_bytes: The file content as bytes
        key: The S3 key (path) for the file
        content_type: MIME type (default: image/jpeg)
    
    Returns:
        S3 URI in format: s3://bucket-name/key
    """
    try:
        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=key,
            Body=file_bytes,
            ContentType=content_type
        )
        s3_uri = f"s3://{BUCKET_NAME}/{key}"
        print(f"[S3] Uploaded to {s3_uri}")
        return s3_uri
    except ClientError as e:
        print(f"[S3 ERROR] Failed to upload {key}: {e}")
        raise


def download_from_uri(s3_uri: str) -> bytes:
    """
    Downloads file bytes from S3 using a full S3 URI.
    
    Args:
        s3_uri: Full S3 URI in format s3://bucket-name/key
    
    Returns:
        File content as bytes
    """
    # Parse s3://bucket-name/key
    if not s3_uri.startswith("s3://"):
        raise ValueError(f"Invalid S3 URI: {s3_uri}")
    
    parts = s3_uri[5:].split('/', 1)  # Remove s3:// and split bucket/key
    if len(parts) != 2:
        raise ValueError(f"Invalid S3 URI format: {s3_uri}")
    
    bucket, key = parts
    
    try:
        response = s3_client.get_object(Bucket=bucket, Key=key)
        return response['Body'].read()
    except ClientError as e:
        print(f"[S3 ERROR] Failed to download {s3_uri}: {e}")
        raise


def generate_character_key(character_id: int, session_id: str = None, extension: str = ".jpg") -> str:
    """Generate a unique S3 key for character anchor images."""
    unique_id = uuid.uuid4().hex
    if session_id:
        return f"anchors/{session_id}/{character_id}_{unique_id}{extension}"
    return f"anchors/{character_id}_{unique_id}{extension}"


def generate_video_key(session_id: str, shot_number: int = None, extension: str = ".mp4") -> str:
    """Generate a unique S3 key for generated videos."""
    unique_id = uuid.uuid4().hex
    if shot_number:
        return f"generated/{session_id}/shot_{shot_number}_{unique_id}{extension}"
    return f"generated/{session_id}/{unique_id}{extension}"


def generate_continuity_key(session_id: str, frame_type: str = "last_frame", shot_number: int = None) -> str:
    """Generate S3 key for continuity frames (flow anchors)."""
    if shot_number is not None:
        return f"continuity/{session_id}/shot_{shot_number}_last_frame.jpg"
    return f"continuity/{session_id}/{frame_type}.jpg"


def upload_character_image(character_id: int, image_bytes: bytes, session_id: str = None, extension: str = ".jpg") -> str:
    """
    Upload character anchor image to S3.
    
    Returns:
        S3 URI: s3://bucket-name/anchors/...
    """
    key = generate_character_key(character_id, session_id, extension)
    return upload_bytes(image_bytes, key, content_type='image/jpeg')


def upload_video(video_bytes: bytes, session_id: str, shot_number: int = None) -> str:
    """
    Upload generated video to S3.
    
    Returns:
        S3 URI: s3://bucket-name/generated/...
    """
    key = generate_video_key(session_id, shot_number)
    return upload_bytes(video_bytes, key, content_type='video/mp4')


def upload_continuity_frame(frame_bytes: bytes, session_id: str, shot_number: int = None) -> str:
    """
    Upload continuity frame (last frame for flow) to S3.
    
    Args:
        frame_bytes: Image bytes
        session_id: Session ID
        shot_number: Optional shot number for per-shot last frames
    
    Returns:
        S3 URI: s3://bucket-name/continuity/session_id/shot_N_last_frame.jpg
    """
    key = generate_continuity_key(session_id, shot_number=shot_number)
    return upload_bytes(frame_bytes, key, content_type='image/jpeg')


def get_public_url(s3_uri: str, expiration: int = 3600) -> str:
    """
    Generate a presigned URL for temporary public access.
    
    Args:
        s3_uri: S3 URI in format s3://bucket-name/key
        expiration: URL expiration time in seconds (default: 1 hour)
    
    Returns:
        Presigned URL (https://...)
    """
    if not s3_uri.startswith("s3://"):
        raise ValueError(f"Invalid S3 URI: {s3_uri}")
    
    parts = s3_uri[5:].split('/', 1)
    if len(parts) != 2:
        raise ValueError(f"Invalid S3 URI format: {s3_uri}")
    
    bucket, key = parts
    
    try:
        url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': bucket, 'Key': key},
            ExpiresIn=expiration
        )
        return url
    except ClientError as e:
        print(f"[S3 ERROR] Failed to generate presigned URL for {s3_uri}: {e}")
        raise


def generate_presigned_upload_url(filename: str, session_id: str, content_type: str = "image/jpeg") -> dict:
    """
    Generates a presigned URL that allows client to upload DIRECTLY to S3.
    The session_id is baked into the S3 path for automatic tracking.
    
    Args:
        filename: Original filename (to extract extension)
        session_id: Session/project ID (embedded in S3 path: uploads/{session_id}/...)
        content_type: MIME type of the file
    
    Returns:
        dict with 'upload_url' (presigned URL) and 's3_uri' (final S3 location)
    
    Example:
        result = generate_presigned_upload_url("dog.jpg", "chat_abc123")
        # Frontend uploads directly: PUT result["upload_url"] with file bytes
        # LLM uses: result["s3_uri"]
    """
    # Extract extension and generate unique key with session_id
    ext = filename.split('.')[-1] if '.' in filename else "jpg"
    s3_key = f"uploads/{session_id}/{uuid.uuid4().hex}.{ext}"
    
    try:
        # Generate presigned PUT URL (client uploads using PUT request)
        upload_url = s3_client.generate_presigned_url(
            'put_object',
            Params={
                'Bucket': BUCKET_NAME,
                'Key': s3_key,
                'ContentType': content_type
            },
            ExpiresIn=300  # URL expires in 5 minutes
        )
        
        s3_uri = f"s3://{BUCKET_NAME}/{s3_key}"
        print(f"[S3] Generated presigned upload URL for {s3_uri}")
        
        return {
            "upload_url": upload_url,
            "s3_uri": s3_uri
        }
    except ClientError as e:
        print(f"[S3 ERROR] Failed to generate presigned upload URL: {e}")
        raise


def delete_file(s3_uri: str) -> bool:
    """
    Delete a file from S3.
    
    Args:
        s3_uri: S3 URI in format s3://bucket-name/key
    
    Returns:
        True if successful, False otherwise
    """
    if not s3_uri.startswith("s3://"):
        raise ValueError(f"Invalid S3 URI: {s3_uri}")
    
    parts = s3_uri[5:].split('/', 1)
    if len(parts) != 2:
        raise ValueError(f"Invalid S3 URI format: {s3_uri}")
    
    bucket, key = parts
    
    try:
        s3_client.delete_object(Bucket=bucket, Key=key)
        print(f"[S3] Deleted {s3_uri}")
        return True
    except ClientError as e:
        print(f"[S3 ERROR] Failed to delete {s3_uri}: {e}")
        return False

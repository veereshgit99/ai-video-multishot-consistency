"""
Upload Endpoints for Production Use
Handles file uploads to S3 with session tracking.
"""
from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from pydantic import BaseModel
from app.services.s3_storage import upload_bytes, generate_presigned_upload_url
import uuid

router = APIRouter(tags=["uploads"])


class UploadResponse(BaseModel):
    """Response model for successful uploads"""
    status: str
    s3_uri: str
    filename: str
    public_url: str | None = None


class PresignedUploadResponse(BaseModel):
    """Response model for presigned URL generation"""
    upload_url: str
    s3_uri: str
    expires_in: int


@router.post("/upload", response_model=UploadResponse)
async def upload_file(
    file: UploadFile = File(...),
    session_id: str = Query(..., description="Session ID to track which project this file belongs to")
):
    """
    Production Endpoint: Accepts a file, uploads to S3, returns the URI.
    
    This is what your Frontend/Client calls BEFORE talking to the LLM.
    The session_id ensures the file is organized under the correct project folder.
    
    Workflow:
    1. User uploads file via your web app
    2. This endpoint receives file + session_id
    3. File uploaded to S3: s3://bucket/uploads/{session_id}/{uuid}.{ext}
    4. Returns s3_uri for LLM to use
    
    Args:
        file: The uploaded file (image, video, etc.)
        session_id: The chat/project session ID (for folder organization)
    
    Returns:
        UploadResponse with s3_uri to pass to generate_video_segment
    
    Example:
        curl -X POST "http://localhost:8000/api/v1/upload?session_id=chat_abc123" \\
             -F "file=@dog.jpg"
    """
    try:
        # Read file content
        file_content = await file.read()
        
        # Generate a secure, unique S3 key with session_id embedded
        ext = file.filename.split('.')[-1] if '.' in file.filename else "jpg"
        s3_key = f"uploads/{session_id}/{uuid.uuid4().hex}.{ext}"
        
        # Determine content type
        content_type = file.content_type or "application/octet-stream"
        if ext in ['jpg', 'jpeg']:
            content_type = 'image/jpeg'
        elif ext == 'png':
            content_type = 'image/png'
        elif ext == 'mp4':
            content_type = 'video/mp4'
        
        # Upload to S3 using existing service
        s3_uri = upload_bytes(file_content, s3_key, content_type=content_type)
        
        return UploadResponse(
            status="success",
            s3_uri=s3_uri,  # <--- PASS THIS TO THE LLM via generate_video_segment
            filename=file.filename,
            public_url=None  # Can add presigned URL if needed
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.post("/upload/presigned", response_model=PresignedUploadResponse)
async def get_presigned_upload_url(
    filename: str = Query(..., description="Original filename to determine file extension"),
    session_id: str = Query(..., description="Session ID for folder organization"),
    content_type: str = Query("image/jpeg", description="MIME type of the file")
):
    """
    Production Endpoint: Generate presigned URL for client-direct uploads.
    
    This is for advanced frontends that want to upload DIRECTLY to S3 without
    passing through your backend (saves bandwidth + latency).
    
    Workflow:
    1. Frontend requests presigned URL (GET /upload/presigned?filename=dog.jpg&session_id=chat_123)
    2. Backend generates URL with embedded session_id in the S3 path
    3. Frontend uploads file directly to S3 using the URL (PUT request)
    4. Frontend passes the s3_uri to the LLM
    
    Args:
        filename: Original filename (used to determine extension)
        session_id: The chat/project session ID (baked into S3 path for tracking)
        content_type: MIME type (e.g., "image/jpeg", "video/mp4")
    
    Returns:
        PresignedUploadResponse with upload_url and s3_uri
    
    Example:
        # Step 1: Get presigned URL
        GET /api/v1/upload/presigned?filename=dog.jpg&session_id=chat_abc123
        
        # Step 2: Upload directly to S3
        curl -X PUT "{upload_url}" --upload-file dog.jpg -H "Content-Type: image/jpeg"
        
        # Step 3: Pass s3_uri to LLM
        generate_video_segment(prompt="...", s3_uri="s3://bucket/uploads/chat_abc123/...")
    """
    try:
        result = generate_presigned_upload_url(filename, session_id, content_type)
        return PresignedUploadResponse(
            upload_url=result["upload_url"],
            s3_uri=result["s3_uri"],
            expires_in=300  # 5 minutes
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate presigned URL: {str(e)}")

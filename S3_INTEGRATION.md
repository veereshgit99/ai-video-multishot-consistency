# S3 Storage Integration - Complete Migration Guide

## 🎯 What Changed

**Before**: All files stored on local disk (`media/` directory)
**After**: All files stored in AWS S3 bucket (`ai-video-consistency`)

## ✅ Changes Implemented

### 1. New S3 Storage Service
**File**: `backend/app/services/s3_storage.py` (NEW)

**Key Functions**:
- `upload_bytes()` - Upload raw bytes to S3
- `download_bytes()` - Download from S3 by key
- `download_from_uri()` - Download using full S3 URI
- `upload_character_image()` - Upload character anchor
- `upload_video()` - Upload generated video
- `upload_continuity_frame()` - Upload flow frame
- `get_public_url()` - Generate presigned URL for sharing

**S3 URI Format**: `s3://ai-video-consistency/path/to/file.ext`

### 2. Updated Configuration

**File**: `backend/.env`
```env
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_REGION=us-east-2
S3_BUCKET_NAME=ai-video-consistency
```

**File**: `backend/app/core/config.py`
Added AWS configuration to Settings class.

### 3. Updated MCP Server Logic

**File**: `mcp_server.py`

**Changes**:
- ❌ Removed: Local file I/O (`os.makedirs`, `open()`, `f.write()`)
- ✅ Added: S3 upload/download functions
- ✅ Updated: `_extract_last_frame_bytes()` - extracts frame from bytes instead of file
- ✅ Updated: `_handle_character_logic()` - uses S3 URIs
- ✅ Updated: `generate_video_segment()` - saves to S3, returns public URL

**Key Changes**:
```python
# OLD:
output_filename = f"media/generated/{session_id}_{uuid}.mp4"
with open(output_filename, "wb") as f:
    f.write(video_bytes)

# NEW:
output_s3_uri = upload_video(video_bytes, session_id, shot_number=1)
public_url = get_public_url(output_s3_uri, expiration=86400)
```

### 4. Updated Continuity Engine

**File**: `backend/app/services/continuity/continuity_engine.py`

**Changes**:
- ✅ Added: `_load_image_from_s3()` - downloads and base64 encodes from S3
- ✅ Updated: Character anchor loading - checks if S3 URI or local path
- ✅ Updated: Flow frame loading - supports both S3 and legacy local files

**Backward Compatibility**: Still supports legacy local files for migration.

### 5. Updated Worker Tasks

**File**: `backend/app/workers/tasks.py`

**Changes**:
- ✅ Updated: `extract_dna_task()` - downloads from S3 to temp file for processing
- ✅ Updated: `render_shot_task()` - uploads video and continuity frames to S3
- ✅ Added: Temp file cleanup after processing

**Flow**:
```
S3 URI → Download bytes → Temp file → Process → Delete temp file
```

## 📊 S3 Bucket Structure

```
s3://ai-video-consistency/
├── anchors/
│   ├── chat_001/
│   │   ├── 1_abc123.jpg        # Character anchor images
│   │   └── 2_def456.jpg
│   └── chat_002/
│       └── 1_xyz789.jpg
├── generated/
│   ├── chat_001/
│   │   ├── shot_1_abc123.mp4   # Generated videos
│   │   └── shot_2_def456.mp4
│   └── chat_002/
│       └── shot_1_xyz789.mp4
└── continuity/
    ├── chat_001/
    │   └── last_frame.jpg      # Flow continuity frames
    └── chat_002/
        └── last_frame.jpg
```

## 🔄 Migration Flow

### First Shot (with uploaded image)
```
User uploads image (base64)
↓
generate_video_segment(image_base64="...")
↓
1. Raw image injected to Veo (weight 1.0)
2. Video generated (video_bytes)
3. Upload video to S3 → s3://bucket/generated/chat_001/shot_1_xxx.mp4
4. Extract frame from video_bytes
5. Upload frame to S3 → s3://bucket/anchors/chat_001/1_xxx.jpg
6. Create character record (ref_image_path = S3 URI)
7. Enqueue DNA extraction (downloads from S3, processes, updates DB)
8. Extract last frame, upload to S3 → s3://bucket/continuity/chat_001/last_frame.jpg
9. Return public URL (valid for 24 hours)
```

### Continuation Shot
```
generate_video_segment(characters_in_shot=[...])
↓
1. Load character anchor from S3 (download → base64)
2. Load flow frame from S3 (download → base64)
3. Inject both into Veo (0.8 + 0.5 weights)
4. Video generated
5. Upload to S3
6. Update flow frame in S3
7. Return public URL
```

## 🧪 Testing Checklist

### 1. Test S3 Connection
```python
from app.services.s3_storage import upload_bytes, download_bytes

# Upload test
test_data = b"Hello S3!"
uri = upload_bytes(test_data, "test/hello.txt", "text/plain")
print(f"Uploaded: {uri}")

# Download test
data = download_bytes("test/hello.txt")
print(f"Downloaded: {data.decode()}")
```

### 2. Test Character Creation
```python
# In Claude Desktop (new chat):
[Upload dog image]
"generate video of a dog playing"

# Expected:
# - Video generated
# - S3 URI returned: s3://ai-video-consistency/generated/...
# - Public URL returned: https://ai-video-consistency.s3.us-east-2.amazonaws.com/...
# - Character created with S3 anchor URI
```

### 3. Test Continuation
```python
# Second shot:
"the dog runs through the park"

# Expected:
# - Character DNA loaded from S3
# - Flow frame loaded from S3
# - New video generated with consistency
```

### 4. Test Worker DNA Extraction
```bash
# Start worker
cd backend
python worker.py

# Check logs:
# [DNA] Downloading from S3: s3://...
# [DNA] Completed extraction for Character 1
```

## 🚨 Important Notes

### No Local Media Directory Needed
- ❌ Old: `media/characters/`, `media/generated/`, `media/continuity/`
- ✅ New: Everything in S3

### Database Stores S3 URIs
- `Character.ref_image_path` → `s3://bucket/anchors/...`
- `ContinuityState.last_frame_path` → `s3://bucket/continuity/...`
- `RenderJob.output_path` → `s3://bucket/generated/...`

### Public URLs Expire
- Default: 1 hour (3600 seconds)
- Videos: 24 hours (86400 seconds)
- Use `get_public_url()` to regenerate if needed

### Backward Compatibility
- Legacy local paths still work (for migration)
- Code checks: `if path.startswith("s3://"):`
- Gradual migration supported

## 🐛 Troubleshooting

### "Access Denied" Error
```python
# Check credentials in .env
print(os.getenv("AWS_ACCESS_KEY_ID"))
print(os.getenv("AWS_SECRET_ACCESS_KEY"))

# Test S3 connection
import boto3
s3 = boto3.client('s3', 
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    region_name="us-east-2"
)
s3.list_buckets()
```

### "Bucket Not Found"
```python
# Verify bucket name
print(os.getenv("S3_BUCKET_NAME"))  # Should be "ai-video-consistency"

# Check if bucket exists
s3.head_bucket(Bucket="ai-video-consistency")
```

### Worker Can't Download from S3
```bash
# Check worker environment
cd backend
python -c "from app.services.s3_storage import download_from_uri; print('OK')"

# Check .env loaded in worker
python -c "from dotenv import load_dotenv; import os; load_dotenv(); print(os.getenv('AWS_ACCESS_KEY_ID'))"
```

## 📈 Next Steps

1. ✅ **S3 Integration Complete** - All code updated
2. ⏳ **Test First Shot** - Upload image, generate video
3. ⏳ **Test Continuation** - Verify character consistency
4. ⏳ **Monitor Costs** - S3 storage + data transfer
5. ⏳ **Add Cleanup** - Delete old videos after X days (optional)

## 💰 Cost Optimization

### S3 Pricing (us-east-2)
- **Storage**: $0.023/GB/month
- **PUT requests**: $0.005 per 1,000 requests
- **GET requests**: $0.0004 per 1,000 requests
- **Data transfer**: $0.09/GB (after 100GB free)

### Estimated Costs (100 videos/day)
- **Storage**: 100 videos × 50MB × 30 days = 150GB → $3.45/month
- **Uploads**: 100/day × 30 = 3,000 uploads → $0.015/month
- **Downloads**: 1,000/day × 30 = 30,000 downloads → $0.012/month
- **Total**: ~$3.50/month

### Cleanup Strategy (Optional)
```python
# Delete videos older than 30 days
from datetime import datetime, timedelta
from app.services.s3_storage import delete_file

# Add to scheduled task
threshold = datetime.now() - timedelta(days=30)
old_shots = db.query(Shot).filter(Shot.created_at < threshold).all()
for shot in old_shots:
    if shot.output_path and shot.output_path.startswith("s3://"):
        delete_file(shot.output_path)
```

---

**Status**: ✅ Complete - Ready for production testing
**Breaking Change**: No - backward compatible with local files
**Migration Required**: No - automatic S3 upload for new files

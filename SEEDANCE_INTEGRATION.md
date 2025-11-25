# Seedance Integration Guide

## Overview

This document covers **three Seedance models** integrated into the multi-shot continuity system:

1. **Seedance 1.0 Lite** - Image-to-video (1-4 reference images)
2. **Seedance 1.0 Pro Fast** - Text-to-video (faster generation)
3. **Seedance 1.0 Pro** - Text-to-video (higher quality)

## Seedance 1.0 Lite (Image-to-Video)

### Key Features

#### Multi-Image Support (Like Veo!)
- Accepts **1-4 reference images** (unlike Runway/MiniMax which only support 1)
- Perfect for multi-anchor strategy: character DNA + flow
- Enables better character consistency across shots

#### Flexible Configuration
- **Duration**: 2-12 seconds (configurable, default: 5s)
- **Resolution**: 480p (faster) or 720p (higher quality)
- **Aspect Ratio**: Multiple ratios supported (21:9 to 9:16, default: auto)
- **Seed**: Reproducible generation support
- **Camera Control**: `camera_fixed` option to lock camera position

#### Queue-Based API
- Submit request → Poll status → Retrieve result
- Similar to MiniMax workflow
- Async generation (2-3 minute wait time)

### Integration Architecture

#### Strategy Assignment
Seedance Lite uses the **Multi-Anchor Strategy** (same as Veo 2.0):

```
Models by Strategy:
├── Multi-Anchor (Character DNA + Flow)
│   ├── Veo 2.0 Exp (6s, $2.40/shot, image-to-video)
│   └── Seedance 1.0 Lite (2-12s, image-to-video)
│
├── Text-Only (First Shot Only)
│   ├── Veo 3.1 (6s, text-to-video)
│   ├── Seedance 1.0 Pro Fast (2-12s, text-to-video, fast)
│   └── Seedance 1.0 Pro (2-12s, text-to-video, high quality)
│
└── Flow-Only (Last Frame Only)
    ├── Runway Gen4 Turbo (5s, $0.30/shot)
    └── MiniMax Hailuo-2.3 (6s, 1080P)
```

#### File Structure
```
backend/app/services/video/
├── base.py                         # Factory function
├── google_flow.py                  # Veo 2.0 & 3.1 implementation
├── runway_flow.py                  # Runway Gen4 implementation
├── minimax_flow.py                 # MiniMax implementation
├── seedance_flow.py                # Seedance Lite (image-to-video)
├── seedance_pro_fast_flow.py       # Seedance Pro Fast (text-to-video)
└── seedance_pro_flow.py            # Seedance Pro (text-to-video) (NEW!)
```

### API Details - Seedance Lite

#### Endpoint
```
fal-ai/bytedance/seedance/v1/lite/reference-to-video
```

## Seedance 1.0 Pro Fast (Text-to-Video)

### Key Features

#### Text-Only Generation
- **NO reference images** - text-to-video only
- Fast generation speed
- For **first shot only** (no continuation support)
- Simpler prompt-based generation

#### High Quality Output
- **Resolution**: 480p, 720p, or **1080p** (default: 1080p)
- **Duration**: 2-12 seconds (configurable, default: 5s)
- **Aspect Ratio**: 21:9, 16:9, 4:3, 1:1, 3:4, 9:16 (default: 16:9)
- **Seed**: Reproducible generation support
- **Camera Control**: `camera_fixed` option

### API Details - Seedance Pro Fast

#### Endpoint
```
fal-ai/bytedance/seedance/v1/pro/fast/text-to-video
```

#### Request Format
```python
{
    "prompt": "Text description of desired video",
    "duration": 5,           # Integer: 2-12 seconds
    "resolution": "1080p",   # "480p", "720p", or "1080p"
    "aspect_ratio": "16:9",  # 21:9, 16:9, 4:3, 1:1, 3:4, 9:16
    "seed": -1,              # -1 for random
    "camera_fixed": false,   # Fix camera position
    "enable_safety_checker": true
}
```

#### Response Format
```python
{
    "video": {
        "url": "https://fal.cdn.url/video.mp4"
    },
    "seed": 12345
}
```

### Implementation - Seedance Pro Fast

**Location**: `backend/app/services/video/seedance_pro_fast_flow.py`

**Key Differences from Lite**:
- NO `_prepare_reference_images()` - text-only
- NO `_upload_to_fal_storage()` - no images to upload
- Duration is integer (not string)
- Supports 1080p resolution
- Default aspect ratio is "16:9" (not "auto")

**Routing in Continuity Engine**:
```python
# Text-only models (Veo 3.1 / Seedance Pro / Seedance Pro Fast)
if is_veo_3 or is_seedance_pro_fast or is_seedance_pro:
    final_prompt = self._enhance_prompt(prompt, state)
    video_bytes = video_service.generate_video(prompt=final_prompt, reference_images=None)
    return video_bytes
```

## Seedance 1.0 Pro (Text-to-Video)

### Key Features

#### Text-Only Generation (Higher Quality)
- **NO reference images** - text-to-video only
- **Higher quality** than Pro Fast (slower generation)
- For **first shot only** (no continuation support)
- Premium quality output

#### High Quality Output
- **Resolution**: 480p, 720p, or **1080p** (default: 1080p)
- **Duration**: 2-12 seconds (configurable, default: 5s)
- **Aspect Ratio**: 21:9, 16:9, 4:3, 1:1, 3:4, 9:16 (default: 16:9)
- **Seed**: Reproducible generation support
- **Camera Control**: `camera_fixed` option

### API Details - Seedance Pro

#### Endpoint
```
fal-ai/bytedance/seedance/v1/pro/text-to-video
```

#### Request Format
```python
{
    "prompt": "Text description of desired video",
    "duration": 5,           # Integer: 2-12 seconds
    "resolution": "1080p",   # "480p", "720p", or "1080p"
    "aspect_ratio": "16:9",  # 21:9, 16:9, 4:3, 1:1, 3:4, 9:16
    "seed": -1,              # -1 for random
    "camera_fixed": false,   # Fix camera position
    "enable_safety_checker": true
}
```

#### Response Format
```python
{
    "video": {
        "url": "https://fal.cdn.url/video.mp4"
    },
    "seed": 12345
}
```

### Implementation - Seedance Pro

**Location**: `backend/app/services/video/seedance_pro_flow.py`

**Identical to Pro Fast except**:
- Different endpoint: `fal-ai/bytedance/seedance/v1/pro/text-to-video`
- Higher quality (slower generation)
- Same API parameters and response format

### Authentication
```bash
export FAL_API_KEY="your_key_here"
```

### Request Format
```python
{
    "prompt": "Text description of desired video",
    "reference_image_urls": [
        "https://url1.jpg",  # Required - 1-4 images
        "https://url2.jpg"
    ],
    "duration": "5",         # Optional: 2-12 seconds
    "resolution": "720p",    # Optional: 480p or 720p
    "aspect_ratio": "auto",  # Optional: 21:9, 16:9, 4:3, 1:1, 3:4, 9:16, auto
    "seed": -1,              # Optional: -1 for random
    "camera_fixed": false,   # Optional: fix camera position
    "enable_safety_checker": true
}
```

### Response Format
```python
{
    "video": {
        "url": "https://fal.cdn.url/video.mp4"
    },
    "seed": 12345  # Seed used for generation
}
```

## Implementation Details

### SeedanceVideoService Class

**Location**: `backend/app/services/video/seedance_flow.py`

**Key Methods**:

1. **`generate_video()`**
   - Main entry point
   - Accepts Veo-format reference images (base64)
   - Converts to Seedance format (URLs)
   - Submits to queue and waits for completion

2. **`_prepare_reference_images()`**
   - Converts Veo reference format to Seedance format
   - Uploads base64 images to fal.ai storage
   - Returns array of image URLs
   - Validates 4-image limit

3. **`_upload_to_fal_storage()`**
   - Uploads base64 image to fal.ai CDN
   - Returns public URL for use in API
   - Handles authentication

4. **`_submit_and_wait()`**
   - Submits request to queue
   - Polls for completion (5s intervals)
   - Max wait: 5 minutes
   - Downloads video from result URL

### Continuity Engine Integration

**Location**: `backend/app/services/continuity/continuity_engine.py`

**Changes**:
1. Renamed `_generate_veo_segment()` → `_generate_multi_anchor_segment()`
2. Added `model_name` parameter for logging
3. Routes both Veo and Seedance to multi-anchor strategy:

```python
if is_veo or is_seedance:
    model_name = "Seedance" if is_seedance else "Veo"
    return self._generate_multi_anchor_segment(
        db, video_service, state, project_id, 
        prompt, raw_image_ref, model_name, continue_from_shot
    )
```

### Factory Function Update

**Location**: `backend/app/services/video/base.py`

```python
def get_video_service(model: str = "veo-2.0"):
    ...
    elif model == "seedance":
        from app.services.video.seedance_flow import SeedanceVideoService
        return SeedanceVideoService()
    elif model == "seedance-pro-fast":
        from app.services.video.seedance_pro_fast_flow import SeedanceProFastVideoService
        return SeedanceProFastVideoService()
    elif model == "seedance-pro":
        from app.services.video.seedance_pro_flow import SeedanceProVideoService
        return SeedanceProVideoService()
    ...
```

### MCP Server Update

**Location**: `mcp_server.py`

**Changes**:
1. Added "seedance" to model selection instructions (image-to-video)
2. Added "seedance-pro-fast" to model selection instructions (text-to-video, fast)
3. Added "seedance-pro" to model selection instructions (text-to-video, high quality)
4. Updated `generate_video_segment()` docstring with all Seedance options
5. No code changes needed - routing handled by continuity engine

## Configuration

### Environment Variables

Add to `backend/.env`:
```bash
FAL_API_KEY=your_fal_api_key_here
```

Add to `backend/app/core/config.py`:
```python
FAL_API_KEY: str = os.getenv("FAL_API_KEY", "")
```

### Requirements

No additional Python packages needed! Uses standard `requests` library (already in requirements).

## Usage Examples

### Seedance Lite (Image-to-Video)

#### Via MCP Server (Claude Desktop)

```python
# First shot with Seedance Lite
generate_video_segment(
    prompt="Woman doing yoga in a peaceful park at sunrise",
    session_id="chat_abc123",
    s3_uri="https://example.com/woman.jpg",
    characters_in_shot=[{"name": "Sarah", "desc": "Yoga instructor"}],
    model="seedance"  # <-- Seedance Lite!
)

# Continuation shot (uses character DNA + last frame)
generate_video_segment(
    prompt="Sarah transitions into tree pose, camera slowly orbits",
    session_id="chat_abc123",
    characters_in_shot=[{"name": "Sarah"}],
    model="seedance"
)
```

#### Multi-Character Scene
```python
# Both characters present - uses both character anchors + flow
generate_video_segment(
    prompt="Sarah and Mike practice partner yoga in the park",
    session_id="chat_abc123",
    characters_in_shot=[
        {"name": "Sarah"},
        {"name": "Mike"}
    ],
    model="seedance"
)
```

### Seedance Pro Fast (Text-to-Video)

#### Via MCP Server (Claude Desktop)

```python
# First shot ONLY - text-to-video (fast generation)
generate_video_segment(
    prompt="A serene mountain landscape at golden hour, camera slowly pans across snow-capped peaks",
    session_id="chat_abc123",
    model="seedance-pro-fast"  # <-- Seedance Pro Fast!
)
```

### Seedance Pro (Text-to-Video)

#### Via MCP Server (Claude Desktop)

```python
# First shot ONLY - text-to-video (high quality)
generate_video_segment(
    prompt="A bustling Tokyo street at night, neon lights reflecting on wet pavement, cinematic quality",
    session_id="chat_abc123",
    model="seedance-pro"  # <-- Seedance Pro!
)
```

**Note**: Both Seedance Pro models are text-only:
- ❌ Cannot be used for continuation shots
- ❌ Do not support reference images
- ✅ Best for first shots when you don't have an image
- ✅ Seedance Pro Fast: Faster generation
- ✅ Seedance Pro: Higher quality output

### Branching from Specific Shot
```python
# Continue from shot 2 instead of most recent
generate_video_segment(
    prompt="Alternative timeline: Sarah decides to meditate instead",
    session_id="chat_abc123",
    characters_in_shot=[{"name": "Sarah"}],
    model="seedance",
    continue_from_shot=2  # Branch from shot 2
)
```

## Model Comparison

### Seedance Lite vs. Runway/MiniMax
- ✅ **Multi-image support** (1-4 vs. 1)
- ✅ **Better character consistency** (multi-anchor strategy)
- ✅ **Configurable duration** (2-12s vs. fixed 5-6s)
- ✅ **Multiple aspect ratios**

### Seedance Lite vs. Veo 2.0
- ⏱️ **Speed**: TBD (need testing)
- 💰 **Cost**: TBD (need pricing research)
- 🎬 **Duration**: More flexible (2-12s vs. fixed 6s)
- ⚖️ **Quality**: TBD (need comparison)

### Seedance Pro Fast vs. Veo 3.1
- 💰 **Cost**: TBD (need pricing research)
- ⚡ **Speed**: Faster generation
- 🎬 **Duration**: More flexible (2-12s vs. fixed 6s)
- 📺 **Resolution**: 1080p (same as Veo 3.1)
- ⚖️ **Quality**: Lower than Pro (but faster)
- 🎯 **Use Case**: Same - first shot only, text-to-video

### Seedance Pro vs. Veo 3.1
- 💰 **Cost**: TBD (need pricing research)
- ⚡ **Speed**: Slower than Pro Fast
- 🎬 **Duration**: More flexible (2-12s vs. fixed 6s)
- 📺 **Resolution**: 1080p (same as Veo 3.1)
- ⚖️ **Quality**: Higher quality than Pro Fast
- 🎯 **Use Case**: Same - first shot only, text-to-video

### Seedance Pro vs. Seedance Pro Fast
- ⚡ **Speed**: Pro Fast is faster
- ⚖️ **Quality**: Pro is higher quality
- 💰 **Cost**: TBD (Pro likely more expensive)
- 🎯 **Use Case**: Both first shot only, choose based on speed vs quality preference

### When to Use Which Model?

**Seedance Lite** (`seedance`):
- Multi-character scenes requiring consistency
- Continuation shots with character DNA
- Projects needing flexible durations
- Cost-conscious users (if cheaper than Veo)

**Seedance Pro Fast** (`seedance-pro-fast`):
- First shots without reference images
- Fast text-to-video generation
- When speed matters more than quality
- Quick iterations and B-roll

**Seedance Pro** (`seedance-pro`):
- First shots without reference images
- High-quality text-to-video generation
- When quality matters more than speed
- Premium establishing shots

## Pricing Considerations

⚠️ **PRICING NOT YET RESEARCHED**

Before heavy usage:
1. Check fal.ai pricing page
2. Run single test generation
3. Monitor costs in fal.ai dashboard
4. Compare with Veo ($2.40/shot) and Runway ($0.30/shot)

**User's requirement**: "First, please be very thorough, I don't want to be wasting money by running un-necessary"

## Testing Checklist

### Before First Production Use:

- [ ] **Get API Key**: Register on fal.ai and get FAL_API_KEY
- [ ] **Research Pricing**: Check cost per generation
- [ ] **Add to .env**: Set FAL_API_KEY in backend/.env
- [ ] **Test Single Generation**: Run one test to verify:
  - API connectivity
  - Image upload to fal.ai storage
  - Queue polling works
  - Video download successful
  - Cost per generation acceptable
- [ ] **Test Multi-Image**: Verify 2-4 reference images work
- [ ] **Test Continuation**: Verify character DNA + flow strategy
- [ ] **Compare Quality**: Side-by-side with Veo and Runway
- [ ] **Monitor Costs**: Track actual spending vs. other models

### Testing Commands

```python
# Test 1: Single image generation (first shot)
python test_seedance.py --test first_shot

# Test 2: Multi-image generation (continuation)
python test_seedance.py --test continuation

# Test 3: Multi-character scene
python test_seedance.py --test multi_character

# Test 4: Branching support
python test_seedance.py --test branching
```

## Known Limitations

1. **Upload Required**: Unlike Veo (native base64), Seedance requires uploading images to fal.ai storage first
2. **Queue Delays**: 2-3 minute generation time (similar to MiniMax)
3. **Timeout Issues**: MCP client may timeout before video completes (known issue)
4. **Image Limit**: Max 4 reference images (Veo supports more)

## Error Handling

### Common Issues

**1. Authentication Error**
```
ValueError: FAL_API_KEY not found in environment variables
```
**Solution**: Add FAL_API_KEY to `.env`

**2. Image Upload Failure**
```
[SEEDANCE ERROR] Failed to upload reference image 0: ...
```
**Solution**: Check internet connectivity, verify image is valid JPEG/PNG

**3. Queue Timeout**
```
TimeoutError: Seedance generation timed out after 300s
```
**Solution**: Check fal.ai status page, retry if service is up

**4. MCP Client Timeout**
```
No result received from client-side tool execution
```
**Solution**: This is expected! Video is still generating. Wait 2-3 minutes and check S3/database.

## Future Enhancements

### Potential Optimizations

1. **Async Generation**: Background task processing to avoid MCP timeouts
2. **Caching**: Store uploaded image URLs to avoid re-uploading
3. **Batch Processing**: Submit multiple shots simultaneously
4. **Smart Duration**: Auto-adjust duration based on prompt complexity
5. **Quality Presets**: Pre-configured settings for different use cases

### Cost Optimization Strategies

1. **480p for Testing**: Use lower resolution during development
2. **Shorter Durations**: Start with 2-3s for rapid iteration
3. **Smart Model Selection**: Route simple shots to Runway, complex to Seedance
4. **Seed Reuse**: Save successful seeds for reproducibility

## Documentation

### Related Files
- `STRATEGY_REFACTORING.md` - Multi-model strategy documentation
- `RUNWAY_INTEGRATION.md` - Runway Gen4 integration guide
- `UPLOAD_ARCHITECTURE.md` - Image upload workflow

### API Documentation
- fal.ai Seedance: https://fal.ai/models/fal-ai/bytedance/seedance/v1/lite/reference-to-video/api

## Summary

Seedance integration adds **three video generation options** with unique advantages:

### Seedance 1.0 Lite (Image-to-Video)
✅ **Multi-image support** (1-4 reference images)  
✅ **Multi-anchor strategy** (character DNA + flow)  
✅ **Flexible duration** (2-12s configurable)  
✅ **Multiple aspect ratios**  

**Best for**:
- Multi-character scenes requiring strong consistency
- Projects needing flexible video durations
- Continuation shots with character DNA

**Not ideal for**:
- Ultra-fast iteration (2-3 min generation time)
- Simple single-character shots (Runway cheaper)

### Seedance 1.0 Pro Fast (Text-to-Video)
✅ **Text-only generation** (no images needed)  
✅ **Fast generation speed**  
✅ **1080p resolution support**  
✅ **Flexible duration** (2-12s configurable)  

**Best for**:
- First shots without reference images
- Fast text-to-video generation
- Quick iterations and B-roll
- Speed over quality

**Not ideal for**:
- Continuation shots (text-only, no flow support)
- Multi-character consistency (use Seedance Lite instead)

### Seedance 1.0 Pro (Text-to-Video)
✅ **Text-only generation** (no images needed)  
✅ **Higher quality output**  
✅ **1080p resolution support**  
✅ **Flexible duration** (2-12s configurable)  

**Best for**:
- First shots without reference images
- High-quality text-to-video generation
- Premium establishing shots
- Quality over speed

**Not ideal for**:
- Continuation shots (text-only, no flow support)
- Multi-character consistency (use Seedance Lite instead)
- Fast iterations (use Pro Fast instead)

**Next Steps**:
1. Get FAL_API_KEY from fal.ai
2. Research pricing for all three models
3. Run test generations for each
4. Compare quality/speed between Pro and Pro Fast
5. Make informed model selection per project

# Runway Gen4 Turbo Integration

## Overview
Integrated Runway ML's Gen4 Turbo model as an alternative to Google Veo, offering 8x cost savings ($0.30 vs $2.40 per shot).

## Changes Made

### 1. Configuration
- **Added to `.env`**: `RUNWAY_ML_API_KEY` (already present)
- **Updated `config.py`**: Added `RUNWAY_API_KEY` setting
- **Updated `config_video.py`**: Added Runway constants
  - `RUNWAY_BASE_URL`: https://api.dev.runwayml.com/v1
  - `RUNWAY_DEFAULT_MODEL`: gen4_turbo
  - `RUNWAY_DURATION`: 5 seconds (cheaper option)

### 2. New Video Provider
**File**: `backend/app/services/video/runway_flow.py`

Features:
- Text-to-video generation
- Image-to-video generation (single image input)
- Async task polling (5s intervals, 10min timeout)
- Video download from Runway CDN
- Handles data URL format for image input

### 3. Multi-Character Support
**File**: `backend/app/services/video/base.py`

New Functions:
- `create_composite_image()`: Merges multiple character DNA images into horizontal composite
- `get_video_service()`: Factory pattern to select Google or Runway based on model parameter

### 4. Continuity Engine Updates
**File**: `backend/app/services/continuity/continuity_engine.py`

Changes:
- Added `model` parameter to `generate_segment()`
- Removed hardcoded Google service initialization
- Added composite image creation for Runway (merges multi-anchor into single image)
- Dynamic service creation per-request

### 5. MCP Tool Updates
**File**: `mcp_server.py`

Changes:
- Added `model` parameter to `generate_video_segment()`
- Updated documentation with model options and pricing
- Added model selection instructions for Claude
- Default recommendation: `gen4_turbo` (8x cheaper)

## Model Comparison

| Feature | Google Veo 3.1 | Runway Gen4 Turbo |
|---------|---------------|-------------------|
| **Duration** | 6 seconds | 5 seconds |
| **Cost** | $2.40/shot | $0.30/shot |
| **Resolution** | 1280x720 | 1280x768 |
| **Image Input** | Multi-anchor (unlimited) | Single image only |
| **Weights** | Supported (0.5-1.0) | Not supported |
| **Best For** | Multi-character scenes | Single character or cost-sensitive |

## Usage Examples

### Using Runway (Cheaper)
```python
generate_video_segment(
    prompt="Woman doing yoga at sunrise",
    session_id="chat_abc123",
    s3_uri="https://example.com/woman.jpg",
    characters_in_shot=[{"name": "Sarah"}],
    model="gen4_turbo"  # 8x cheaper!
)
```

### Using Google Veo (Multi-Character)
```python
generate_video_segment(
    prompt="Sarah and John practicing yoga together",
    session_id="chat_abc123",
    characters_in_shot=[{"name": "Sarah"}, {"name": "John"}],
    model="veo-2.0"  # Better multi-character support
)
```

## How Multi-Character Works with Runway

Since Runway only accepts ONE image input, the system:

1. **Collects all character DNA images** (Sarah's anchor + John's anchor + flow frame)
2. **Creates horizontal composite** using PIL (merges side-by-side)
3. **Sends composite to Runway** as single image reference
4. **Video model sees all characters** in one reference image

Example composite layout:
```
+----------+----------+----------+
|  Sarah   |   John   |   Flow   |
| (anchor) | (anchor) | (motion) |
+----------+----------+----------+
```

## Testing Checklist

- [ ] Text-only generation (no image)
- [ ] Single character with image
- [ ] Multi-character (tests composite image merger)
- [ ] Continuation shots (character DNA reuse)
- [ ] Cost verification ($0.30 per 5s shot)
- [ ] Video quality comparison vs Veo

## Known Limitations

1. **No weight support**: Runway ignores reference image weights (always treated as 1.0)
2. **Single image only**: Multi-character support via composite merging (may reduce quality)
3. **Fixed resolution**: 1280x768 (not configurable)
4. **5s max duration**: Shorter than Veo's 6s

## Next Steps

1. Test Runway integration with real videos
2. Compare output quality: Veo vs Runway
3. Benchmark multi-character composite image quality
4. Consider adding 10s duration option (higher cost)
5. Add model selection UI in frontend

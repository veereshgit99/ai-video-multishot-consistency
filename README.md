# Multi-Shot Video Continuity Engine (Still in work)

AI-powered video generation system that maintains character consistency and visual continuity across multiple shots.

## 🎯 What It Does

Solves the biggest problem in AI video generation: **inconsistency between shots**. When you generate multiple videos, characters change appearance, scenes shift, and continuity breaks. This engine fixes that.

## ✨ Features

- **Character Continuity**: Upload reference images once, characters stay consistent across all shots
- **Scene Consistency**: Maintains lighting, color palette, and environment across shots
- **Smart Script Breakdown**: LLM-powered script analysis that generates scenes and shots automatically
- **Last-Frame Reference**: Uses the last frame of previous shots to ensure smooth transitions
- **Multi-Model Support**: Works with Veo 2.0, Gemini, and other video generation models

## 🏗️ Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   FastAPI   │────▶│    Redis     │────▶│   Worker    │
│   Backend   │     │    Queue     │     │   (RQ)      │
└─────────────┘     └──────────────┘     └─────────────┘
       │                                         │
       │                                         │
       ▼                                         ▼
┌─────────────┐                          ┌─────────────┐
│  SQLite DB  │                          │ Veo / Video │
│  (Postgres) │                          │     API     │
└─────────────┘                          └─────────────┘
```

## 🎬 How Continuity Works

1. **Character DNA Extraction**: Analyzes uploaded images for facial features, clothing, colors
2. **Scene Embedding**: Captures lighting, palette, and environment from reference frames
3. **Last-Frame Conditioning**: Extracts final frame from each shot as reference for next
4. **Seed Locking**: Uses deterministic seeds for consistency
5. **LLM-Enhanced Prompts**: Injects continuity hints into generation prompts


**Built for creators who demand consistency in AI-generated video.**
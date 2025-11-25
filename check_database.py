"""
Check SQLite database for recent video generations and their S3 locations.
"""

import sys
import os
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

# Change to backend dir to find the database
os.chdir(os.path.join(os.path.dirname(__file__), 'backend'))

from app.db.session import SessionLocal
from app import models
from datetime import datetime

db = SessionLocal()

print("=" * 70)
print("Recent Video Generations")
print("=" * 70)

# Get all shots ordered by most recent
shots = db.query(models.Shot).order_by(models.Shot.created_at.desc()).limit(10).all()

if not shots:
    print("No shots found in database.")
else:
    for shot in shots:
        print(f"\n[Shot #{shot.index}]")
        print(f"  Project ID: {shot.project_id}")
        print(f"  Description: {shot.description[:80]}...")
        print(f"  Created: {shot.created_at}")
        print(f"  Duration: {shot.duration_seconds}s")
        
        # Note: video_path is not stored in Shot model
        # Videos are stored in S3 with pattern: s3://bucket/sessions/{session_id}/videos/shot_{index}.mp4

# Get all projects (sessions)
print("\n" + "=" * 70)
print("Recent Sessions")
print("=" * 70)

projects = db.query(models.Project).order_by(models.Project.id.desc()).limit(5).all()

for proj in projects:
    print(f"\n[Project {proj.id}] {proj.name}")
    print(f"  Description: {proj.description}")
    
    # Get shot count
    shot_count = db.query(models.Shot).filter(models.Shot.project_id == proj.id).count()
    print(f"  Shots: {shot_count}")
    
    # Get characters
    chars = db.query(models.Character).filter(models.Character.project_id == proj.id).all()
    if chars:
        print(f"  Characters: {', '.join([c.name for c in chars])}")

# Get continuity states
print("\n" + "=" * 70)
print("Continuity States (Last Frame Paths)")
print("=" * 70)

states = db.query(models.ContinuityState).order_by(models.ContinuityState.id.desc()).limit(5).all()

for state in states:
    print(f"\n[State {state.id}] Project {state.project_id}")
    print(f"  Session: {state.session_id}")
    print(f"  Last Frame: {state.last_frame_path}")
    print(f"  Active Characters: {state.active_character_ids}")

db.close()

print("\n" + "=" * 70)
print("Note: Videos are stored in S3 at:")
print("s3://ai-video-consistency/sessions/{session_id}/videos/shot_{index}.mp4")
print("=" * 70)

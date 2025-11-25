"""
Database migration script to add per-shot last frame tracking.
Adds last_frame_path and video_path columns to shots table.
"""

import sys
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_dir))

import os
os.chdir(str(backend_dir))

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import text
from app.db.session import engine, SessionLocal

def migrate():
    """Add new columns to shots table."""
    
    with engine.connect() as conn:
        try:
            # Check if columns already exist
            result = conn.execute(text("PRAGMA table_info(shots)"))
            columns = {row[1] for row in result}
            
            if 'last_frame_path' not in columns:
                print("Adding last_frame_path column to shots table...")
                conn.execute(text("""
                    ALTER TABLE shots 
                    ADD COLUMN last_frame_path VARCHAR(1024)
                """))
                conn.commit()
                print("✅ Added last_frame_path column")
            else:
                print("ℹ️  last_frame_path column already exists")
            
            if 'video_path' not in columns:
                print("Adding video_path column to shots table...")
                conn.execute(text("""
                    ALTER TABLE shots 
                    ADD COLUMN video_path VARCHAR(1024)
                """))
                conn.commit()
                print("✅ Added video_path column")
            else:
                print("ℹ️  video_path column already exists")
            
            print("\n✅ Migration completed successfully!")
            
        except Exception as e:
            print(f"❌ Migration failed: {e}")
            conn.rollback()
            raise

if __name__ == "__main__":
    migrate()

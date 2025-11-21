# create_db.py - Create database tables
import sys
from pathlib import Path

# Add backend directory to Python path
backend_dir = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_dir))

from app.db.base import Base
from app.db.session import engine
from app import models  # This imports all models

print("Creating database tables...")
Base.metadata.create_all(bind=engine)
print("✅ Database tables created successfully!")

# List created tables
from sqlalchemy import inspect
inspector = inspect(engine)
tables = inspector.get_table_names()
print(f"\n📊 Created {len(tables)} tables:")
for table in tables:
    print(f"   - {table}")

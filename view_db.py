"""
Simple script to view the contents of app.db
"""
import sqlite3
import json
from pathlib import Path

# Connect to database
db_path = Path(__file__).parent / "backend" / "app.db"
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row  # Access columns by name
cursor = conn.cursor()

print("=" * 80)
print("DATABASE CONTENTS: app.db")
print("=" * 80)

# Projects
print("\n📁 PROJECTS (Sessions):")
print("-" * 80)
cursor.execute("SELECT * FROM projects ORDER BY created_at DESC")
projects = cursor.fetchall()
for p in projects:
    print(f"  ID: {p['id']} | Name: {p['name']}")
    print(f"  Description: {p['description']}")
    print(f"  Created: {p['created_at']}")
    print()

# Characters
print("\n👤 CHARACTERS:")
print("-" * 80)
cursor.execute("""
    SELECT c.*, p.name as project_name 
    FROM characters c 
    JOIN projects p ON c.project_id = p.id 
    ORDER BY c.created_at DESC
""")
characters = cursor.fetchall()
for c in characters:
    print(f"  ID: {c['id']} | Name: {c['name']} | Project: {c['project_name']}")
    print(f"  Description: {c['description']}")
    print(f"  Anchor Image: {c['ref_image_path']}")
    has_dna = "✅" if c['face_embedding'] else "❌"
    print(f"  Has DNA: {has_dna}")
    print()

# Shots
print("\n🎬 SHOTS:")
print("-" * 80)
cursor.execute("""
    SELECT s.*, p.name as project_name 
    FROM shots s 
    JOIN projects p ON s.project_id = p.id 
    ORDER BY s.created_at DESC
    LIMIT 20
""")
shots = cursor.fetchall()
for s in shots:
    print(f"  Shot #{s['index']} | Project: {s['project_name']}")
    print(f"  Description: {s['description'][:60]}...")
    print(f"  Created: {s['created_at']}")
    print()

# Continuity States
print("\n🔄 CONTINUITY STATES:")
print("-" * 80)
cursor.execute("""
    SELECT cs.*, p.name as project_name 
    FROM continuity_states cs 
    JOIN projects p ON cs.project_id = p.id
""")
states = cursor.fetchall()
for s in states:
    print(f"  Project: {s['project_name']} (Session: {s['session_id']})")
    print(f"  Last Frame: {s['last_frame_path']}")
    if s['active_character_ids']:
        char_ids = json.loads(s['active_character_ids'])
        print(f"  Active Characters: {char_ids}")
    if s['narrative_context']:
        print(f"  Narrative: {s['narrative_context']}")
    print()

# Statistics
print("\n📊 STATISTICS:")
print("-" * 80)
cursor.execute("SELECT COUNT(*) FROM projects")
print(f"  Total Projects: {cursor.fetchone()[0]}")
cursor.execute("SELECT COUNT(*) FROM characters")
print(f"  Total Characters: {cursor.fetchone()[0]}")
cursor.execute("SELECT COUNT(*) FROM shots")
print(f"  Total Shots: {cursor.fetchone()[0]}")
cursor.execute("SELECT COUNT(*) FROM characters WHERE face_embedding IS NOT NULL")
print(f"  Characters with DNA: {cursor.fetchone()[0]}")

conn.close()
print("\n" + "=" * 80)

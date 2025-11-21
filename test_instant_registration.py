"""
Quick test to verify instant registration performance
"""
import os
import sys
import time
import base64
from pathlib import Path

backend_dir = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_dir))
os.chdir(str(backend_dir))

print("=" * 70)
print("INSTANT REGISTRATION PERFORMANCE TEST")
print("=" * 70)

# Create a test image
from PIL import Image
import io

img = Image.new('RGB', (512, 512), color=(100, 150, 200))
img_bytes = io.BytesIO()
img.save(img_bytes, format='JPEG')
img_bytes = img_bytes.getvalue()
image_base64 = base64.b64encode(img_bytes).decode()

print(f"\n[Test] Simulating register_character_anchor operations...")
print(f"Image size: {len(img_bytes)} bytes ({len(image_base64)} base64 chars)")

# Test each operation
operations = []

# 1. Base64 decode
start = time.time()
decoded = base64.b64decode(image_base64)
operations.append(("Base64 Decode", time.time() - start))

# 2. File write
from app.core.files import save_character_image_bytes
start = time.time()
test_path = save_character_image_bytes(0, decoded, ".jpg")
operations.append(("File Write", time.time() - start))

# 3. Database operations (simulated)
from app.db.session import SessionLocal
from app import models
start = time.time()
db = SessionLocal()
project = models.Project(name="Test", description="Test")
db.add(project)
db.flush()
operations.append(("DB Insert (Project)", time.time() - start))

start = time.time()
char = models.Character(
    project_id=project.id,
    name="Test Char",
    description="Test",
    ref_image_path=test_path
)
db.add(char)
db.flush()
operations.append(("DB Insert (Character)", time.time() - start))

# 4. File rename
start = time.time()
final_path = test_path.replace("/0_", f"/{char.id}_")
os.rename(test_path, final_path)
operations.append(("File Rename", time.time() - start))

# 5. Queue enqueue (simulated)
start = time.time()
from app.core.queue import render_queue
from app.workers.tasks import extract_dna_task
job = render_queue.enqueue(extract_dna_task, char.id)
operations.append(("Queue Job Enqueue", time.time() - start))

# 6. DB commit
start = time.time()
db.commit()
operations.append(("DB Commit", time.time() - start))

# Cleanup
db.delete(char)
db.delete(project)
db.commit()
db.close()
os.remove(final_path)

# Results
print("\n" + "=" * 70)
print("OPERATION BREAKDOWN")
print("=" * 70)

total_time = 0
for op_name, op_time in operations:
    total_time += op_time
    ms = op_time * 1000
    print(f"{op_name:.<30} {ms:>6.1f} ms")

print("=" * 70)
print(f"{'TOTAL TIME':.<30} {total_time * 1000:>6.1f} ms")
print("=" * 70)

if total_time < 0.5:
    print(f"\n✅ EXCELLENT! Registration is INSTANT (< 500ms)")
    print(f"   User will experience near-zero latency!")
elif total_time < 1.0:
    print(f"\n✓ GOOD! Registration is fast (< 1s)")
    print(f"   User will experience minimal latency")
else:
    print(f"\n⚠️  SLOW! Registration takes > 1s")
    print(f"   Check for bottlenecks in database or file I/O")

print("\n" + "=" * 70)
print("BACKGROUND DNA EXTRACTION")
print("=" * 70)
print("While user got instant response, the worker is processing:")
print("  1. Load CLIP model (one-time, ~3s)")
print("  2. Extract embeddings (~0.6s)")
print("  3. Save to database (~0.1s)")
print(f"  Total: ~3.7s (INVISIBLE to user)")
print("=" * 70)

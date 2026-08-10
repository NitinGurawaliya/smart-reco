"""Inspect the app DB and print free_resources count and a sample of titles."""
import sys
import os
sys.path.insert(0, './backend')
# Load .env from backend so Settings can read DATABASE_URL when invoked
env_path = os.path.join(os.getcwd(), 'backend', '.env')
if os.path.exists(env_path):
    try:
        from dotenv import load_dotenv

        load_dotenv(env_path)
    except Exception:
        pass

from app.config import settings
from app.database import SessionLocal
from app.models import FreeResource

db = SessionLocal()
try:
    rows = db.query(FreeResource).order_by(FreeResource.id.asc()).all()
    print("DATABASE_URL:", settings.DATABASE_URL)
    print("free_resources count:", len(rows))
    sample = [r.title for r in rows[:30]]
    print("sample titles (up to 30):")
    for t in sample:
        print(" -", t)
finally:
    db.close()

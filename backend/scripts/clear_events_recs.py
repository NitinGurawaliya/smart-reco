import sys
import os
# Safety: require explicit TEST_DATABASE_URL (or TARGET_DATABASE_URL) to run
# This prevents accidental writes to the live app database.
TEST_DB = os.environ.get('TEST_DATABASE_URL') or os.environ.get('TARGET_DATABASE_URL')
if not TEST_DB:
    print("Refusing to run: set TEST_DATABASE_URL to a test database (will not modify live DATABASE_URL).")
    sys.exit(1)

# Ensure backend package importable when run from repo root
sys.path.insert(0, './backend')
# Load backend .env defaults when running from repo root
env_path = os.path.join(os.getcwd(), 'backend', '.env')
if os.path.exists(env_path):
    try:
        from dotenv import load_dotenv

        load_dotenv(env_path)
    except Exception:
        pass

# Override DATABASE_URL to the explicit test DB for safety
os.environ['DATABASE_URL'] = TEST_DB
os.environ.setdefault('JWT_SECRET', 'dev-test-secret')

from app.database import SessionLocal
from app.models import Event, Recommendation
import logging

logger = logging.getLogger("scripts.clear_events_recs")

with SessionLocal() as db:
    e = db.query(Event).delete()
    r = db.query(Recommendation).delete()
    db.commit()
    logger.info("Deleted events=%s recommendations=%s", e, r)

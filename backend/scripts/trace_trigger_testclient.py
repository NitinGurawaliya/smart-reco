"""Use FastAPI TestClient to POST /events and print full JSON responses for each POST.
Runs on a fresh DB to avoid prior cooldown.
"""
import os
import sys
import time
from datetime import datetime, timezone

# Require explicit TEST_DATABASE_URL to avoid touching the live app DB
TEST_DB = os.environ.get('TEST_DATABASE_URL') or os.environ.get('TARGET_DATABASE_URL')
if not TEST_DB:
    print("Refusing to run: set TEST_DATABASE_URL to a test database (will not modify live DATABASE_URL).")
    sys.exit(1)

sys.path.insert(0, str("./backend"))
# override
os.environ['DATABASE_URL'] = TEST_DB

from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal, Base, engine

# Ensure DB tables exist before creating test data
Base.metadata.create_all(bind=engine)
from app.models import User, FreeResource
from app.auth import create_access_token, hash_password
from app.trigger import maybe_run_agent
from datetime import timedelta

# clean DB file will be created by app startup; ensure no leftover
# The DATABASE_URL env must point to the desired file; script caller should set it.

# create a fresh user and seed resources
with SessionLocal() as db:
    db.query(FreeResource).delete()
    db.query(User).delete()
    db.commit()
    user = User(email=f"tc+{int(time.time())}@example.com", password_hash=hash_password("password"), role="user")
    db.add(user)
    db.commit()
    db.refresh(user)

    fr1 = FreeResource(title="Intro to React - Free", description="", topic_tags=[], youtube_url="", level="beginner", category="web-development", sync_status="ok")
    fr2 = FreeResource(title="Advanced React Patterns - Free", description="", topic_tags=[], youtube_url="", level="intermediate", category="web-development", sync_status="ok")
    fr3 = FreeResource(title="React Hooks Deep Dive - Free", description="", topic_tags=[], youtube_url="", level="intermediate", category="web-development", sync_status="ok")
    db.add_all([fr1, fr2, fr3])
    db.commit()
    print("Seeded user id=", user.id, "resources=", [fr1.id, fr2.id, fr3.id])

# generate token
token = create_access_token(user_id=user.id, role=user.role)
headers = {"Authorization": f"Bearer {token}"}

# monkeypatch trigger.run_agent to a fast stub that stores a rec
import app.trigger as trigger_mod
from sqlalchemy.orm import Session
from app.models import Recommendation

orig_run_agent = trigger_mod.run_agent if hasattr(trigger_mod, "run_agent") else None

def fake_run_agent(db: Session, *, user_id: int, trigger_reason: str):
    now = datetime.now(timezone.utc)
    rows = db.query(FreeResource).limit(3).all()
    ids = [r.id for r in rows]
    # set expires_at in future so cooldown applies realistically
    rec = Recommendation(
        user_id=user_id,
        narrative="TC simulated rec",
        resource_ids=ids,
        match_meta=[{"resource_id": ids[0], "because": "sim"}],
        source_summary={"family":"frontend"},
        trigger_reason=trigger_reason,
        generated_at=now,
        expires_at=now + timedelta(seconds=3600),
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)
    print(f"[fake_run_agent] stored rec id={rec.id}")
    return rec

trigger_mod.run_agent = fake_run_agent

client = TestClient(app)

courseA = {"event_type": "view", "source": "udemy", "raw_metadata": {"courseId": "A", "title": "Course A", "category": "React"}}
courseB = {"event_type": "view", "source": "udemy", "raw_metadata": {"courseId": "B", "title": "Course B", "category": "React"}}
courseC = {"event_type": "view", "source": "udemy", "raw_metadata": {"courseId": "C", "title": "Course C", "category": "React"}}
courseD = {"event_type": "view", "source": "udemy", "raw_metadata": {"courseId": "D", "title": "Course D", "category": "React"}}

print("Starting TestClient sequence at", datetime.now(timezone.utc).isoformat())

def post_events(ev):
    resp = client.post("/events", headers=headers, json={"events": [ev]})
    print("POST /events -> status", resp.status_code)
    try:
        print("RESPONSE JSON:", resp.json())
    except Exception as exc:
        print("Failed to decode JSON response:", exc, resp.text)

post_events(courseA)
time.sleep(2)
post_events(courseB)
time.sleep(2)
post_events(courseC)  # this should trigger
# short wait
time.sleep(1)
post_events(courseD)

# restore
if orig_run_agent:
    trigger_mod.run_agent = orig_run_agent

print("TestClient sequence complete.")

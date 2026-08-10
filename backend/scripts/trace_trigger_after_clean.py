"""Run AFTER-only DB simulation on a fresh DB to avoid cooldown contamination.
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
os.environ['DATABASE_URL'] = TEST_DB

from app.database import engine, Base, SessionLocal
from app.models import User, FreeResource, Event, Recommendation
from app.agent import clustering
from app.pipeline_log import pipe

# remove existing test DB
db_path = "backend_test_after.db"
if os.path.exists(db_path):
    os.remove(db_path)

# point the SQLALCHEMY to use this file by env override is easier, but the app's engine is already configured in database.py
# We'll just recreate tables on the engine (which uses DATABASE_URL env), so ensure DATABASE_URL env used earlier points to sqlite:///./backend_test_after.db

print("Creating fresh DB and tables...")
Base.metadata.create_all(bind=engine)

# clear
with SessionLocal() as db:
    db.query(Event).delete()
    db.query(Recommendation).delete()
    db.query(User).delete()
    db.query(FreeResource).delete()
    db.commit()

with SessionLocal() as db:
    user = User(email=f"trace_after+{int(time.time())}@example.com", password_hash="x", role="user")
    db.add(user)
    db.commit()
    db.refresh(user)
    user_id = user.id
    print("Created user id=", user_id)

    fr1 = FreeResource(title="Intro to React - Free", description="", topic_tags=[], youtube_url="", level="beginner", category="web-development", sync_status="ok")
    fr2 = FreeResource(title="Advanced React Patterns - Free", description="", topic_tags=[], youtube_url="", level="intermediate", category="web-development", sync_status="ok")
    fr3 = FreeResource(title="React Hooks Deep Dive - Free", description="", topic_tags=[], youtube_url="", level="intermediate", category="web-development", sync_status="ok")
    db.add_all([fr1, fr2, fr3])
    db.commit()
    db.refresh(fr1); db.refresh(fr2); db.refresh(fr3)
    print("Seeded free resources ids=", [fr1.id, fr2.id, fr3.id])

# monkeypatch clustering hint to return confident majority for frontend
orig_hint = clustering.get_family_guardrail_hint

def confident_hint(events):
    return {"confident": True, "family_counts": {"frontend": len(events)}, "family": "frontend", "confidence_reason": "confident_majority"}

clustering.get_family_guardrail_hint = confident_hint

from app.trigger import evaluate_trigger, maybe_run_agent

courseA = {"event_type": "view", "source": "udemy", "raw_metadata": {"courseId": "A", "title": "Course A", "category": "React"}}
courseB = {"event_type": "view", "source": "udemy", "raw_metadata": {"courseId": "B", "title": "Course B", "category": "React"}}
courseC = {"event_type": "view", "source": "udemy", "raw_metadata": {"courseId": "C", "title": "Course C", "category": "React"}}
courseD = {"event_type": "view", "source": "udemy", "raw_metadata": {"courseId": "D", "title": "Course D", "category": "React"}}

with SessionLocal() as db:
    # reuse the committed user id
    # (user object from previous session is not available here)
    uid_row = db.query(User).order_by(User.id.desc()).first()
    user_id = uid_row.id
    def post_and_check(events):
        rows = []
        for ev in events:
            e = Event(user_id=user_id, event_type=ev["event_type"], source=ev.get("source","udemy"), raw_metadata=ev.get("raw_metadata", {}))
            db.add(e)
            db.commit()
            db.refresh(e)
            rows.append(e)
            print(f"Inserted event id={e.id} course={e.raw_metadata.get('courseId')} ts={e.created_at.isoformat()}")
        decision = evaluate_trigger(db, user_id)
        print(f"EVALUATE_TRIGGER -> should_run={decision.should_run} reason={decision.reason} skip={decision.skip_reason} new_count={decision.new_event_count} cooldown_remaining={decision.cooldown_remaining}")
        triggered, reason, rec = maybe_run_agent(db, user_id)
        print(f"MAYBE_RUN_AGENT -> triggered={triggered} reason={reason} rec_id={(rec.id if rec else None)}")
        if rec:
            print(f"REC STORED id={rec.id} generated_at={rec.generated_at.isoformat()} resources={rec.resource_ids} trigger_reason={rec.trigger_reason}")

    print("Start sequence at", datetime.now(timezone.utc).isoformat())
    post_and_check([courseA])
    time.sleep(2)
    post_and_check([courseB])
    time.sleep(2)
    post_and_check([courseC])
    print("waiting 1s")
    time.sleep(1)
    post_and_check([courseD])

# restore
clustering.get_family_guardrail_hint = orig_hint
print("Done AFTER clean run.")

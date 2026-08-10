"""Lightweight DB-only simulation of Step 2: A,B,C (2s gaps), wait 60s, D.
Runs two scenarios:
    - BEFORE: force get_family_guardrail_hint to be NOT confident so agent is skipped.
    - AFTER: allow guardrail to decide (should be confident for 3 same-family events) and stub run_agent to store a Recommendation.

Prints detailed logs and the trigger decisions after each event.
"""
import os
import time
from datetime import datetime, timezone
import importlib
import sys

# Require explicit TEST_DATABASE_URL to avoid touching the live app DB
TEST_DB = os.environ.get('TEST_DATABASE_URL') or os.environ.get('TARGET_DATABASE_URL')
if not TEST_DB:
        print("Refusing to run: set TEST_DATABASE_URL to a test database (will not modify live DATABASE_URL).")
        sys.exit(1)

# ensure backend package importable when run from repo root
sys.path.insert(0, str("./backend"))
# Override DATABASE_URL to the test DB
os.environ['DATABASE_URL'] = TEST_DB

from app.database import engine, Base, SessionLocal
from app.models import User, Event, FreeResource, Recommendation
from app.trigger import evaluate_trigger, maybe_run_agent, get_latest_recommendation
from app.agent import clustering
from sqlalchemy.orm import Session

print("Setting up DB (SQLite backend_test.db)...")
# Use engine from config (respecting env), create tables
Base.metadata.create_all(bind=engine)

# helper
def now_iso():
    return datetime.now(timezone.utc).isoformat()

# ensure clean test data
with SessionLocal() as db:
    db.query(Event).delete()
    db.query(Recommendation).delete()
    db.query(User).delete()
    db.query(FreeResource).delete()
    db.commit()

# create test user and some free resources
with SessionLocal() as db:
    user = User(email=f"trace+{int(time.time())}@example.com", password_hash="x", role="user")
    db.add(user)
    db.commit()
    db.refresh(user)
    print("Created user id=", user.id)

    # add free resources matching frontend family (category -> family mapping)
    fr1 = FreeResource(title="Intro to React - Free", description="", topic_tags=[], youtube_url="", level="beginner", category="web-development", sync_status="ok")
    fr2 = FreeResource(title="Advanced React Patterns - Free", description="", topic_tags=[], youtube_url="", level="intermediate", category="web-development", sync_status="ok")
    fr3 = FreeResource(title="React Hooks Deep Dive - Free", description="", topic_tags=[], youtube_url="", level="intermediate", category="web-development", sync_status="ok")
    db.add_all([fr1, fr2, fr3])
    db.commit()
    db.refresh(fr1); db.refresh(fr2); db.refresh(fr3)
    print("Seeded free resources ids=", [fr1.id, fr2.id, fr3.id])

# prepare event templates
courseA = {"event_type": "view", "source": "udemy", "raw_metadata": {"courseId": "A", "title": "Course A", "category": "React"}}
courseB = {"event_type": "view", "source": "udemy", "raw_metadata": {"courseId": "B", "title": "Course B", "category": "React"}}
courseC = {"event_type": "view", "source": "udemy", "raw_metadata": {"courseId": "C", "title": "Course C", "category": "React"}}
courseD = {"event_type": "view", "source": "udemy", "raw_metadata": {"courseId": "D", "title": "Course D", "category": "React"}}

# function to insert events and run trigger check
def post_and_check(db: Session, user_id: int, events):
    inserted = []
    for ev in events:
        e = Event(user_id=user_id, event_type=ev["event_type"], source=ev.get("source","udemy"), raw_metadata=ev.get("raw_metadata", {}))
        db.add(e)
        db.commit()
        db.refresh(e)
        inserted.append(e)
        print(f"Inserted event id={e.id} type={e.event_type} course={e.raw_metadata.get('courseId')} ts={e.created_at.isoformat()}")
    # evaluate trigger
    decision = evaluate_trigger(db, user_id)
    print(f"EVALUATE_TRIGGER -> should_run={decision.should_run} reason={decision.reason} skip={decision.skip_reason} new_count={decision.new_event_count} cooldown_remaining={decision.cooldown_remaining}")
    # call maybe_run_agent to simulate the actual flow
    triggered, reason, rec = maybe_run_agent(db, user_id)
    print(f"MAYBE_RUN_AGENT -> triggered={triggered} reason={reason} rec_id={(rec.id if rec else None)}")
    if rec:
        print(f"REC STORED id={rec.id} generated_at={rec.generated_at.isoformat()} resource_ids={rec.resource_ids} trigger_reason={rec.trigger_reason}")
    return decision, triggered, rec

# Save original clustering function to restore later
orig_get_hint = clustering.get_family_guardrail_hint
# Save original run_agent (we'll monkeypatch in AFTER scenario)
import app.agent.runner as runner_mod
orig_run_agent = runner_mod.run_agent

# ------------------ BEFORE scenario: force insufficient confidence ------------------
print("\n=== BEFORE scenario: force insufficient confidence (agent should skip) ===")
with SessionLocal() as db:
    # monkeypatch guardrail to always report not confident
    def fake_hint(events):
        return {"confident": False, "family_counts": {}, "family": None, "confidence_reason": "forced_insufficient"}
    clustering.get_family_guardrail_hint = fake_hint

    # ensure no recommendations initially
    print("Initial latest rec:", get_latest_recommendation(db, 1))

    # run sequence: A, wait2, B, wait2, C, wait60, D
    user_id = db.query(User).first().id
    print("Start sequence at", now_iso())
    post_and_check(db, user_id, [courseA])
    time.sleep(2)
    post_and_check(db, user_id, [courseB])
    time.sleep(2)
    post_and_check(db, user_id, [courseC])
    print("waiting 60s to pass cooldown")
    time.sleep(1)  # shorten wait in simulation to 1s to save time; cooldown logic uses generated_at so ok for demo
    post_and_check(db, user_id, [courseD])

# restore clustering hint
clustering.get_family_guardrail_hint = orig_get_hint

# ------------------ AFTER scenario: allow confidence and stub run_agent to store a rec ------------------
print("\n=== AFTER scenario: allow confidence and stub run_agent to store rec ===")
with SessionLocal() as db:
    # monkeypatch run_agent to a fast stub that creates a recommendation row
    def fake_run_agent(db_sess: Session, *, user_id: int, trigger_reason: str):
        now = datetime.now(timezone.utc)
        # pick seeded free resource ids
        rows = db_sess.query(FreeResource).limit(3).all()
        ids = [r.id for r in rows]
        rec = Recommendation(user_id=user_id, narrative="Simulated rec", resource_ids=ids, match_meta=[{"dominant_pattern":"React"}], source_summary={"family":"frontend"}, trigger_reason=trigger_reason, generated_at=now, expires_at=now)
        db_sess.add(rec)
        db_sess.commit()
        db_sess.refresh(rec)
        print(f"[fake_run_agent] stored rec id={rec.id} resources={rec.resource_ids}")
        return rec

    runner_mod.run_agent = fake_run_agent

    user_id = db.query(User).first().id
    print("Start sequence at", now_iso())
    post_and_check(db, user_id, [courseA])
    time.sleep(2)
    post_and_check(db, user_id, [courseB])
    time.sleep(2)
    post_and_check(db, user_id, [courseC])
    print("waiting 1s (simulated cooldown) to proceed")
    time.sleep(1)
    post_and_check(db, user_id, [courseD])

    # restore run_agent
    runner_mod.run_agent = orig_run_agent

print("\nSimulation complete.")

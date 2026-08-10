"""
Scripted trigger-pipeline session (Step 2 / Step 5).

Simulates:
  View A (2s) → B (2s) → C (2s) → wait 60s → View D
WITHOUT calling /recommendations/refresh.

Usage (from backend/):
  python scripts/trace_trigger_session.py
"""

from __future__ import annotations

import json
import sys
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

# Require explicit TEST_DATABASE_URL to avoid touching the live app DB
TEST_DB = os.environ.get('TEST_DATABASE_URL') or os.environ.get('TARGET_DATABASE_URL')
if not TEST_DB:
    print("Refusing to run: set TEST_DATABASE_URL to a test database (will not modify live DATABASE_URL).")
    sys.exit(1)

# Allow `python scripts/...` from backend/
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
# Override database to test DB
os.environ['DATABASE_URL'] = TEST_DB

from sqlalchemy.orm import Session

from app.auth import create_access_token, hash_password
from app.database import SessionLocal
from app.models import Event, Recommendation, User
from app.trigger import maybe_run_agent, evaluate_trigger, get_agent_status


COURSES = [
    {
        "courseId": "c4",
        "title": "React — The Complete Guide 2024",
        "category": "React",
        "level": "intermediate",
    },
    {
        "courseId": "c37",
        "title": "React Hooks Deep Dive",
        "category": "React",
        "level": "intermediate",
    },
    {
        "courseId": "c38",
        "title": "React Query / TanStack Query Masterclass",
        "category": "React",
        "level": "intermediate",
    },
    {
        "courseId": "c40",
        "title": "Testing React Apps with Jest & RTL",
        "category": "React",
        "level": "intermediate",
    },
]


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%H:%M:%S.%f")[:-3]


def log(msg: str) -> None:
    print(f"[TRACE {_ts()}] {msg}", flush=True)


def post_view(db: Session, user: User, course: dict) -> dict:
    """Mimic POST /events single view + maybe_run_agent (same as API)."""
    from app.pipeline_log import pipe

    pipe(
        "EVENTS_POST",
        user_id=user.id,
        batch_n=1,
        events=[{"type": "view", **{k: course[k] for k in ("courseId", "category", "title")}}],
    )
    ev = Event(
        user_id=user.id,
        event_type="view",
        source="udemy",
        raw_metadata=dict(course),
    )
    db.add(ev)
    db.commit()
    pipe("EVENTS_INSERTED", user_id=user.id, inserted=1, skipped_dedupe=0)

    # Snapshot trigger state BEFORE maybe_run
    decision = evaluate_trigger(db, user.id)
    status = get_agent_status(db, user.id)
    log(
        f"PRE_MAYBE user={user.id} should_run={decision.should_run} "
        f"skip={decision.skip_reason} reason={decision.reason} "
        f"new_count={decision.new_event_count} cooldown_rem={decision.cooldown_remaining:.1f} "
        f"ready_to_run={status.get('ready_to_run')} status_skip={status.get('skip_reason')}"
    )

    triggered, reason, rec = maybe_run_agent(db, user.id)
    out = {
        "triggered": triggered,
        "trigger_reason": reason,
        "rec_id": rec.id if rec else None,
        "generated_at": rec.generated_at.isoformat() if rec and rec.generated_at else None,
        "resource_ids": list(rec.resource_ids or []) if rec else None,
        "narrative": (rec.narrative[:80] if rec and rec.narrative else None),
        "source_summary": rec.source_summary if rec else None,
    }
    pipe(
        "EVENTS_RESPONSE",
        user_id=user.id,
        inserted=1,
        triggered=triggered,
        trigger_reason=reason,
        rec_id=out["rec_id"],
        rec_generated_at=out["generated_at"],
    )
    # Simulate frontend apply from event response
    if triggered and rec:
        log(
            f"FE_WOULD_APPLY source=event_response id={rec.id} "
            f"generated_at={out['generated_at']} resources={out['resource_ids']}"
        )
    elif triggered and not rec:
        log("FE_WOULD_FETCH_LATEST source=event_triggered_no_body")
    else:
        log(f"FE_NO_UPDATE triggered=False reason={reason}")
    return out


def ensure_fresh_user(db: Session) -> User:
    email = f"pipe_trace_{uuid.uuid4().hex[:8]}@test.local"
    user = User(email=email, password_hash=hash_password("test1234"), role="user")
    db.add(user)
    db.commit()
    db.refresh(user)
    log(f"FRESH_USER id={user.id} email={email}")
    return user


def main() -> None:
    db = SessionLocal()
    try:
        user = ensure_fresh_user(db)
        results = []

        for i, course in enumerate(COURSES[:3]):
            label = chr(ord("A") + i)
            log(f"=== VIEW {label}: {course['title']} ({course['category']}) ===")
            results.append(post_view(db, user, course))
            log(f"sleep 2s after {label}")
            time.sleep(2)

        log("=== WAIT 60s (past cooldown) — NO events ===")
        # During wait, show that nothing auto-fires without a new POST
        for t in (15, 30, 45, 60):
            time.sleep(15 if t > 0 else 0)
            st = get_agent_status(db, user.id)
            dec = evaluate_trigger(db, user.id)
            log(
                f"WAIT_T+{t}s should_run={dec.should_run} skip={dec.skip_reason} "
                f"new_count={dec.new_event_count} cooldown_rem={dec.cooldown_remaining:.1f} "
                f"ready_to_run={st.get('ready_to_run')} "
                f"(NOTE: no maybe_run_agent without new POST/status trigger)"
            )

        log(f"=== VIEW D: {COURSES[3]['title']} ===")
        results.append(post_view(db, user, COURSES[3]))

        log("=== SESSION SUMMARY ===")
        print(json.dumps(results, indent=2, default=str))
        recs = (
            db.query(Recommendation)
            .filter(Recommendation.user_id == user.id)
            .order_by(Recommendation.generated_at.asc())
            .all()
        )
        log(f"total_recommendations_stored={len(recs)}")
        for r in recs:
            log(
                f"  rec id={r.id} at={r.generated_at} reason={r.trigger_reason} "
                f"ids={r.resource_ids} narrative={(r.narrative or '')[:60]!r}"
            )
    finally:
        db.close()


if __name__ == "__main__":
    main()

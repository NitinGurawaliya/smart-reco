"""Safely identify and (optionally) delete clearly-fake/test rows from the
running app database. This script is conservative by default: it only lists
matches unless you set the environment variable `CONFIRM=1` to actually delete
the found rows.

Usage (from repo root):
  # inspect what would be removed
  python backend/scripts/cleanup_fake_rows.py

  # actually delete (intentional):
  CONFIRM=1 python backend/scripts/cleanup_fake_rows.py

WARNING: This will connect to the database configured by the running app
(`app.config.settings.DATABASE_URL`). Be deliberate before setting `CONFIRM`.
"""
import os
import sys
from typing import List

sys.path.insert(0, './backend')

# Load .env if present so settings reflect the running app
env_path = os.path.join(os.getcwd(), 'backend', '.env')
if os.path.exists(env_path):
    try:
        from dotenv import load_dotenv

        load_dotenv(env_path)
    except Exception:
        pass

from app.config import settings
from app.database import SessionLocal
from app.models import FreeResource, Event, Recommendation

TOKENS = [
    'simulated free',
    'simulated',
    'e2e-test',
    'fixture',
    'placeholder',
]


def _matches_text(s: str | None, tokens: List[str]) -> bool:
    if not s:
        return False
    low = s.lower()
    if low.strip() == 'desc':
        return True
    for t in tokens:
        if t in low:
            return True
    return False


def find_fake_free_resources(db):
    rows = db.query(FreeResource).all()
    matches = [r for r in rows if _matches_text(r.title, TOKENS) or _matches_text(r.description, TOKENS)]
    return matches


def find_fake_recommendations(db):
    rows = db.query(Recommendation).all()
    matches = [r for r in rows if _matches_text(r.narrative, TOKENS) or _matches_text(r.trigger_reason, TOKENS)]
    return matches


def find_fake_events(db):
    rows = db.query(Event).all()
    matches = []
    for r in rows:
        try:
            title = (r.raw_metadata or {}).get('title')
        except Exception:
            title = None
        if _matches_text(title, TOKENS):
            matches.append(r)
    return matches


def summarize_and_maybe_delete(confirm: bool = False):
    print("Connecting to app DB:", settings.DATABASE_URL)
    db = SessionLocal()
    try:
        frees = find_fake_free_resources(db)
        recs = find_fake_recommendations(db)
        evs = find_fake_events(db)

        print(f"Found free_resources matches={len(frees)} recommendations={len(recs)} events={len(evs)}")
        if frees:
            print("free_resources IDs:", [r.id for r in frees], "titles:", [r.title for r in frees])
        if recs:
            print("recommendation IDs:", [r.id for r in recs], "narratives:", [(r.id, (r.narrative or '')[:80]) for r in recs])
        if evs:
            print("event IDs:", [r.id for r in evs], "sample_titles:", [((r.raw_metadata or {}).get('title')) for r in evs])

        if not (frees or recs or evs):
            print("No clearly-fake rows found. Nothing to delete.")
            return

        if not confirm:
            print("Run with CONFIRM=1 to actually delete the above rows.")
            return

        # Delete by id lists (bulk delete)
        if frees:
            ids = [r.id for r in frees]
            db.query(FreeResource).filter(FreeResource.id.in_(ids)).delete(synchronize_session=False)
            print("Deleted free_resources:", ids)
        if recs:
            ids = [r.id for r in recs]
            db.query(Recommendation).filter(Recommendation.id.in_(ids)).delete(synchronize_session=False)
            print("Deleted recommendations:", ids)
        if evs:
            ids = [r.id for r in evs]
            db.query(Event).filter(Event.id.in_(ids)).delete(synchronize_session=False)
            print("Deleted events:", ids)

        db.commit()
        print("Deletion committed.")
    finally:
        db.close()


if __name__ == '__main__':
    confirm = os.environ.get('CONFIRM') in ('1', 'true', 'yes', 'y')
    summarize_and_maybe_delete(confirm=confirm)

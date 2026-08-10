# archived helper moved from create_e2e_rec.py
# kept for reference; not used by tests
import sys
import os

# Safety: archived helpers must not run against the live DB. Require TEST_DATABASE_URL.
TEST_DB = os.environ.get('TEST_DATABASE_URL') or os.environ.get('TARGET_DATABASE_URL')
if not TEST_DB:
    print("Refusing to run archived helper: set TEST_DATABASE_URL to a test database.")
    sys.exit(1)

sys.path.insert(0, './')
os.environ['DATABASE_URL'] = TEST_DB

from app.database import SessionLocal
from app.models import User, FreeResource, Recommendation
from datetime import datetime, timezone

with SessionLocal() as db:
    user = db.query(User).filter(User.email == 'e2e-test@example.com').first()
    if user is None:
        print('No e2e-test user found')
        raise SystemExit(1)

    resources = db.query(FreeResource).limit(3).all()
    if len(resources) < 3:
        # seed some free resources
        frs = [
            FreeResource(title='Simulated Free 1', description='desc', topic_tags=[], youtube_url='', level='beginner', category='React', sync_status='ok'),
            FreeResource(title='Simulated Free 2', description='desc', topic_tags=[], youtube_url='', level='intermediate', category='React', sync_status='ok'),
            FreeResource(title='Simulated Free 3', description='desc', topic_tags=[], youtube_url='', level='intermediate', category='React', sync_status='ok'),
        ]
        db.add_all(frs)
        db.commit()
        resources = db.query(FreeResource).limit(3).all()

    ids = [r.id for r in resources[:3]]
    now = datetime.now(timezone.utc)
    rec = Recommendation(
        user_id=user.id,
        narrative='Simulated free path for React',
        resource_ids=ids,
        match_meta=[{'dominant_pattern': 'React', 'theme': 'React'}],
        source_summary={'dominant_pattern': 'React', 'top_categories': ['React']},
        trigger_reason='simulated',
        generated_at=now,
        expires_at=now,
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)
    print('Created rec id=', rec.id, 'resource_ids=', rec.resource_ids)

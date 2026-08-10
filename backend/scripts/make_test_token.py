"""Create a test user (if missing) and print a JWT token for use in external requests.

Safety: requires `TEST_DATABASE_URL` (or `TARGET_DATABASE_URL`) env var to be set. This
ensures tokens are created only in a test DB and never in the live app DB.
"""
import sys
import os

# Require explicit test DB
TEST_DB = os.environ.get('TEST_DATABASE_URL') or os.environ.get('TARGET_DATABASE_URL')
if not TEST_DB:
    print("Refusing to run: set TEST_DATABASE_URL to a test database (will not modify live DATABASE_URL).")
    sys.exit(1)

sys.path.insert(0, './')

# Override DATABASE_URL for safety
os.environ['DATABASE_URL'] = TEST_DB

from app.database import SessionLocal
from app.models import User
from app.auth import create_access_token, hash_password
from sqlalchemy.orm import Session
import logging

logger = logging.getLogger("scripts.make_test_token")

with SessionLocal() as db:
    u = db.query(User).filter(User.email == 'e2e-test@example.com').first()
    if u is None:
        u = User(email='e2e-test@example.com', password_hash=hash_password('password'), role='user')
        db.add(u)
        db.commit()
        db.refresh(u)
    token = create_access_token(user_id=u.id, role=u.role)
    logger.info("Created test token for user id=%s", u.id)
    print(token)

import os
import sys
from time import sleep
from datetime import datetime
import uuid

# Require explicit TEST_DATABASE_URL to avoid touching the live app DB
TEST_DB = os.environ.get('TEST_DATABASE_URL') or os.environ.get('TARGET_DATABASE_URL')
if not TEST_DB:
    print("Refusing to run: set TEST_DATABASE_URL to a test database (will not modify live DATABASE_URL).")
    sys.exit(1)

# Ensure backend package importable when run from repo root and override DB
sys.path.insert(0, str('./backend'))
os.environ['DATABASE_URL'] = TEST_DB

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

EMAIL = f"trace+{uuid.uuid4().hex[:8]}@example.com"
PASSWORD = "admin123"

print("Starting trace test", EMAIL)

# Signup
r = client.post("/auth/signup", json={"email": EMAIL, "password": PASSWORD})
print("signup", r.status_code, r.json())
token = r.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

# Helper to post events and print response
def post_events(events):
    now = datetime.utcnow().isoformat()
    print(f"POST /events ts={now} events={events}")
    res = client.post("/events", json={"events": events}, headers=headers)
    try:
        data = res.json()
    except Exception:
        data = {"status_code": res.status_code, "text": res.text}
    print("RESPONSE", res.status_code, data)
    return data

# Sequence: A, wait 2s, B, wait 2s, C, wait 60s, D
courseA = {"event_type": "view", "source": "udemy", "raw_metadata": {"courseId": "A", "title": "Course A", "category": "React"}}
courseB = {"event_type": "view", "source": "udemy", "raw_metadata": {"courseId": "B", "title": "Course B", "category": "React"}}
courseC = {"event_type": "view", "source": "udemy", "raw_metadata": {"courseId": "C", "title": "Course C", "category": "React"}}
courseD = {"event_type": "view", "source": "udemy", "raw_metadata": {"courseId": "D", "title": "Course D", "category": "React"}}

post_events([courseA])
sleep(2)
post_events([courseB])
sleep(2)
post_events([courseC])
print("waiting 60s to pass cooldown")
sleep(60)
post_events([courseD])

print("Trace test complete")

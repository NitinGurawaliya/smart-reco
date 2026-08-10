import sqlite3
import os

dbs = [
    'backend_test.db',
    'backend_test_live.db',
    'backend_test_after.db',
    'backend_test_tc.db',
    'backend/chroma_db/chroma.sqlite3',
]

for db in dbs:
    path = os.path.join(os.path.dirname(__file__), '..', db) if os.path.dirname(__file__) else db
    path = os.path.normpath(path)
    # Also check absolute path fallback
    if not os.path.exists(path):
        path = db
    print('Checking', path)
    if not os.path.exists(path):
        print('  Not found')
        continue
    try:
        conn = sqlite3.connect(path)
        cur = conn.cursor()
        cur.execute("SELECT id, title FROM free_resources WHERE title LIKE '%Simulated%'")
        rows = cur.fetchall()
        if rows:
            print('  Found rows:')
            for r in rows:
                print('   ', r)
        else:
            print('  No matching rows')
    except Exception as e:
        print('  Error reading', e)
    finally:
        try:
            conn.close()
        except:
            pass

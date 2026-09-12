import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.db import connection, init_db
from app.security import hash_secret

init_db()
with connection() as db:
    db.execute("INSERT OR IGNORE INTO devices VALUES(?,?,?,?,?)", (
        "ELE-001", "Gajendra", hash_secret("demo-device-key"), 1, datetime.now(timezone.utc).isoformat()))
    db.execute("""INSERT OR IGNORE INTO geofences(id,name,kind,latitude,longitude,radius_m,active,created_at)
        VALUES(1,'Demo railway crossing','railway',12.9141,74.8560,750,1,?)""",
        (datetime.now(timezone.utc).isoformat(),))
print("Demo device ELE-001 and railway geofence are ready.")
print("Device key: demo-device-key")


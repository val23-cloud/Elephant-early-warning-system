import sqlite3
from contextlib import contextmanager
from pathlib import Path

from .config import settings


SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS devices (
    device_id TEXT PRIMARY KEY,
    elephant_name TEXT NOT NULL,
    device_key_hash TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS telemetry (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id TEXT NOT NULL REFERENCES devices(device_id),
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    battery_percent REAL NOT NULL,
    speed_kmh REAL NOT NULL DEFAULT 0,
    temperature_c REAL,
    signal_strength REAL,
    recorded_at TEXT NOT NULL,
    received_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_telemetry_device_time ON telemetry(device_id, recorded_at DESC);

CREATE TABLE IF NOT EXISTS geofences (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    kind TEXT NOT NULL,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    radius_m REAL NOT NULL,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id TEXT NOT NULL REFERENCES devices(device_id),
    alert_type TEXT NOT NULL,
    severity TEXT NOT NULL,
    message TEXT NOT NULL,
    latitude REAL,
    longitude REAL,
    created_at TEXT NOT NULL,
    acknowledged_at TEXT,
    dedupe_key TEXT
);
CREATE INDEX IF NOT EXISTS idx_alerts_created ON alerts(created_at DESC);
"""


def init_db() -> None:
    Path(settings.db_path).parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(settings.db_path) as connection:
        connection.executescript(SCHEMA)


@contextmanager
def connection():
    db = sqlite3.connect(settings.db_path)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


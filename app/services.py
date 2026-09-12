from datetime import datetime, timedelta, timezone

from .config import settings
from .db import connection
from .geofence import distance_m


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_alert(db, device_id, alert_type, severity, message, latitude, longitude, dedupe_key):
    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=15)).isoformat()
    existing = db.execute(
        "SELECT 1 FROM alerts WHERE dedupe_key=? AND created_at>=? AND acknowledged_at IS NULL",
        (dedupe_key, cutoff),
    ).fetchone()
    if existing:
        return None
    cursor = db.execute(
        """INSERT INTO alerts(device_id,alert_type,severity,message,latitude,longitude,created_at,dedupe_key)
           VALUES(?,?,?,?,?,?,?,?)""",
        (device_id, alert_type, severity, message, latitude, longitude, iso_now(), dedupe_key),
    )
    return cursor.lastrowid


def evaluate_telemetry(db, item) -> list[int]:
    alert_ids: list[int] = []
    if item.battery_percent <= settings.low_battery_percent:
        result = create_alert(db, item.device_id, "low_battery", "warning",
                              f"Battery is {item.battery_percent:.0f}%", item.latitude, item.longitude,
                              f"battery:{item.device_id}")
        if result: alert_ids.append(result)
    if item.speed_kmh >= settings.overspeed_kmh:
        result = create_alert(db, item.device_id, "abnormal_speed", "critical",
                              f"Unusual speed detected: {item.speed_kmh:.1f} km/h", item.latitude, item.longitude,
                              f"speed:{item.device_id}")
        if result: alert_ids.append(result)
    fences = db.execute("SELECT * FROM geofences WHERE active=1").fetchall()
    for fence in fences:
        distance = distance_m(item.latitude, item.longitude, fence["latitude"], fence["longitude"])
        if distance <= fence["radius_m"]:
            result = create_alert(db, item.device_id, "geofence", "critical",
                                  f"Entered {fence['kind']} zone: {fence['name']} ({distance:.0f} m from centre)",
                                  item.latitude, item.longitude, f"fence:{item.device_id}:{fence['id']}")
            if result: alert_ids.append(result)
    return alert_ids


def detect_stale_devices() -> int:
    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=settings.stale_minutes)).isoformat()
    count = 0
    with connection() as db:
        rows = db.execute("""
            SELECT d.device_id, MAX(t.recorded_at) AS last_seen
            FROM devices d LEFT JOIN telemetry t ON t.device_id=d.device_id
            WHERE d.active=1 GROUP BY d.device_id
        """).fetchall()
        for row in rows:
            if row["last_seen"] is None or row["last_seen"] < cutoff:
                result = create_alert(db, row["device_id"], "device_stale", "warning",
                                      "No recent tracker signal", None, None, f"stale:{row['device_id']}")
                count += int(result is not None)
    return count


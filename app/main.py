import csv
import io
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from .db import connection, init_db
from .models import DeviceCreate, GeofenceCreate, TelemetryIn
from .security import hash_secret, require_admin, verify_device
from .services import detect_stale_devices, evaluate_telemetry


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="Elephant Tracking System", version="1.0.0", lifespan=lifespan,
              description="Conservation tracker by Vyalery and Kavya")
static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/", response_class=HTMLResponse)
def dashboard():
    return (static_dir / "index.html").read_text(encoding="utf-8")


@app.get("/health")
def health():
    return {"status": "ok", "time": datetime.now(timezone.utc).isoformat()}


@app.post("/api/v1/devices", dependencies=[Depends(require_admin)], status_code=201)
def add_device(item: DeviceCreate):
    with connection() as db:
        try:
            db.execute("INSERT INTO devices VALUES(?,?,?,?,?)", (
                item.device_id, item.elephant_name, hash_secret(item.device_key), 1,
                datetime.now(timezone.utc).isoformat()))
        except Exception as exc:
            if "UNIQUE" in str(exc):
                raise HTTPException(409, "Device already exists") from exc
            raise
    return {"device_id": item.device_id, "elephant_name": item.elephant_name}


@app.post("/api/v1/geofences", dependencies=[Depends(require_admin)], status_code=201)
def add_geofence(item: GeofenceCreate):
    with connection() as db:
        cursor = db.execute("""INSERT INTO geofences(name,kind,latitude,longitude,radius_m,active,created_at)
            VALUES(?,?,?,?,?,1,?)""", (item.name, item.kind, item.latitude, item.longitude,
            item.radius_m, datetime.now(timezone.utc).isoformat()))
    return {"id": cursor.lastrowid, **item.model_dump()}


@app.post("/api/v1/telemetry", status_code=202)
def ingest(item: TelemetryIn, x_device_key: str = Header(...)):
    verify_device(item.device_id, x_device_key)
    now = datetime.now(timezone.utc)
    if item.recorded_at > now + timedelta(minutes=5) or item.recorded_at < now - timedelta(days=7):
        raise HTTPException(422, "recorded_at is outside the accepted time window")
    with connection() as db:
        cursor = db.execute("""INSERT INTO telemetry
            (device_id,latitude,longitude,battery_percent,speed_kmh,temperature_c,signal_strength,recorded_at,received_at)
            VALUES(?,?,?,?,?,?,?,?,?)""", (item.device_id, item.latitude, item.longitude,
            item.battery_percent, item.speed_kmh, item.temperature_c, item.signal_strength,
            item.recorded_at.isoformat(), now.isoformat()))
        alert_ids = evaluate_telemetry(db, item)
    return {"accepted": True, "telemetry_id": cursor.lastrowid, "alert_ids": alert_ids}


@app.get("/api/v1/devices/latest", dependencies=[Depends(require_admin)])
def latest_positions():
    with connection() as db:
        rows = db.execute("""
            SELECT d.device_id,d.elephant_name,t.latitude,t.longitude,t.battery_percent,t.speed_kmh,
                   t.temperature_c,t.signal_strength,t.recorded_at
            FROM devices d LEFT JOIN telemetry t ON t.id=(
                SELECT id FROM telemetry WHERE device_id=d.device_id ORDER BY recorded_at DESC LIMIT 1)
            WHERE d.active=1 ORDER BY d.elephant_name
        """).fetchall()
    return [dict(row) for row in rows]


@app.get("/api/v1/geofences", dependencies=[Depends(require_admin)])
def geofences():
    with connection() as db:
        return [dict(row) for row in db.execute("SELECT * FROM geofences WHERE active=1").fetchall()]


@app.get("/api/v1/alerts", dependencies=[Depends(require_admin)])
def alerts(unacknowledged_only: bool = False):
    sql = "SELECT * FROM alerts" + (" WHERE acknowledged_at IS NULL" if unacknowledged_only else "") + " ORDER BY created_at DESC LIMIT 200"
    with connection() as db:
        return [dict(row) for row in db.execute(sql).fetchall()]


@app.post("/api/v1/alerts/{alert_id}/acknowledge", dependencies=[Depends(require_admin)])
def acknowledge(alert_id: int):
    with connection() as db:
        cursor = db.execute("UPDATE alerts SET acknowledged_at=? WHERE id=? AND acknowledged_at IS NULL",
                            (datetime.now(timezone.utc).isoformat(), alert_id))
    if not cursor.rowcount:
        raise HTTPException(404, "Alert not found or already acknowledged")
    return {"acknowledged": True, "alert_id": alert_id}


@app.post("/api/v1/maintenance/check-stale", dependencies=[Depends(require_admin)])
def check_stale():
    return {"alerts_created": detect_stale_devices()}


@app.get("/api/v1/history/{device_id}.csv", dependencies=[Depends(require_admin)])
def export_history(device_id: str, limit: int = Query(5000, ge=1, le=50000)):
    with connection() as db:
        rows = db.execute("SELECT * FROM telemetry WHERE device_id=? ORDER BY recorded_at DESC LIMIT ?",
                          (device_id, limit)).fetchall()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["recorded_at", "latitude", "longitude", "battery_percent", "speed_kmh", "temperature_c", "signal_strength"])
    writer.writerows([[r["recorded_at"], r["latitude"], r["longitude"], r["battery_percent"],
                       r["speed_kmh"], r["temperature_c"], r["signal_strength"]] for r in rows])
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{device_id}-history.csv"'})


@app.get("/api/v1/public/summary")
def public_summary():
    with connection() as db:
        devices = db.execute("SELECT COUNT(*) FROM devices WHERE active=1").fetchone()[0]
        alerts_count = db.execute("SELECT COUNT(*) FROM alerts WHERE acknowledged_at IS NULL").fetchone()[0]
    return {"active_trackers": devices, "open_alerts": alerts_count, "precise_locations_withheld": True}

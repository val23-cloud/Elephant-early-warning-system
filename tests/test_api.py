def admin(): return {"X-Admin-Key": "test-admin"}


def test_tracking_and_geofence_alert(client):
    response = client.post("/api/v1/devices", headers=admin(), json={
        "device_id": "ELE-100", "elephant_name": "Asha", "device_key": "secret-key-100"})
    assert response.status_code == 201
    response = client.post("/api/v1/geofences", headers=admin(), json={
        "name": "Rail crossing", "kind": "railway", "latitude": 12.9, "longitude": 74.8, "radius_m": 1000})
    assert response.status_code == 201
    response = client.post("/api/v1/telemetry", headers={"X-Device-Key": "secret-key-100"}, json={
        "device_id": "ELE-100", "latitude": 12.9001, "longitude": 74.8001,
        "battery_percent": 80, "speed_kmh": 4})
    assert response.status_code == 202
    assert response.json()["alert_ids"]
    latest = client.get("/api/v1/devices/latest", headers=admin())
    assert latest.status_code == 200
    assert latest.json()[0]["elephant_name"] == "Asha"


def test_authentication(client):
    assert client.get("/api/v1/devices/latest", headers={"X-Admin-Key": "wrong"}).status_code == 401


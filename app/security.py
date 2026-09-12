import hashlib
import hmac

from fastapi import Header, HTTPException

from .config import settings
from .db import connection


def hash_secret(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def require_admin(x_admin_key: str = Header(...)) -> None:
    if not hmac.compare_digest(x_admin_key, settings.admin_key):
        raise HTTPException(status_code=401, detail="Invalid admin key")


def verify_device(device_id: str, supplied_key: str) -> None:
    with connection() as db:
        row = db.execute(
            "SELECT device_key_hash, active FROM devices WHERE device_id = ?", (device_id,)
        ).fetchone()
    if not row or not row["active"] or not hmac.compare_digest(row["device_key_hash"], hash_secret(supplied_key)):
        raise HTTPException(status_code=401, detail="Invalid or inactive device")


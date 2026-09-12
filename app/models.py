from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field, field_validator


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class DeviceCreate(BaseModel):
    device_id: str = Field(pattern=r"^[A-Za-z0-9_-]{3,40}$")
    elephant_name: str = Field(min_length=1, max_length=80)
    device_key: str = Field(min_length=8, max_length=200)


class GeofenceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    kind: Literal["railway", "village", "highway", "farm", "other"] = "other"
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    radius_m: float = Field(gt=10, le=100_000)


class TelemetryIn(BaseModel):
    device_id: str = Field(pattern=r"^[A-Za-z0-9_-]{3,40}$")
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    battery_percent: float = Field(ge=0, le=100)
    speed_kmh: float = Field(default=0, ge=0, le=100)
    temperature_c: float | None = Field(default=None, ge=-40, le=85)
    signal_strength: float | None = Field(default=None, ge=0, le=100)
    recorded_at: datetime = Field(default_factory=utc_now)

    @field_validator("recorded_at")
    @classmethod
    def timestamp_must_have_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("recorded_at must include a timezone")
        return value.astimezone(timezone.utc)


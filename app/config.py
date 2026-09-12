import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    db_path: str = os.getenv("ELEPHANT_DB_PATH", "data/elephants.db")
    admin_key: str = os.getenv("ELEPHANT_ADMIN_KEY", "change-this-admin-key")
    stale_minutes: int = int(os.getenv("ELEPHANT_STALE_MINUTES", "30"))
    low_battery_percent: float = float(os.getenv("ELEPHANT_LOW_BATTERY_PERCENT", "20"))
    overspeed_kmh: float = float(os.getenv("ELEPHANT_OVERSPEED_KMH", "25"))


settings = Settings()


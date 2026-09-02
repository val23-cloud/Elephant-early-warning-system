#!/usr/bin/env python3
"""
Forever Young Global - Elephant Early-Warning System (Concept Prototype)

Python conversion of elephant_early_warning.c.

The program consumes elephant detections from an AUTHORIZED AI/data gateway,
checks whether the reported position is near a railway, highway or farm danger
zone, records the event, and produces a near-real-time warning.

It does not log in to INSAT or any protected satellite system. A real project
requires approved data APIs, surveyed GIS coordinates, human verification,
cybersecurity review and coordination with Forest/Railway authorities.

Run:
    python3 elephant_early_warning.py --simulate
    python3 elephant_early_warning.py --input detections.csv

Authorized gateway CSV format:
    timestamp,source_id,latitude,longitude,confidence,elephant_count,frame_id
"""

from __future__ import annotations

import argparse
import csv
import math
import sys
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Iterable


EARTH_RADIUS_M = 6_371_000.0
MAX_ALERT_CACHE = 128


class ZoneType(str, Enum):
    RAILWAY = "RAILWAY"
    HIGHWAY = "HIGHWAY"
    FARM = "FARM"


class RiskLevel(str, Enum):
    NONE = "NONE"
    WATCH = "WATCH"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


@dataclass(frozen=True)
class Detection:
    timestamp: str
    source_id: str
    latitude: float
    longitude: float
    confidence: float
    elephant_count: int
    frame_id: str


@dataclass(frozen=True)
class DangerZone:
    """Circular demonstration geofence.

    Production systems should use surveyed GIS polylines or polygons.
    """

    zone_id: str
    name: str
    zone_type: ZoneType
    latitude: float
    longitude: float
    critical_radius_m: float
    warning_radius_m: float


@dataclass(frozen=True)
class Config:
    minimum_confidence: float = 0.75
    cooldown_seconds: int = 300
    event_log_path: Path = Path("elephant_events.csv")
    dry_run: bool = True


@dataclass
class AlertCacheEntry:
    sent_at: float


class AlertCache:
    """Suppresses repeated alerts for the same source, zone and risk level."""

    def __init__(self, maximum_entries: int = MAX_ALERT_CACHE) -> None:
        self.maximum_entries = maximum_entries
        self._entries: dict[str, AlertCacheEntry] = {}

    def is_suppressed(self, key: str, cooldown_seconds: int) -> bool:
        now = time.time()
        existing = self._entries.get(key)
        if existing and now - existing.sent_at < cooldown_seconds:
            return True

        if len(self._entries) >= self.maximum_entries and key not in self._entries:
            oldest_key = min(self._entries, key=lambda item: self._entries[item].sent_at)
            del self._entries[oldest_key]

        self._entries[key] = AlertCacheEntry(sent_at=now)
        return False


def distance_metres(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return great-circle distance using the Haversine formula."""

    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2.0) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2.0) ** 2
    )
    a = min(1.0, max(0.0, a))
    return EARTH_RADIUS_M * 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))


def validate_detection(detection: Detection, config: Config) -> tuple[bool, str]:
    """Validate external data before it enters the warning engine."""

    if not detection.timestamp or not detection.source_id or not detection.frame_id:
        return False, "missing timestamp, source ID or frame ID"
    if not (-90.0 <= detection.latitude <= 90.0):
        return False, "latitude outside valid range"
    if not (-180.0 <= detection.longitude <= 180.0):
        return False, "longitude outside valid range"
    if not math.isfinite(detection.latitude) or not math.isfinite(detection.longitude):
        return False, "non-finite coordinate"
    if not config.minimum_confidence <= detection.confidence <= 1.0:
        return False, "confidence below threshold or above 1.0"
    if not 1 <= detection.elephant_count <= 500:
        return False, "invalid elephant count"
    return True, "valid"


def assess_risk(detection: Detection, zone: DangerZone) -> tuple[RiskLevel, float]:
    distance = distance_metres(
        detection.latitude,
        detection.longitude,
        zone.latitude,
        zone.longitude,
    )
    if distance <= zone.critical_radius_m:
        return RiskLevel.CRITICAL, distance
    if distance <= zone.warning_radius_m:
        return RiskLevel.WARNING, distance
    if distance <= zone.warning_radius_m * 1.5:
        return RiskLevel.WATCH, distance
    return RiskLevel.NONE, distance


EVENT_LOG_HEADER = [
    "timestamp",
    "source_id",
    "frame_id",
    "latitude",
    "longitude",
    "confidence",
    "elephant_count",
    "zone_id",
    "zone_type",
    "risk",
    "distance_metres",
]


def log_event(
    config: Config,
    detection: Detection,
    zone: DangerZone,
    risk: RiskLevel,
    distance: float,
) -> None:
    """Append an auditable CSV event record, including a header when new."""

    new_file = not config.event_log_path.exists() or config.event_log_path.stat().st_size == 0
    with config.event_log_path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        if new_file:
            writer.writerow(EVENT_LOG_HEADER)
        writer.writerow(
            [
                detection.timestamp,
                detection.source_id,
                detection.frame_id,
                f"{detection.latitude:.6f}",
                f"{detection.longitude:.6f}",
                f"{detection.confidence:.3f}",
                detection.elephant_count,
                zone.zone_id,
                zone.zone_type.value,
                risk.value,
                f"{distance:.1f}",
            ]
        )


def send_alert(
    config: Config,
    cache: AlertCache,
    detection: Detection,
    zone: DangerZone,
    risk: RiskLevel,
    distance: float,
) -> None:
    """Display an alert after cooldown checks.

    Production replacement: authenticated HTTPS/CAP/SMS adapter using TLS,
    secrets management, retry queues, delivery acknowledgements and official
    recipients. Never hard-code API keys or personal phone numbers.
    """

    key = f"{detection.source_id}|{zone.zone_id}|{risk.value}"
    if cache.is_suppressed(key, config.cooldown_seconds):
        print(f"SUPPRESSED duplicate alert: {key}")
        return

    print("\n================ ELEPHANT ALERT ================")
    print(f"Severity       : {risk.value}")
    print(f"Zone           : {zone.name} ({zone.zone_type.value})")
    print(f"Distance       : {distance:.1f} metres")
    print(f"Elephants      : {detection.elephant_count}")
    print(f"AI confidence  : {detection.confidence * 100.0:.1f}%")
    print(f"Location       : {detection.latitude:.6f}, {detection.longitude:.6f}")
    print(f"Source / frame : {detection.source_id} / {detection.frame_id}")
    print("Recommended    : Verify with operator; slow/stop traffic if confirmed;")
    print("                 notify forest response team; never approach the herd.")
    print(f"Mode           : {'DRY RUN - no external message' if config.dry_run else 'LIVE ADAPTER'}")
    print("================================================\n")


def process_detection(
    config: Config,
    cache: AlertCache,
    detection: Detection,
    zones: Iterable[DangerZone],
) -> None:
    valid, reason = validate_detection(detection, config)
    if not valid:
        print(
            f"REJECTED detection from {detection.source_id!r}: {reason}",
            file=sys.stderr,
        )
        return

    for zone in zones:
        risk, distance = assess_risk(detection, zone)
        if risk is RiskLevel.NONE:
            continue

        log_event(config, detection, zone, risk, distance)
        if risk in (RiskLevel.WARNING, RiskLevel.CRITICAL):
            send_alert(config, cache, detection, zone, risk, distance)
        else:
            print(f"WATCH: {detection.source_id} is {distance:.1f}m from {zone.name}")


def parse_detection_row(row: dict[str, str], line_number: int) -> Detection:
    required = {
        "timestamp",
        "source_id",
        "latitude",
        "longitude",
        "confidence",
        "elephant_count",
        "frame_id",
    }
    missing = required.difference(row)
    if missing:
        raise ValueError(f"line {line_number}: missing columns {sorted(missing)}")
    try:
        return Detection(
            timestamp=row["timestamp"].strip(),
            source_id=row["source_id"].strip(),
            latitude=float(row["latitude"]),
            longitude=float(row["longitude"]),
            confidence=float(row["confidence"]),
            elephant_count=int(row["elephant_count"]),
            frame_id=row["frame_id"].strip(),
        )
    except (TypeError, ValueError) as error:
        raise ValueError(f"line {line_number}: invalid field value: {error}") from error


def run_csv_file(
    path: Path,
    config: Config,
    zones: Iterable[DangerZone],
    cache: AlertCache,
) -> int:
    try:
        with path.open("r", newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames is None:
                raise ValueError("input contains no CSV header")
            for line_number, row in enumerate(reader, start=2):
                try:
                    detection = parse_detection_row(row, line_number)
                except ValueError as error:
                    print(f"REJECTED malformed CSV: {error}", file=sys.stderr)
                    continue
                process_detection(config, cache, detection, zones)
    except (OSError, ValueError) as error:
        print(f"ERROR: cannot process {path}: {error}", file=sys.stderr)
        return 1
    return 0


def run_simulation(
    config: Config,
    zones: Iterable[DangerZone],
    cache: AlertCache,
) -> None:
    demo_detections = [
        Detection("2026-09-02T12:30:00Z", "CAM-KA-017", 12.97170, 77.59470, 0.94, 3, "frame-00042"),
        Detection("2026-09-02T12:30:05Z", "CAM-KA-017", 12.97171, 77.59471, 0.96, 3, "frame-00043"),
        Detection("2026-09-02T12:32:00Z", "DRONE-AUTH-02", 12.98000, 77.61000, 0.88, 1, "frame-00810"),
        Detection("2026-09-02T12:33:00Z", "CAM-KA-021", 12.96560, 77.60010, 0.42, 2, "frame-00113"),
    ]
    print("Running safe built-in simulation...\n")
    for detection in demo_detections:
        process_detection(config, cache, detection, zones)


def demonstration_zones() -> list[DangerZone]:
    """Return placeholder zones; never deploy these as real coordinates."""

    return [
        DangerZone(
            "RAIL-DEMO-01",
            "Demo Railway Crossing",
            ZoneType.RAILWAY,
            12.97160,
            77.59460,
            150.0,
            500.0,
        ),
        DangerZone(
            "ROAD-DEMO-01",
            "Demo Forest Highway",
            ZoneType.HIGHWAY,
            12.98020,
            77.61020,
            100.0,
            400.0,
        ),
        DangerZone(
            "FARM-DEMO-01",
            "Demo Community Farm",
            ZoneType.FARM,
            12.96550,
            77.60000,
            75.0,
            300.0,
        ),
    ]


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Forever Young Global elephant early-warning concept prototype"
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--simulate", action="store_true", help="run safe built-in detections")
    mode.add_argument("--input", type=Path, help="authorized gateway detection CSV")
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.75,
        help="minimum accepted AI confidence from 0 to 1 (default: 0.75)",
    )
    parser.add_argument(
        "--cooldown",
        type=int,
        default=300,
        help="duplicate-alert cooldown in seconds (default: 300)",
    )
    parser.add_argument(
        "--log",
        type=Path,
        default=Path("elephant_events.csv"),
        help="event log CSV path",
    )
    return parser


def main() -> int:
    args = build_argument_parser().parse_args()
    if not 0.0 <= args.threshold <= 1.0:
        print("ERROR: --threshold must be between 0 and 1", file=sys.stderr)
        return 2
    if args.cooldown < 0:
        print("ERROR: --cooldown cannot be negative", file=sys.stderr)
        return 2

    config = Config(
        minimum_confidence=args.threshold,
        cooldown_seconds=args.cooldown,
        event_log_path=args.log,
        dry_run=True,
    )
    zones = demonstration_zones()
    cache = AlertCache()

    print("Forever Young Global - Elephant Early-Warning Concept Prototype")
    print("AUTHORIZED DATA ONLY | HUMAN VERIFICATION REQUIRED\n")

    if args.simulate:
        run_simulation(config, zones, cache)
        return 0
    return run_csv_file(args.input, config, zones, cache)


if __name__ == "__main__":
    raise SystemExit(main())

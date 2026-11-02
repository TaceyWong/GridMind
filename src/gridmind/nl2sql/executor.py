from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from gridmind.agents.iot_tools import ALARMS, DEVICES
from gridmind.core.config import settings


STATIONS = [
    ("ST-E", "华东变电站", "华东"),
    ("ST-N", "华北变电站", "华北"),
    ("ST-S", "华南变电站", "华南"),
    ("ST-W", "西南变电站", "西南"),
]


def _connect(db_path: Path | None = None) -> sqlite3.Connection:
    path = db_path or settings.sqlite_path
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def init_demo_db(db_path: Path | None = None) -> Path:
    path = db_path or settings.sqlite_path
    conn = _connect(path)
    cur = conn.cursor()
    cur.executescript(
        """
        DROP TABLE IF EXISTS telemetry_daily;
        DROP TABLE IF EXISTS alarms;
        DROP TABLE IF EXISTS devices;
        DROP TABLE IF EXISTS stations;

        CREATE TABLE stations (
            station_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            region TEXT NOT NULL
        );
        CREATE TABLE devices (
            device_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            station_id TEXT NOT NULL,
            region TEXT NOT NULL,
            device_type TEXT NOT NULL,
            status TEXT NOT NULL
        );
        CREATE TABLE alarms (
            alarm_id TEXT PRIMARY KEY,
            device_id TEXT NOT NULL,
            level TEXT NOT NULL,
            message TEXT NOT NULL,
            status TEXT NOT NULL,
            occurred_at TEXT NOT NULL
        );
        CREATE TABLE telemetry_daily (
            device_id TEXT NOT NULL,
            station_id TEXT NOT NULL,
            day TEXT NOT NULL,
            max_temp_c REAL NOT NULL,
            avg_temp_c REAL NOT NULL
        );
        """
    )
    cur.executemany("INSERT INTO stations VALUES (?, ?, ?)", STATIONS)
    station_by_region = {r: sid for sid, _, r in STATIONS}
    for device in DEVICES.values():
        cur.execute(
            "INSERT INTO devices VALUES (?, ?, ?, ?, ?, ?)",
            (
                device["device_id"],
                device["name"],
                station_by_region[device["region"]],
                device["region"],
                device["type"],
                device["status"],
            ),
        )
    for alarm in ALARMS:
        cur.execute(
            "INSERT INTO alarms VALUES (?, ?, ?, ?, ?, ?)",
            (
                alarm["alarm_id"],
                alarm["device_id"],
                alarm["level"],
                alarm["message"],
                alarm["status"],
                alarm["ts"],
            ),
        )

    today = datetime.now().date()
    rows = []
    for device in DEVICES.values():
        for offset in range(0, 10):
            day = today - timedelta(days=offset)
            base = 70.0 if device["device_id"] == "DEV-001" else 55.0
            rows.append(
                (
                    device["device_id"],
                    station_by_region[device["region"]],
                    day.isoformat(),
                    base + offset,
                    base + offset - 2,
                )
            )
    cur.executemany(
        "INSERT INTO telemetry_daily VALUES (?, ?, ?, ?, ?)",
        rows,
    )
    conn.commit()
    conn.close()
    return path


def execute_sql(sql: str, db_path: Path | None = None) -> list[dict[str, Any]]:
    path = db_path or settings.sqlite_path
    if not path.exists():
        init_demo_db(path)
    conn = _connect(path)
    try:
        cur = conn.execute(sql)
        rows = cur.fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def memory_timeseries_join(device_ids: list[str], hours: int = 24) -> list[dict[str, Any]]:
    """Simulate cross-store join: SQLite device ids + in-memory TDengine-like telemetry."""
    from gridmind.agents.iot_tools import get_device_telemetry

    out: list[dict[str, Any]] = []
    for device_id in device_ids:
        points = get_device_telemetry(device_id, hours=hours)
        if not points:
            continue
        values = [p["value"] for p in points]
        out.append(
            {
                "device_id": device_id,
                "points": len(points),
                "max_temp_c": max(values),
                "min_temp_c": min(values),
                "latest_temp_c": values[-1],
            }
        )
    return out

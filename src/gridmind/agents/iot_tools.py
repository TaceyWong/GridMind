"""Sample IoT tools for GridMind learning demos."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

DEVICES: dict[str, dict[str, Any]] = {
    "DEV-001": {
        "device_id": "DEV-001",
        "name": "主变 A 相温度传感器",
        "station": "华东变电站",
        "region": "华东",
        "type": "temperature",
        "status": "online",
        "sample_interval_min": 5,
    },
    "DEV-002": {
        "device_id": "DEV-002",
        "name": "线路 B 电流互感器",
        "station": "华北变电站",
        "region": "华北",
        "type": "current",
        "status": "online",
        "sample_interval_min": 5,
    },
    "DEV-003": {
        "device_id": "DEV-003",
        "name": "开关柜环境监测",
        "station": "华南变电站",
        "region": "华南",
        "type": "environment",
        "status": "offline",
        "sample_interval_min": 10,
    },
    "DEV-004": {
        "device_id": "DEV-004",
        "name": "主变 B 相温度传感器",
        "station": "华东变电站",
        "region": "华东",
        "type": "temperature",
        "status": "online",
        "sample_interval_min": 5,
    },
    "DEV-005": {
        "device_id": "DEV-005",
        "name": "配电房温湿度",
        "station": "西南变电站",
        "region": "西南",
        "type": "environment",
        "status": "online",
        "sample_interval_min": 5,
    },
}

ALARMS: list[dict[str, Any]] = [
    {
        "alarm_id": "ALM-1001",
        "device_id": "DEV-001",
        "level": "critical",
        "message": "绕组温度过高",
        "status": "open",
        "ts": (datetime.now() - timedelta(hours=2)).isoformat(timespec="seconds"),
    },
    {
        "alarm_id": "ALM-1002",
        "device_id": "DEV-001",
        "level": "warning",
        "message": "温度上升过快",
        "status": "open",
        "ts": (datetime.now() - timedelta(days=1)).isoformat(timespec="seconds"),
    },
    {
        "alarm_id": "ALM-1003",
        "device_id": "DEV-004",
        "level": "critical",
        "message": "油温异常",
        "status": "acked",
        "ts": (datetime.now() - timedelta(days=2)).isoformat(timespec="seconds"),
    },
    {
        "alarm_id": "ALM-1004",
        "device_id": "DEV-002",
        "level": "info",
        "message": "采样抖动",
        "status": "closed",
        "ts": (datetime.now() - timedelta(days=3)).isoformat(timespec="seconds"),
    },
    {
        "alarm_id": "ALM-1005",
        "device_id": "DEV-005",
        "level": "warning",
        "message": "湿度偏高",
        "status": "open",
        "ts": (datetime.now() - timedelta(hours=8)).isoformat(timespec="seconds"),
    },
]


def get_device_info(device_id: str) -> dict[str, Any]:
    """查询设备基本信息。"""
    device = DEVICES.get(device_id)
    if not device:
        return {"error": f"device {device_id} not found"}
    return dict(device)


def get_device_alarms(device_id: str) -> list[dict[str, Any]]:
    """查询设备告警。"""
    return [a for a in ALARMS if a["device_id"] == device_id]


def get_device_telemetry(device_id: str, hours: int = 24) -> list[dict[str, Any]]:
    """查询设备历史遥测（温度样例）。"""
    if device_id not in DEVICES:
        return []
    now = datetime.now()
    points: list[dict[str, Any]] = []
    base = 55.0 if device_id in {"DEV-001", "DEV-004"} else 30.0
    for i in range(max(hours, 1)):
        ts = now - timedelta(hours=hours - i)
        value = base + (i % 7) * 0.8 + (3 if device_id == "DEV-001" and i > hours - 4 else 0)
        points.append(
            {
                "device_id": device_id,
                "metric": "temperature_c",
                "ts": ts.isoformat(timespec="seconds"),
                "value": round(value, 2),
            }
        )
    return points


def list_online_devices() -> list[dict[str, Any]]:
    return [d for d in DEVICES.values() if d["status"] == "online"]


def top_alarm_devices(limit: int = 5) -> list[dict[str, Any]]:
    counts: dict[str, int] = {}
    for alarm in ALARMS:
        counts[alarm["device_id"]] = counts.get(alarm["device_id"], 0) + 1
    ranked = sorted(counts.items(), key=lambda x: x[1], reverse=True)[:limit]
    return [
        {"device_id": device_id, "alarm_count": count, **DEVICES[device_id]}
        for device_id, count in ranked
        if device_id in DEVICES
    ]

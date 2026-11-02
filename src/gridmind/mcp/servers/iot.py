from __future__ import annotations

from gridmind.agents import iot_tools
from gridmind.mcp.registry import registry


def register_iot_tools() -> None:
    registry.register(
        "iot",
        "get_device_info",
        "查询设备基本信息",
        iot_tools.get_device_info,
    )
    registry.register(
        "iot",
        "get_device_alarms",
        "查询设备告警",
        iot_tools.get_device_alarms,
    )
    registry.register(
        "iot",
        "get_device_telemetry",
        "查询设备历史遥测",
        iot_tools.get_device_telemetry,
    )
    registry.register(
        "iot",
        "list_online_devices",
        "列出在线设备",
        iot_tools.list_online_devices,
    )
    registry.register(
        "iot",
        "top_alarm_devices",
        "告警最多的设备",
        iot_tools.top_alarm_devices,
    )

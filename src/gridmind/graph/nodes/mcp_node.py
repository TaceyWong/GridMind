from __future__ import annotations

import re
from typing import Any

from gridmind.core.security import UserContext
from gridmind.graph.state import ChatState
from gridmind.mcp.client import McpClient
from gridmind.nl2sql.gpt_vis import rows_to_gpt_vis


def _extract_device_id(question: str) -> str | None:
    match = re.search(r"DEV-\d+", question.upper())
    if match:
        return match.group(0)
    match = re.search(r"设备\s*(\d+)", question)
    if match:
        return f"DEV-{int(match.group(1)):03d}"
    return None


async def execute_mcp(state: ChatState) -> ChatState:
    client = McpClient()
    user = UserContext(
        user_id=state.get("user_id", "demo-user"),
        tenant_id=state.get("tenant_id", "demo-tenant"),
    )
    question = state["question"]
    device_id = _extract_device_id(question)

    tool_name = "list_online_devices"
    args: dict[str, Any] = {}
    server = "iot"

    if device_id and any(k in question for k in ("告警",)):
        tool_name, args = "get_device_alarms", {"device_id": device_id}
    elif device_id and any(k in question for k in ("温度", "遥测", "历史")):
        tool_name, args = "get_device_telemetry", {"device_id": device_id, "hours": 24}
    elif device_id:
        tool_name, args = "get_device_info", {"device_id": device_id}
    elif any(k in question for k in ("告警最多", "排名")):
        server, tool_name, args = "iot", "top_alarm_devices", {"limit": 5}

    result = await client.call_tool(tool_name, args, server=server, user=user)
    events = list(state.get("events", []))
    events.append({"type": "mcp", "server": server, "tool": tool_name})
    intermediate = list(state.get("intermediate", []))
    intermediate.append(str(result["result"]))
    return {
        "tool_name": f"{server}.{tool_name}",
        "tool_args": args,
        "tool_result": result["result"],
        "answer": f"工具 {server}.{tool_name} 结果：{result['result']}",
        "events": events,
        "intermediate": intermediate,
    }  # type: ignore[return-value]


async def execute_hybrid(state: ChatState) -> ChatState:
    """Composite path: BI alarm ranking -> IoT temperature -> summary."""
    client = McpClient()
    user = UserContext(
        user_id=state.get("user_id", "demo-user"),
        tenant_id=state.get("tenant_id", "demo-tenant"),
    )
    top = await client.call_tool("alarm_top", {"limit": 5}, server="bi", user=user)
    rows = top["result"] or []
    device_ids = [r.get("device_id") for r in rows if r.get("device_id")]
    if not device_ids:
        iot_top = await client.call_tool("top_alarm_devices", {"limit": 5}, server="iot", user=user)
        rows = iot_top["result"] or []
        device_ids = [r.get("device_id") for r in rows if r.get("device_id")]

    temp = await client.call_tool(
        "temperature_for_devices",
        {"device_ids": device_ids[:5]},
        server="bi",
        user=user,
    )
    chart_rows = [r for r in rows if isinstance(r, dict)]
    vis = rows_to_gpt_vis(chart_rows, intent="rank", metric="alarm_count")
    answer_parts = [
        "综合分析结果：",
        f"1) 告警较多设备：{rows}",
        f"2) 近一周温度汇总：{temp['result']}",
    ]
    if vis:
        answer_parts.extend(["", "告警分布：", vis])
    answer_parts.append("结论：请重点关注温度偏高且告警密集的设备。")
    answer = "\n".join(answer_parts)
    events = list(state.get("events", []))
    events.append({"type": "hybrid", "devices": device_ids[:5]})
    return {
        "tool_result": {"alarms": rows, "temperature": temp["result"]},
        "answer": answer,
        "events": events,
        "intermediate": [str(rows), str(temp["result"])],
    }  # type: ignore[return-value]

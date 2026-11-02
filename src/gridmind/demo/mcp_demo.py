"""学习示例：官方 MCP Python SDK（内存 Server + Client）

覆盖：
- MCPServer：Tool / Resource / Prompt
- Client(server) 同进程内存连接（真协议，无端口）
- list_tools / call_tool
- list_resource_templates / read_resource
- list_prompts / get_prompt
- 与 stdio / HTTP transport、以及 GridMind 自写 mcp 层的对比说明

运行::

    uv run python -m gridmind.demo mcp
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from mcp import Client
from mcp.server import MCPServer

from gridmind.demo._common import banner


def build_server() -> MCPServer:
    """构建一个电网场景的演示 MCP Server。"""
    server = MCPServer(
        "GridMindDemo",
        instructions="电网 IoT / ChatBI 演示 MCP：提供设备查询工具、变电站资源与分析提示词。",
    )

    @server.tool()
    def get_device_info(device_id: str) -> dict[str, Any]:
        """查询设备基本信息。"""
        catalog = {
            "DEV-001": {"name": "主变 A 相温度传感器", "region": "华东", "status": "online"},
            "DEV-002": {"name": "线路 B 电流互感器", "region": "华北", "status": "online"},
        }
        info = catalog.get(device_id)
        if not info:
            return {"error": f"unknown device: {device_id}"}
        return {"device_id": device_id, **info}

    @server.tool()
    def get_device_alarms(device_id: str, limit: int = 5) -> list[dict[str, Any]]:
        """查询设备告警列表。"""
        return [
            {
                "alarm_id": f"ALM-{device_id[-3:]}-{i}",
                "device_id": device_id,
                "level": "warning" if i % 2 else "critical",
                "message": "温度异常" if i % 2 == 0 else "采样抖动",
            }
            for i in range(1, max(limit, 1) + 1)
        ][:limit]

    @server.resource("grid://stations/{station_id}")
    def station_profile(station_id: str) -> str:
        """变电站档案（Resource Template）。"""
        return f"station_id={station_id}; name=演示变电站; region=华东"

    @server.prompt()
    def analyze_alarm(device_id: str) -> str:
        """生成告警分析提示词。"""
        return f"请结合设备 {device_id} 的告警与温度趋势，判断是否异常并给出处置建议。"

    return server


def _content_text(result: Any) -> str:
    """从 CallToolResult / ReadResourceResult 里抽出可读文本。"""
    if getattr(result, "structured_content", None):
        return json.dumps(result.structured_content, ensure_ascii=False)
    contents = getattr(result, "content", None) or getattr(result, "contents", None) or []
    parts: list[str] = []
    for item in contents:
        text = getattr(item, "text", None)
        if text is not None:
            parts.append(text)
    return "\n".join(parts) if parts else str(result)


async def run_demo() -> None:
    banner("官方 MCP SDK：内存 Server + Client")
    server = build_server()

    print("Transport: Client(server) → 同进程内存连接")
    print("（仍走 MCP 协议：发现、参数校验、调用；无子进程/端口）\n")

    async with Client(server) as client:
        # 1) 会话元信息
        print("--- 1) 握手 / 能力 ---")
        print("server_info =", client.server_info)
        print("capabilities.tools =", client.server_capabilities.tools)
        print("capabilities.resources =", client.server_capabilities.resources)
        print("capabilities.prompts =", client.server_capabilities.prompts)
        print("instructions =", client.instructions)

        # 2) Tools
        print("\n--- 2) Tools：list + call ---")
        tools = await client.list_tools()
        for tool in tools.tools:
            print(f"  - {tool.name}: {tool.description}")
            print(f"    schema = {tool.input_schema}")

        info = await client.call_tool("get_device_info", {"device_id": "DEV-001"})
        print("call get_device_info =>", _content_text(info))

        alarms = await client.call_tool(
            "get_device_alarms",
            {"device_id": "DEV-001", "limit": 2},
        )
        print("call get_device_alarms =>", _content_text(alarms))

        # 3) Resources
        print("\n--- 3) Resources：templates + read ---")
        listed = await client.list_resources()
        print("static resources =", listed.resources)
        templates = await client.list_resource_templates()
        for tpl in templates.resource_templates:
            print(f"  - {tpl.name}: {tpl.uri_template}")

        profile = await client.read_resource("grid://stations/ST-E")
        print("read grid://stations/ST-E =>", _content_text(profile))

        # 4) Prompts
        print("\n--- 4) Prompts：list + get ---")
        prompts = await client.list_prompts()
        for p in prompts.prompts:
            print(f"  - {p.name}: {p.description}")
        prompt = await client.get_prompt("analyze_alarm", {"device_id": "DEV-001"})
        for msg in prompt.messages:
            print(f"  [{msg.role}] {getattr(msg.content, 'text', msg.content)}")

    print("\n--- 5) 其它 Transport（本 demo 未启动，仅说明） ---")
    print("  - Client(StdioServerParameters(...))  → 子进程 stdin/stdout")
    print("  - Client('http://host/mcp')           → Streamable HTTP（生产常见）")
    print("  - server.run_stdio_async() / streamable_http_app() → 对外暴露")

    print("\n--- 6) 和 GridMind 现有 mcp 包的区别 ---")
    print("  gridmind.mcp.*  = 自写 registry 直调函数（学习用仿 MCP）")
    print("  官方 mcp 库     = 标准协议 + Tool/Resource/Prompt + 可换 transport")
    print("  下一步可将 IoT/BI 工具迁到 MCPServer，LangGraph 节点用 Client 调用。")


def main() -> None:
    asyncio.run(run_demo())


if __name__ == "__main__":
    main()

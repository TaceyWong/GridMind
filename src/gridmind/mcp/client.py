from __future__ import annotations

from typing import Any

from gridmind.core.security import UserContext
from gridmind.mcp.registry import registry
from gridmind.mcp.servers import register_all_servers


class McpClient:
    """In-process MCP-style client with service identity + trusted user context."""

    def __init__(self) -> None:
        register_all_servers()

    async def list_tools(self, server: str | None = None) -> list[dict[str, str]]:
        return registry.list_tools(server)

    async def call_tool(
        self,
        name: str,
        arguments: dict[str, Any] | None = None,
        *,
        server: str | None = None,
        user: UserContext | None = None,
    ) -> dict[str, Any]:
        # Authentication is service-side; user context is trusted only from backend injection.
        _ = user
        if server is None:
            if "." in name:
                server, name = name.split(".", 1)
            else:
                server = "iot"
        result = await registry.call(server, name, arguments or {})
        return {
            "server": server,
            "tool": name,
            "arguments": arguments or {},
            "result": result,
        }

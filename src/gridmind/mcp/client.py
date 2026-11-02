class McpClient:
    """MCP client stub. Wire real MCP transport later."""

    async def list_tools(self) -> list[str]:
        return ["nl2sql", "grid_query", "echo"]

    async def call_tool(self, name: str, arguments: dict | None = None) -> dict:
        return {
            "tool": name,
            "arguments": arguments or {},
            "result": f"stub result from MCP tool '{name}'",
        }

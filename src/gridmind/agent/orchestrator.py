from gridmind.mcp.client import McpClient
from gridmind.nl2sql.converter import Nl2SqlConverter


class AgentOrchestrator:
    """Agent orchestration stub. Coordinates MCP and NL2SQL placeholders."""

    def __init__(
        self,
        mcp_client: McpClient | None = None,
        nl2sql: Nl2SqlConverter | None = None,
    ) -> None:
        self._mcp = mcp_client or McpClient()
        self._nl2sql = nl2sql or Nl2SqlConverter()

    async def run(self, message: str) -> str:
        sql = await self._nl2sql.convert(message)
        tool_result = await self._mcp.call_tool(
            "nl2sql",
            {"sql": sql, "question": message},
        )
        return (
            f"GridMind stub reply for: {message}\n"
            f"SQL: {sql}\n"
            f"MCP: {tool_result['result']}"
        )

    async def list_tools(self) -> list[str]:
        return await self._mcp.list_tools()

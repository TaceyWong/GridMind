"""Legacy orchestrator kept for compatibility; prefer graph.workflow.run_chat."""

from gridmind.graph.workflow import run_chat


class AgentOrchestrator:
    async def run(self, message: str) -> str:
        result = await run_chat(message)
        return result.get("answer") or ""

    async def list_tools(self) -> list[str]:
        from gridmind.mcp.client import McpClient

        tools = await McpClient().list_tools()
        return [t["key"] for t in tools]

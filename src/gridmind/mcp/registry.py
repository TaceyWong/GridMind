from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any


ToolHandler = Callable[..., Awaitable[Any] | Any]


@dataclass
class ToolSpec:
    name: str
    description: str
    handler: ToolHandler
    server: str


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}

    def register(self, server: str, name: str, description: str, handler: ToolHandler) -> None:
        key = f"{server}.{name}"
        self._tools[key] = ToolSpec(name=name, description=description, handler=handler, server=server)

    def list_tools(self, server: str | None = None) -> list[dict[str, str]]:
        items = self._tools.values()
        if server:
            items = [t for t in items if t.server == server]
        return [
            {"server": t.server, "name": t.name, "description": t.description, "key": f"{t.server}.{t.name}"}
            for t in items
        ]

    async def call(self, server: str, name: str, arguments: dict[str, Any] | None = None) -> Any:
        key = f"{server}.{name}"
        if key not in self._tools:
            raise KeyError(f"Unknown tool: {key}")
        handler = self._tools[key].handler
        result = handler(**(arguments or {}))
        if hasattr(result, "__await__"):
            return await result
        return result


registry = ToolRegistry()

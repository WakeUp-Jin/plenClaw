from __future__ import annotations

import json
from typing import Any, Callable, Awaitable

from core.tool.types import InternalTool
from utils import logger


class ToolManager:
    def __init__(self) -> None:
        self._tools: dict[str, InternalTool] = {}

    def register(
        self,
        name: str,
        definition: dict[str, Any],
        handler: Callable[[dict[str, Any]], Awaitable[str]],
        category: str = "general",
        is_read_only: bool = False,
        should_confirm: bool | None = None,
    ) -> None:
        self._tools[name] = InternalTool(
            name=name,
            definition=definition,
            handler=handler,
            category=category,
            is_read_only=is_read_only,
            should_confirm=should_confirm,
        )
        logger.debug("Registered tool: %s [%s]", name, category)

    def get_tool(self, name: str) -> InternalTool | None:
        return self._tools.get(name)

    async def execute(self, name: str, arguments: str | dict) -> str:
        tool = self._tools.get(name)
        if tool is None:
            return json.dumps({"error": f"Unknown tool: {name}"})

        if isinstance(arguments, str):
            try:
                args = json.loads(arguments)
            except json.JSONDecodeError as e:
                return json.dumps({"error": f"Invalid JSON arguments: {e}"})
        else:
            args = arguments

        return await tool.handler(args)

    def get_formatted_tools(self) -> list[dict[str, Any]]:
        """Return tools in OpenAI function calling format."""
        return [
            {
                "type": "function",
                "function": tool.definition,
            }
            for tool in self._tools.values()
        ]

    def list_tools(self) -> list[str]:
        return list(self._tools.keys())

from __future__ import annotations

from typing import Any

from core.context.base import BaseContext


class ToolSequenceContext(BaseContext):
    """Manages tool_call + tool_result message pairs during a single agent run."""

    def __init__(self) -> None:
        self._messages: list[dict[str, Any]] = []

    def add_tool_call(self, assistant_message: dict[str, Any]) -> None:
        self._messages.append(assistant_message)

    def add_tool_result(self, tool_call_id: str, content: str) -> None:
        self._messages.append(
            {
                "role": "tool",
                "tool_call_id": tool_call_id,
                "content": content,
            }
        )

    def get_messages(self) -> list[dict[str, Any]]:
        return list(self._messages)

    def clear(self) -> None:
        self._messages.clear()

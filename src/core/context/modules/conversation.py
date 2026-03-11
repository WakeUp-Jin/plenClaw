from __future__ import annotations

from typing import Any

from core.context.base import BaseContext

DEFAULT_MAX_TURNS = 20


class ConversationContext(BaseContext):
    def __init__(self, max_turns: int = DEFAULT_MAX_TURNS):
        self._messages: list[dict[str, Any]] = []
        self._max_turns = max_turns

    def add_user_message(self, content: str) -> None:
        self._messages.append({"role": "user", "content": content})
        self._trim()

    def add_assistant_message(self, content: str) -> None:
        self._messages.append({"role": "assistant", "content": content})
        self._trim()

    def get_messages(self) -> list[dict[str, Any]]:
        return list(self._messages)

    def clear(self) -> None:
        self._messages.clear()

    def _trim(self) -> None:
        max_messages = self._max_turns * 2
        if len(self._messages) > max_messages:
            self._messages = self._messages[-max_messages:]

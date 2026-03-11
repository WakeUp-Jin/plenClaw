from __future__ import annotations

from typing import Any

from core.context.base import BaseContext
from memory.memory_store import MemoryStore


class MemoryContext(BaseContext):
    """Injects long-term memory from MemoryStore into LLM context."""

    def __init__(self, memory_store: MemoryStore):
        self._store = memory_store

    def get_messages(self) -> list[dict[str, Any]]:
        text = self._store.get_memory_text()
        if not text.strip():
            return []

        return [
            {
                "role": "system",
                "content": (
                    "以下是你对用户的长期记忆，请基于这些信息个性化回复：\n\n"
                    f"{text}"
                ),
            }
        ]

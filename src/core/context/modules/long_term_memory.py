"""Long-term memory context module.

Bridges the ``LocalMemoryStore`` (local file-based persistent storage) into
the context pipeline.  This module is read-only at the context level --
writes go through the ``LocalMemoryStore`` / memory tools directly.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from core.context.base import BaseContext
from core.context.types import ContextParts, SystemPart

if TYPE_CHECKING:
    from storage.memory_store import LocalMemoryStore


class LongTermMemoryContext(BaseContext[str]):
    """Injects long-term memory text into the LLM context."""

    def __init__(self, memory_store: LocalMemoryStore) -> None:
        super().__init__()
        self._store = memory_store

    def refresh(self) -> None:
        """Reload memory text from the backing store into the item list."""
        self.clear()
        text = self._store.get_memory_text()
        if text and text.strip():
            self.add(text)

    def format(self) -> ContextParts:
        all_text = self.get_all()
        if not all_text:
            text = self._store.get_memory_text()
            if not text or not text.strip():
                return ContextParts()
        else:
            text = "\n".join(all_text)

        return ContextParts(system_parts=[
            SystemPart(
                tag="long_term_memory",
                description="以下是你对用户的长期记忆，请基于这些信息个性化回复",
                content=text,
            ),
        ])

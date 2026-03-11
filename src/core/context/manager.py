from __future__ import annotations

from typing import Any, TYPE_CHECKING

from core.context.modules.system_prompt import SystemPromptContext
from core.context.modules.conversation import ConversationContext
from core.context.modules.tool_sequence import ToolSequenceContext

if TYPE_CHECKING:
    from core.context.modules.memory import MemoryContext


class ContextManager:
    def __init__(
        self,
        system_prompt: SystemPromptContext | None = None,
        memory: MemoryContext | None = None,
    ):
        self.system_prompt = system_prompt or SystemPromptContext()
        self.memory = memory
        self.conversation = ConversationContext()
        self.tool_sequence = ToolSequenceContext()

    def get_context(self) -> list[dict[str, Any]]:
        """Assemble all contexts: system_prompt -> memory -> conversation -> tool_sequence."""
        messages: list[dict[str, Any]] = []

        messages.extend(self.system_prompt.get_messages())

        if self.memory is not None:
            messages.extend(self.memory.get_messages())

        messages.extend(self.conversation.get_messages())
        messages.extend(self.tool_sequence.get_messages())

        return messages

    def clear_tool_sequence(self) -> None:
        self.tool_sequence.clear()

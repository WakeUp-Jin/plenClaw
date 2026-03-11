from __future__ import annotations

from typing import TYPE_CHECKING

from core.llm.utils.tool_loop import execute_tool_loop
from utils import logger
from utils.token_counter import TokenCounter

if TYPE_CHECKING:
    from core.llm.services.base import BaseLLMService
    from core.context.manager import ContextManager
    from core.tool.manager import ToolManager


class SimpleAgent:
    def __init__(
        self,
        llm: BaseLLMService,
        context_manager: ContextManager,
        tool_manager: ToolManager,
        token_counter: TokenCounter | None = None,
    ):
        self._llm = llm
        self._ctx = context_manager
        self._tools = tool_manager
        self._token_counter = token_counter or TokenCounter()

    @property
    def token_counter(self) -> TokenCounter:
        return self._token_counter

    async def run(self, user_text: str, chat_id: str = "", open_id: str = "") -> str:
        logger.info("Agent run: user=%s, chat=%s, text=%s", open_id, chat_id, user_text[:80])

        self._ctx.conversation.add_user_message(user_text)

        messages = self._ctx.get_context()
        tools = self._tools.get_formatted_tools()

        response_text, usage = await execute_tool_loop(
            self._llm, messages, tools, self._tools
        )

        self._token_counter.add(usage.prompt_tokens, usage.completion_tokens)

        self._ctx.conversation.add_assistant_message(response_text)
        self._ctx.clear_tool_sequence()

        logger.info(
            "Agent done: tokens=%d (p=%d, c=%d)",
            usage.total_tokens, usage.prompt_tokens, usage.completion_tokens,
        )
        return response_text

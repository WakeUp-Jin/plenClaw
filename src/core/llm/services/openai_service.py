from __future__ import annotations

from typing import Any

from openai import AsyncOpenAI

from core.llm.types import LLMConfig, LLMResponse, TokenUsage, ToolCall
from core.llm.services.base import BaseLLMService
from utils import logger


class OpenAIService(BaseLLMService):
    def __init__(self, config: LLMConfig):
        super().__init__(config)
        self._client = AsyncOpenAI(
            api_key=config.api_key,
            base_url=config.base_url,
        )

    async def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        params: dict[str, Any] = {
            "model": self.config.model,
            "messages": messages,
            "temperature": kwargs.get("temperature", self.config.temperature),
            "max_tokens": kwargs.get("max_tokens", self.config.max_tokens),
        }

        if tools:
            params["tools"] = tools
            params["tool_choice"] = "auto"

        logger.debug("LLM request: model=%s, messages=%d", self.config.model, len(messages))

        resp = await self._client.chat.completions.create(**params)

        choice = resp.choices[0]
        message = choice.message

        tool_calls: list[ToolCall] = []
        if message.tool_calls:
            for tc in message.tool_calls:
                tool_calls.append(
                    ToolCall(
                        id=tc.id,
                        name=tc.function.name,
                        arguments=tc.function.arguments,
                    )
                )

        usage = TokenUsage()
        if resp.usage:
            usage = TokenUsage(
                prompt_tokens=resp.usage.prompt_tokens,
                completion_tokens=resp.usage.completion_tokens,
            )

        logger.debug(
            "LLM response: content_len=%s, tool_calls=%d, tokens=%d",
            len(message.content) if message.content else 0,
            len(tool_calls),
            usage.total_tokens,
        )

        return LLMResponse(
            content=message.content,
            tool_calls=tool_calls,
            usage=usage,
        )

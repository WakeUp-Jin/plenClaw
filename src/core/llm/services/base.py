from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from core.llm.types import LLMConfig, LLMResponse


class BaseLLMService(ABC):
    def __init__(self, config: LLMConfig):
        self.config = config

    @abstractmethod
    async def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> LLMResponse: ...

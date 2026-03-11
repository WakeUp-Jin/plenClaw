from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Awaitable


@dataclass
class InternalTool:
    name: str
    definition: dict[str, Any]   # OpenAI function calling format
    handler: Callable[[dict[str, Any]], Awaitable[str]]
    category: str = "general"

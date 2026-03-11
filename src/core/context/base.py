from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseContext(ABC):
    @abstractmethod
    def get_messages(self) -> list[dict[str, Any]]:
        """Return a list of messages in OpenAI chat format."""
        ...

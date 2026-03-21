"""Unified local file storage layer.

Provides three storage backends:
- ``ConversationStore`` -- JSONL-based conversation history (short-term memory)
- ``LocalMemoryStore`` -- Markdown-based long-term memory
- ``ConfigStore``       -- JSON config with dot-notation access

And the abstract contracts:
- ``IStorage``          -- base class with file I/O primitives
- ``IContextStorage``   -- interface for conversation persistence
"""

from storage.base import IStorage, IContextStorage
from storage.conversation_store import ConversationStore
from storage.memory_store import LocalMemoryStore
from storage.config_store import ConfigStore

__all__ = [
    "IStorage",
    "IContextStorage",
    "ConversationStore",
    "LocalMemoryStore",
    "ConfigStore",
]

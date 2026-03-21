"""Local file-based long-term memory storage.

Stores user profile, preferences and long-term facts in a single Markdown
file (``memory.md``) under the configured data directory.  All operations
are synchronous local I/O -- no network calls.
"""

from __future__ import annotations

from pathlib import Path

from storage.base import IStorage
from utils import logger

MEMORY_FILE = "memory.md"


class LocalMemoryStore(IStorage):
    """Read / append / replace a local ``memory.md`` file."""

    def __init__(self, base_dir: str = "./data/memory") -> None:
        super().__init__(base_dir)
        self._cache: str = ""
        self._load_cache()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def memory_path(self) -> Path:
        return self._base_dir / MEMORY_FILE

    @property
    def is_empty(self) -> bool:
        return not self._cache.strip()

    def get_memory_text(self) -> str:
        """Return the full memory text (from in-memory cache)."""
        return self._cache

    def append_memory(self, content: str) -> bool:
        """Append *content* to the memory file and update cache."""
        try:
            self.append_text(MEMORY_FILE, content + "\n")
            self._cache += content + "\n"
            return True
        except Exception as e:
            logger.error("Failed to append memory: %s", e)
            return False

    def replace_memory(self, content: str) -> bool:
        """Overwrite the entire memory file with *content*."""
        try:
            self.write_text(MEMORY_FILE, content)
            self._cache = content
            return True
        except Exception as e:
            logger.error("Failed to replace memory: %s", e)
            return False

    def clear_memory(self) -> bool:
        """Clear the memory file (write empty string)."""
        return self.replace_memory("")

    def reload(self) -> None:
        """Force-reload from disk (useful after external edits)."""
        self._load_cache()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _load_cache(self) -> None:
        self._cache = self.read_text(MEMORY_FILE)
        if self._cache:
            logger.info(
                "LocalMemoryStore loaded: %d chars from %s",
                len(self._cache),
                self.memory_path,
            )
        else:
            logger.info("LocalMemoryStore: memory file empty or not found")

"""Config file storage with dot-notation access.

Wraps ``config.json`` with convenient get/set helpers that support nested
key paths like ``"llm.models.high.temperature"``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from utils import logger


class ConfigStore:
    """Read / write ``config.json`` with dot-notation key paths."""

    def __init__(self, config_path: str | Path = "./config.json") -> None:
        self._path = Path(config_path)
        self._cache: dict[str, Any] | None = None

    @property
    def config_path(self) -> Path:
        return self._path

    # ------------------------------------------------------------------
    # Full-file operations
    # ------------------------------------------------------------------

    def load(self) -> dict[str, Any]:
        """Load and cache the JSON config from disk."""
        result: dict[str, Any] = {}
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                result = json.load(f)
        except FileNotFoundError:
            logger.warning("Config file not found: %s, using empty dict", self._path)
        except Exception as e:
            logger.error("Failed to load config: %s", e)
        self._cache = result
        return dict(result)

    def save(self, data: dict[str, Any] | None = None) -> None:
        """Write *data* (or the current cache) back to disk."""
        payload = data if data is not None else self._cache
        if payload is None:
            return
        try:
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
                f.write("\n")
            if data is not None:
                self._cache = data
        except Exception as e:
            logger.error("Failed to save config: %s", e)

    # ------------------------------------------------------------------
    # Dot-notation helpers
    # ------------------------------------------------------------------

    def get(self, key_path: str, default: Any = None) -> Any:
        """Retrieve a nested value using ``"a.b.c"`` notation."""
        data = self._ensure_loaded()
        keys = key_path.split(".")
        current: Any = data
        for key in keys:
            if isinstance(current, dict):
                current = current.get(key)
                if current is None:
                    return default
            else:
                return default
        return current

    def set(self, key_path: str, value: Any, *, persist: bool = True) -> None:
        """Set a nested value and optionally write to disk."""
        data = self._ensure_loaded()
        keys = key_path.split(".")
        current = data
        for key in keys[:-1]:
            if key not in current or not isinstance(current[key], dict):
                current[key] = {}
            current = current[key]
        current[keys[-1]] = value
        self._cache = data
        if persist:
            self.save()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _ensure_loaded(self) -> dict[str, Any]:
        if self._cache is None:
            self.load()
        assert self._cache is not None
        return self._cache

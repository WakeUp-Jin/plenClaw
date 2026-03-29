"""JSONL-based conversation storage.

File layout::

    data/conversations/
        conv_20260321_143022.jsonl            <- messages, append-only
        conv_20260321_143022.checkpoint.json  <- compression state
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from storage.base import IContextStorage, IStorage
from utils.logger import logger

FILE_PREFIX = "conv_"
JSONL_SUFFIX = ".jsonl"
CHECKPOINT_SUFFIX = ".checkpoint.json"


@dataclass
class ConversationMeta:
    """Lightweight descriptor returned by ``list_conversations``."""

    conv_id: str
    path: Path
    created_at: str
    message_count: int


class ConversationStore(IStorage, IContextStorage):
    """Append-only JSONL persistence with checkpoint support.

    Implements ``IContextStorage`` so it can be consumed directly by
    ``ShortTermMemoryContext``, while also exposing richer query / management
    methods (list, get, delete).
    """

    def __init__(self, base_dir: str = "./data/conversations") -> None:
        IStorage.__init__(self, base_dir)
        self._conv_file: Path = self._find_or_create_conversation()

    # ------------------------------------------------------------------
    # IContextStorage implementation
    # ------------------------------------------------------------------

    def append(self, message: dict[str, Any]) -> None:
        try:
            with open(self._conv_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(message, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.error("Failed to append message: %s", e)

    def load_all(self) -> list[dict[str, Any]]:
        return self._read_jsonl(self._conv_file)

    def load_from_line(self, line_number: int) -> list[dict[str, Any]]:
        messages: list[dict[str, Any]] = []
        try:
            with open(self._conv_file, "r", encoding="utf-8") as f:
                for i, line in enumerate(f):
                    if i >= line_number:
                        line = line.strip()
                        if line:
                            messages.append(json.loads(line))
        except Exception as e:
            logger.error("Failed to load from line %d: %s", line_number, e)
        return messages

    def count_lines(self) -> int:
        try:
            with open(self._conv_file, "r", encoding="utf-8") as f:
                return sum(1 for line in f if line.strip())
        except Exception:
            return 0

    def save_checkpoint(self, summary: str, checkpoint_line: int) -> None:
        data = {
            "summary": summary,
            "checkpoint_line": checkpoint_line,
            "created_at": datetime.now().isoformat(),
        }
        try:
            with open(self._checkpoint_path(), "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info("Checkpoint saved at line %d", checkpoint_line)
        except Exception as e:
            logger.error("Failed to save checkpoint: %s", e)

    def load_checkpoint(self) -> dict[str, Any] | None:
        cp = self._checkpoint_path()
        if not cp.exists():
            return None
        try:
            with open(cp, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error("Failed to load checkpoint: %s", e)
            return None

    def new_conversation(self) -> None:
        old = self._conv_file
        self._conv_file = self._create_conv_file()
        logger.info(
            "New conversation created. Old: %s, New: %s",
            old.name,
            self._conv_file.name,
        )

    # ------------------------------------------------------------------
    # Query / management helpers
    # ------------------------------------------------------------------

    @property
    def current_conversation_id(self) -> str:
        """Extract the timestamp-based id from the current file name."""
        name = self._conv_file.stem  # e.g. "conv_20260321_143022"
        return name.removeprefix(FILE_PREFIX)

    @property
    def conversation_file(self) -> Path:
        return self._conv_file

    def list_conversations(self) -> list[ConversationMeta]:
        """Return metadata for every conversation file, newest first."""
        files = sorted(
            self._base_dir.glob(f"{FILE_PREFIX}*{JSONL_SUFFIX}"),
            reverse=True,
        )
        result: list[ConversationMeta] = []
        for f in files:
            if f.name.endswith(CHECKPOINT_SUFFIX):
                continue
            conv_id = f.stem.removeprefix(FILE_PREFIX)
            count = self._count_lines(f)
            created = self._conv_id_to_datetime(conv_id)
            result.append(ConversationMeta(
                conv_id=conv_id,
                path=f,
                created_at=created,
                message_count=count,
            ))
        return result

    def get_conversation(self, conv_id: str) -> list[dict[str, Any]]:
        """Load all messages from a specific conversation by id."""
        path = self._base_dir / f"{FILE_PREFIX}{conv_id}{JSONL_SUFFIX}"
        return self._read_jsonl(path)

    def delete_conversation(self, conv_id: str) -> bool:
        """Delete a conversation and its checkpoint file."""
        jsonl = self._base_dir / f"{FILE_PREFIX}{conv_id}{JSONL_SUFFIX}"
        checkpoint = jsonl.with_suffix(CHECKPOINT_SUFFIX)
        ok = True
        for p in (jsonl, checkpoint):
            if p.exists():
                try:
                    p.unlink()
                except Exception as e:
                    logger.error("Failed to delete %s: %s", p, e)
                    ok = False
        return ok

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _find_or_create_conversation(self) -> Path:
        files = sorted(
            self._base_dir.glob(f"{FILE_PREFIX}*{JSONL_SUFFIX}"),
            reverse=True,
        )
        conv_files = [f for f in files if not f.name.endswith(CHECKPOINT_SUFFIX)]
        if conv_files:
            logger.info("Loaded existing conversation: %s", conv_files[0].name)
            return conv_files[0]
        return self._create_conv_file()

    def _create_conv_file(self) -> Path:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = self._base_dir / f"{FILE_PREFIX}{ts}{JSONL_SUFFIX}"
        path.touch()
        logger.info("Created conversation file: %s", path.name)
        return path

    def _checkpoint_path(self) -> Path:
        return self._conv_file.with_suffix(CHECKPOINT_SUFFIX)

    @staticmethod
    def _read_jsonl(path: Path) -> list[dict[str, Any]]:
        messages: list[dict[str, Any]] = []
        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        messages.append(json.loads(line))
        except FileNotFoundError:
            pass
        except Exception as e:
            logger.error("Failed to read %s: %s", path, e)
        return messages

    @staticmethod
    def _count_lines(path: Path) -> int:
        try:
            with open(path, "r", encoding="utf-8") as f:
                return sum(1 for line in f if line.strip())
        except Exception:
            return 0

    @staticmethod
    def _conv_id_to_datetime(conv_id: str) -> str:
        try:
            dt = datetime.strptime(conv_id, "%Y%m%d_%H%M%S")
            return dt.isoformat()
        except ValueError:
            return conv_id

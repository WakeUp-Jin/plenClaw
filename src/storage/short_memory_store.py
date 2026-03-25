"""Time-folder based short-term memory storage.

File layout::

    ~/.pineclaw/memory/short_term/
        state.json                          <- active folder pointer
        20260325_143022/                    <- archived segment
            history.jsonl                   <- raw ContextItem dicts
            checkpoint.json                 <- compression summary
        20260325_160000/                    <- active segment
            history.jsonl
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from storage.base import IContextStorage
from utils import logger

HISTORY_FILE = "history.jsonl"
CHECKPOINT_FILE = "checkpoint.json"
STATE_FILE = "state.json"


class ShortMemoryStore(IContextStorage):
    """Append-only JSONL storage organised into time-stamped folders.

    Each folder represents a memory segment.  When compression happens the
    current folder gets a ``checkpoint.json`` and a new folder is created
    for fresh records.
    """

    def __init__(self, base_dir: str | Path) -> None:
        self._base_dir = Path(base_dir)
        self._base_dir.mkdir(parents=True, exist_ok=True)
        self._active_dir: Path = self._resolve_active_dir()

    @property
    def active_dir(self) -> Path:
        return self._active_dir

    # ------------------------------------------------------------------
    # IContextStorage implementation
    # ------------------------------------------------------------------

    def append(self, message: dict[str, Any]) -> None:
        history = self._active_dir / HISTORY_FILE
        try:
            with open(history, "a", encoding="utf-8") as f:
                f.write(json.dumps(message, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.error("ShortMemoryStore: failed to append: %s", e)

    def load_all(self) -> list[dict[str, Any]]:
        return self._read_jsonl(self._active_dir / HISTORY_FILE)

    def load_from_line(self, line_number: int) -> list[dict[str, Any]]:
        history = self._active_dir / HISTORY_FILE
        messages: list[dict[str, Any]] = []
        try:
            with open(history, "r", encoding="utf-8") as f:
                for i, line in enumerate(f):
                    if i >= line_number:
                        line = line.strip()
                        if line:
                            messages.append(json.loads(line))
        except FileNotFoundError:
            pass
        except Exception as e:
            logger.error("ShortMemoryStore: load_from_line failed: %s", e)
        return messages

    def count_lines(self) -> int:
        history = self._active_dir / HISTORY_FILE
        try:
            with open(history, "r", encoding="utf-8") as f:
                return sum(1 for line in f if line.strip())
        except FileNotFoundError:
            return 0
        except Exception:
            return 0

    def save_checkpoint(self, summary: str, checkpoint_line: int) -> None:
        total = self.count_lines()
        data = {
            "summary": summary,
            "compressed_lines": checkpoint_line,
            "kept_from_line": checkpoint_line,
            "total_lines": total,
            "archive_hint": (
                f"完整原始记录保存在 {self._active_dir.name}/{HISTORY_FILE} "
                f"前 {checkpoint_line} 行"
            ),
            "created_at": datetime.now().isoformat(),
        }
        cp_path = self._active_dir / CHECKPOINT_FILE
        try:
            with open(cp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                f.write("\n")
            logger.info(
                "Checkpoint saved: %s (compressed %d / %d lines)",
                self._active_dir.name, checkpoint_line, total,
            )
        except Exception as e:
            logger.error("ShortMemoryStore: save_checkpoint failed: %s", e)

    def load_checkpoint(self) -> dict[str, Any] | None:
        cp_path = self._active_dir / CHECKPOINT_FILE
        if not cp_path.exists():
            return None
        try:
            with open(cp_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error("ShortMemoryStore: load_checkpoint failed: %s", e)
            return None

    def rotate(self) -> Path:
        """Archive the current segment and start a new one.

        Called after compression.  Returns the new active directory.
        """
        new_dir = self._create_segment_dir()
        self._active_dir = new_dir
        self._save_state(new_dir.name)
        logger.info("Memory segment rotated -> %s", new_dir.name)
        return new_dir

    # ------------------------------------------------------------------
    # Segment listing (for tools that retrieve archived memory)
    # ------------------------------------------------------------------

    def list_segments(self) -> list[Path]:
        """Return all segment folders sorted by name (oldest first)."""
        return sorted(
            [d for d in self._base_dir.iterdir() if d.is_dir()],
            key=lambda p: p.name,
        )

    def load_segment_checkpoint(self, segment_name: str) -> dict[str, Any] | None:
        cp = self._base_dir / segment_name / CHECKPOINT_FILE
        if not cp.exists():
            return None
        try:
            with open(cp, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_active_dir(self) -> Path:
        """Read state.json to find active folder, or create one."""
        state = self._load_state()
        active_name = state.get("active_folder", "")

        if active_name:
            active = self._base_dir / active_name
            if active.is_dir():
                logger.info("ShortMemoryStore: active segment = %s", active_name)
                return active
            logger.warning(
                "ShortMemoryStore: state points to %s but it doesn't exist, creating new",
                active_name,
            )

        return self._create_segment_dir()

    def _create_segment_dir(self) -> Path:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        d = self._base_dir / ts
        d.mkdir(parents=True, exist_ok=True)
        (d / HISTORY_FILE).touch()
        self._save_state(ts)
        logger.info("ShortMemoryStore: created segment %s", ts)
        return d

    def _load_state(self) -> dict[str, Any]:
        state_path = self._base_dir / STATE_FILE
        if not state_path.exists():
            return {}
        try:
            with open(state_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _save_state(self, folder_name: str) -> None:
        state_path = self._base_dir / STATE_FILE
        data = {
            "active_folder": folder_name,
            "created_at": datetime.now().isoformat(),
        }
        try:
            with open(state_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                f.write("\n")
        except Exception as e:
            logger.error("ShortMemoryStore: _save_state failed: %s", e)

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
            logger.error("ShortMemoryStore: _read_jsonl failed on %s: %s", path, e)
        return messages

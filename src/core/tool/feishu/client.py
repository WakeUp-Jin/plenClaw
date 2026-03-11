from __future__ import annotations

import json
from typing import Any

import lark_oapi as lark

from utils import logger


class FeishuClient:
    """Shared Feishu API client wrapping lark-oapi SDK."""

    def __init__(self, app_id: str, app_secret: str):
        self.app_id = app_id
        self.app_secret = app_secret
        self.client = (
            lark.Client.builder()
            .app_id(app_id)
            .app_secret(app_secret)
            .log_level(lark.LogLevel.WARNING)
            .build()
        )
        self.api_call_count = 0

    def increment_api_count(self) -> None:
        self.api_call_count += 1

    def reset_api_count(self) -> int:
        count = self.api_call_count
        self.api_call_count = 0
        return count

    @staticmethod
    def check_response(resp: Any, action: str) -> dict[str, Any]:
        """Check lark-oapi response and return data or raise."""
        if not resp.success():
            error_msg = f"Feishu API [{action}] failed: code={resp.code}, msg={resp.msg}"
            logger.error(error_msg)
            return {"error": error_msg}
        return {}

    @staticmethod
    def to_json(data: Any) -> str:
        if isinstance(data, str):
            return data
        return json.dumps(data, ensure_ascii=False, default=str)

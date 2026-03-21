"""工具调度器 —— 管理工具调用的完整生命周期。

参考 Reason Code 的 ToolScheduler，实现:
  validating -> (awaiting_approval) -> executing -> success / error / cancelled
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any, Callable, Awaitable, TYPE_CHECKING

from core.tool.types import (
    ApprovalMode,
    ConfirmDetails,
    InternalTool,
    ScheduleResult,
    ToolCallRecord,
    ToolCallStatus,
)
from core.tool.approval import ApprovalStore, ApprovalOutcome
from utils import logger

if TYPE_CHECKING:
    from core.tool.manager import ToolManager


class ToolSchedulerConfig:
    __slots__ = ("approval_mode", "approval_timeout")

    def __init__(
        self,
        approval_mode: ApprovalMode = ApprovalMode.YOLO,
        approval_timeout: float = 120.0,
    ) -> None:
        self.approval_mode = approval_mode
        self.approval_timeout = approval_timeout


# 审批卡片发送回调类型: (chat_id, card_json_str) -> None
SendCardFn = Callable[[str, str], Awaitable[None]]


class ToolScheduler:
    def __init__(
        self,
        tool_manager: ToolManager,
        approval_store: ApprovalStore,
        config: ToolSchedulerConfig | None = None,
        send_card: SendCardFn | None = None,
    ) -> None:
        self._tool_manager = tool_manager
        self._approval_store = approval_store
        self._config = config or ToolSchedulerConfig()
        self._send_card = send_card
        self._records: dict[str, ToolCallRecord] = {}

    @property
    def tool_manager(self) -> ToolManager:
        return self._tool_manager

    # ------------------------------------------------------------------
    # 公开 API
    # ------------------------------------------------------------------

    async def schedule(
        self,
        call_id: str,
        tool_name: str,
        raw_args: str,
        chat_id: str = "",
    ) -> ScheduleResult:
        """单个工具调用的完整调度流程。"""

        # 1. validating ─ 参数解析 & 工具查找
        record = ToolCallRecord(call_id=call_id, tool_name=tool_name)
        self._records[call_id] = record

        try:
            args = json.loads(raw_args) if raw_args else {}
        except json.JSONDecodeError as e:
            return self._set_error(record, f"参数解析失败: {e}")

        record.args = args

        tool = self._tool_manager.get_tool(tool_name)
        if tool is None:
            return self._set_error(record, f"工具不存在: {tool_name}")

        # 2. 审批检查
        needs_confirm = self._check_confirmation(tool)
        if needs_confirm:
            record.status = ToolCallStatus.AWAITING_APPROVAL
            record.confirm_details = needs_confirm
            logger.info(
                "Tool %s (call=%s) awaiting approval", tool_name, call_id,
            )

            # 发送审批卡片 (如果配置了 send_card 且有 chat_id)
            if self._send_card and chat_id:
                card_json = self._build_approval_card(call_id, tool_name, args)
                try:
                    await self._send_card(chat_id, card_json)
                except Exception as e:
                    logger.error("Failed to send approval card: %s", e)

            outcome = await self._approval_store.wait_for_approval(
                call_id, timeout=self._config.approval_timeout,
            )

            if outcome != "approve":
                reason = "用户取消" if outcome == "cancel" else "审批超时"
                return self._set_cancelled(record, reason)

        # 3. executing
        record.status = ToolCallStatus.EXECUTING
        logger.info("Tool executing: %s (call=%s)", tool_name, call_id)

        try:
            tool_result = await self._tool_manager.execute(tool_name, args)
        except Exception as e:
            logger.error("Tool %s execution error: %s", tool_name, e, exc_info=True)
            return self._set_error(record, str(e))

        if not tool_result.success:
            return self._set_error(record, tool_result.error or "工具执行失败")

        # 4. 输出格式化 (render_result) -> success
        result_str = self._tool_manager.render(tool_name, tool_result)
        return self._set_success(record, result_str)

    async def schedule_batch(
        self,
        tool_calls: list[dict[str, Any]],
        chat_id: str = "",
    ) -> list[ScheduleResult]:
        """批量调度 LLM 返回的 tool_calls。

        只读工具并行执行，否则串行。
        """
        if self._can_parallel(tool_calls):
            tasks = [
                self.schedule(
                    call_id=tc["id"],
                    tool_name=tc["function"]["name"],
                    raw_args=tc["function"]["arguments"],
                    chat_id=chat_id,
                )
                for tc in tool_calls
            ]
            return list(await asyncio.gather(*tasks))

        results: list[ScheduleResult] = []
        for tc in tool_calls:
            r = await self.schedule(
                call_id=tc["id"],
                tool_name=tc["function"]["name"],
                raw_args=tc["function"]["arguments"],
                chat_id=chat_id,
            )
            results.append(r)
        return results

    def get_records(self) -> list[ToolCallRecord]:
        return list(self._records.values())

    def clear_records(self) -> None:
        self._records.clear()

    # ------------------------------------------------------------------
    # 审批检查
    # ------------------------------------------------------------------

    def _check_confirmation(self, tool: InternalTool) -> ConfirmDetails | None:
        """根据 ApprovalMode 和工具属性判断是否需要确认。"""
        if self._config.approval_mode == ApprovalMode.YOLO:
            return None

        # 工具显式声明不需要确认
        if tool.should_confirm is False:
            return None

        # 只读工具不需要确认
        if tool.is_read_only:
            return None

        # 工具显式声明需要确认，或 DEFAULT 模式下非只读工具
        return ConfirmDetails(
            title="工具执行确认",
            message=f"即将执行工具 {tool.name}，是否继续？",
            tool_name=tool.name,
        )

    # ------------------------------------------------------------------
    # 审批卡片构建
    # ------------------------------------------------------------------

    @staticmethod
    def _build_approval_card(
        call_id: str, tool_name: str, args: dict[str, Any],
    ) -> str:
        args_preview = json.dumps(args, ensure_ascii=False, indent=2)
        if len(args_preview) > 500:
            args_preview = args_preview[:500] + "\n..."

        card = {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"tag": "plain_text", "content": "工具执行确认"},
                "template": "orange",
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": (
                            f"**工具**: `{tool_name}`\n"
                            f"**参数**:\n```json\n{args_preview}\n```"
                        ),
                    },
                },
                {
                    "tag": "action",
                    "actions": [
                        {
                            "tag": "button",
                            "text": {"tag": "plain_text", "content": "批准执行"},
                            "type": "primary",
                            "value": {"call_id": call_id, "outcome": "approve"},
                        },
                        {
                            "tag": "button",
                            "text": {"tag": "plain_text", "content": "取消"},
                            "type": "danger",
                            "value": {"call_id": call_id, "outcome": "cancel"},
                        },
                    ],
                },
            ],
        }
        return json.dumps(card, ensure_ascii=False)

    # ------------------------------------------------------------------
    # 并行判断
    # ------------------------------------------------------------------

    def _can_parallel(self, tool_calls: list[dict[str, Any]]) -> bool:
        if len(tool_calls) <= 1:
            return False
        for tc in tool_calls:
            tool = self._tool_manager.get_tool(tc["function"]["name"])
            if tool is None or not tool.is_read_only:
                return False
        return True

    # ------------------------------------------------------------------
    # 状态设置
    # ------------------------------------------------------------------

    def _set_success(self, record: ToolCallRecord, result_string: str) -> ScheduleResult:
        record.status = ToolCallStatus.SUCCESS
        record.result = result_string
        record.duration_ms = record.elapsed_ms()
        logger.info(
            "Tool %s success (call=%s, %.0fms)",
            record.tool_name, record.call_id, record.duration_ms,
        )
        return ScheduleResult(
            call_id=record.call_id,
            tool_name=record.tool_name,
            success=True,
            status=ToolCallStatus.SUCCESS,
            result=result_string,
            result_string=result_string,
        )

    def _set_error(self, record: ToolCallRecord, error: str) -> ScheduleResult:
        record.status = ToolCallStatus.ERROR
        record.error = error
        record.duration_ms = record.elapsed_ms()
        logger.error(
            "Tool %s error (call=%s): %s", record.tool_name, record.call_id, error,
        )
        return ScheduleResult(
            call_id=record.call_id,
            tool_name=record.tool_name,
            success=False,
            status=ToolCallStatus.ERROR,
            error=error,
        )

    def _set_cancelled(self, record: ToolCallRecord, reason: str) -> ScheduleResult:
        record.status = ToolCallStatus.CANCELLED
        record.error = reason
        record.duration_ms = record.elapsed_ms()
        logger.warning(
            "Tool %s cancelled (call=%s): %s",
            record.tool_name, record.call_id, reason,
        )
        return ScheduleResult(
            call_id=record.call_id,
            tool_name=record.tool_name,
            success=False,
            status=ToolCallStatus.CANCELLED,
            error=reason,
        )

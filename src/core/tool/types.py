from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Awaitable
import time


class ToolCallStatus(str, Enum):
    """工具调用生命周期状态"""
    VALIDATING = "validating"
    AWAITING_APPROVAL = "awaiting_approval"
    EXECUTING = "executing"
    SUCCESS = "success"
    ERROR = "error"
    CANCELLED = "cancelled"


class ApprovalMode(str, Enum):
    """审批模式：控制工具执行前的确认行为"""
    DEFAULT = "default"   # 非只读工具需要用户确认
    YOLO = "yolo"         # 全部自动批准


@dataclass
class ConfirmDetails:
    """确认详情，描述需要用户确认的工具调用"""
    title: str
    message: str
    tool_name: str
    args_summary: str = ""


@dataclass
class InternalTool:
    """工具定义"""
    name: str
    definition: dict[str, Any]   # OpenAI function calling format
    handler: Callable[[dict[str, Any]], Awaitable[str]]
    category: str = "general"
    is_read_only: bool = False
    should_confirm: bool | None = None  # None = 由 ApprovalMode 决定


@dataclass
class ToolCallRecord:
    """单次工具调用的完整生命周期记录"""
    call_id: str
    tool_name: str
    status: ToolCallStatus = ToolCallStatus.VALIDATING
    args: dict[str, Any] = field(default_factory=dict)
    result: Any = None
    error: str | None = None
    start_time: float = field(default_factory=time.time)
    duration_ms: float | None = None
    confirm_details: ConfirmDetails | None = None

    def elapsed_ms(self) -> float:
        return (time.time() - self.start_time) * 1000


@dataclass
class ScheduleResult:
    """调度器返回给 tool_loop 的结果"""
    call_id: str
    tool_name: str
    success: bool
    status: ToolCallStatus
    result: Any = None
    result_string: str = ""
    error: str | None = None

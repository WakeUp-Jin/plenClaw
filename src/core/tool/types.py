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
class ToolParameterSchema:
    """JSON Schema 风格的工具参数定义"""
    type: str = "object"
    properties: dict[str, Any] = field(default_factory=dict)
    required: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "properties": self.properties,
            "required": self.required,
        }


@dataclass
class ToolResult:
    """工具执行的统一结果，所有 handler 都应返回此类型"""
    success: bool
    data: Any = None
    error: str | None = None

    @staticmethod
    def ok(data: Any = None) -> ToolResult:
        return ToolResult(success=True, data=data)

    @staticmethod
    def fail(error: str) -> ToolResult:
        return ToolResult(success=False, error=error)


@dataclass
class InternalTool:
    """工具定义——覆盖名称、描述、参数 Schema、执行函数、输出格式化"""
    name: str
    category: str
    description: str
    parameters: ToolParameterSchema
    handler: Callable[[dict[str, Any]], Awaitable[ToolResult]]
    render_result: Callable[[ToolResult], str] | None = None
    is_read_only: bool = False
    should_confirm: bool | None = None  # None = 由 ApprovalMode 决定

    def get_openai_function(self) -> dict[str, Any]:
        """输出 OpenAI function calling 格式的工具定义"""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters.to_dict(),
        }


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

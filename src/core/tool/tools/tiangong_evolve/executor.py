"""天工锻造令工具的执行逻辑。

如意通过此工具向天工下达锻造令——生成一份 Markdown 文件写入
.pineclaw/tiangong/orders/pending/ 目录，天工定时巡查后开始锻造。
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any

from config.settings import get_pineclaw_home
from core.tool.types import ToolResult
from utils.logger import get_logger

logger = get_logger("tool.tiangong_evolve")


async def tiangong_evolve_handler(args: dict[str, Any]) -> ToolResult:
    """生成锻造令并写入 pending 目录。"""
    task: str = args.get("task", "").strip()
    if not task:
        return ToolResult.fail("task is required: 需要描述锻造什么工具")

    tool_name: str = args.get("tool_name", "").strip()
    if not tool_name:
        tool_name = _derive_tool_name(task)

    now = datetime.now()
    filename = f"{now.strftime('%Y%m%d-%H%M%S')}-{tool_name}.md"

    order_content = _build_order(tool_name, task, now)

    pending_dir = get_pineclaw_home() / "tiangong" / "orders" / "pending"
    pending_dir.mkdir(parents=True, exist_ok=True)
    order_path = pending_dir / filename

    try:
        order_path.write_text(order_content, encoding="utf-8")
    except OSError as e:
        logger.error("Failed to write forge order: %s", e)
        return ToolResult.fail(f"写入锻造令失败: {e}")

    logger.info("Forge order created: %s", order_path)
    return ToolResult.ok(
        f"锻造令已下达：{filename}\n"
        f"天工将在下次巡查时开始锻造 {tool_name}。\n"
        f"锻造令位置：{order_path}"
    )


def render_evolve_result(result: ToolResult) -> str:
    """格式化锻造令结果供 LLM 阅读。"""
    if not result.success:
        return f"Error: {result.error}"
    return str(result.data)


def _derive_tool_name(task: str) -> str:
    """从任务描述中提取一个简短的工具名。

    取前 30 个字符，替换非字母数字字符为短横线，转小写。
    """
    short = task[:30]
    name = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff]+", "-", short).strip("-").lower()
    return name or "new-tool"


def _build_order(tool_name: str, task: str, now: datetime) -> str:
    """构建锻造令 Markdown 内容。"""
    return (
        f"# 锻造令：{tool_name}\n"
        f"\n"
        f"## 需求描述\n"
        f"\n"
        f"{task}\n"
        f"\n"
        f"## 元信息\n"
        f"\n"
        f"- 创建时间：{now.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"- 请求方：如意\n"
        f"- 优先级：normal\n"
    )

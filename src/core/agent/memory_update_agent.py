"""Dedicated LOW-model agents for daily long-term memory updates.

Each agent is a thin wrapper around a single LLM call (not a full Agent
with tool loops).  It reads today's short-term records plus the current
content of its assigned long-term memory file, then decides whether an
update is needed.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from utils.logger import get_logger

if TYPE_CHECKING:
    from core.llm.services.base import BaseLLMService
    from storage.memory_store import LocalMemoryStore

logger = get_logger("memory_update_agent")


# ------------------------------------------------------------------
# Per-file system prompts
# ------------------------------------------------------------------

_PROMPTS: dict[str, str] = {
    "user_instructions": (
        "你是一个记忆更新助手，负责维护「用户指令」文件。\n\n"
        "任务：阅读今天的对话记录，识别用户说的明确指令和规则，例如：\n"
        "- 「以后都要…」、「记住不要…」、「每次都帮我…」\n"
        "- 对 Agent 行为的约束和期望\n\n"
        "如果找到新指令，将其提炼为简洁的规则条目，追加到文件末尾。\n"
        "如果没有新指令，回复「无需更新」。\n"
        "保留文件中所有已有内容，只追加新内容。"
    ),

    "user_profile": (
        "你是一个记忆更新助手，负责维护「用户画像」文件。\n\n"
        "任务：阅读今天的对话记录，识别用户透露的个人信息：\n"
        "- 姓名、职业、技术背景、使用的编程语言/框架\n"
        "- 工作习惯、时间偏好\n"
        "- 推断的信息请标注 [推断]\n\n"
        "如果有新信息，更新文件中对应部分或追加新条目。\n"
        "如果没有新信息，回复「无需更新」。\n"
        "保留所有已有内容。"
    ),

    "facts_and_decisions": (
        "你是一个记忆更新助手，负责维护「事实与决策」文件。\n\n"
        "任务：阅读今天的对话记录，识别用户做出的重要决策和确认的事实：\n"
        "- 技术选型决策（如选择某个框架、数据库）\n"
        "- 架构决策和设计选择\n"
        "- 用户明确确认的事实\n\n"
        "每个条目应包含日期标注和简要说明。\n"
        "如果有新的事实或决策，追加到文件末尾。\n"
        "如果没有，回复「无需更新」。\n"
        "保留所有已有内容。"
    ),

    "topics_and_interests": (
        "你是一个记忆更新助手，负责维护「话题与兴趣」文件。\n\n"
        "任务：阅读今天的对话记录，识别用户反复讨论或表现出兴趣的话题：\n"
        "- 经常提起的技术领域\n"
        "- 关注的项目和产品\n"
        "- 学习中的知识领域\n\n"
        "只有当某个话题在多次交互中出现时才值得记录。\n"
        "如果有新的兴趣话题，追加到文件末尾。\n"
        "如果没有，回复「无需更新」。\n"
        "保留所有已有内容。"
    ),
}

_NO_UPDATE_MARKERS = {"无需更新", "无需更新。", "不需要更新", "无变化"}


async def run_single_update(
    llm: BaseLLMService,
    memory_store: LocalMemoryStore,
    file_name: str,
    daily_text: str,
) -> tuple[str, bool, str]:
    """Run a single memory update agent for one file.

    Returns (file_name, updated, detail_message).
    """
    system_prompt = _PROMPTS.get(file_name, "")
    if not system_prompt:
        return file_name, False, "no prompt defined"

    current_content = memory_store.read_file(file_name)

    user_message = (
        f"## 当前「{file_name}」文件内容\n\n"
        f"{current_content if current_content.strip() else '(空)'}\n\n"
        f"## 今天的对话记录\n\n{daily_text}\n\n"
        f"请分析对话记录，决定是否需要更新文件。"
        f"如果需要更新，直接输出更新后的完整文件内容（保留所有已有内容+新增内容）。"
        f"如果不需要更新，只回复「无需更新」。"
    )

    try:
        response = await llm.simple_chat(user_message, system_prompt=system_prompt)
    except Exception as e:
        logger.error("LLM call failed for %s: %s", file_name, e)
        return file_name, False, f"llm_error: {e}"

    response_stripped = response.strip()

    if response_stripped in _NO_UPDATE_MARKERS:
        return file_name, False, "no update needed"

    success, msg = memory_store.safe_write(file_name, response_stripped)
    if success:
        logger.info("Updated %s: %s", file_name, msg)
        return file_name, True, msg
    else:
        logger.warning("Update blocked for %s: %s", file_name, msg)
        return file_name, False, msg

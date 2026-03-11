from __future__ import annotations

import json
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from memory.memory_store import MemoryStore

# --- Tool Definitions ---

memory_append_def: dict[str, Any] = {
    "name": "memory_append",
    "description": (
        "向长期记忆追加一条新信息。当对话中出现值得长期记住的用户偏好、"
        "个人信息、工作习惯或重要事实时调用。不要记录临时性信息。"
        "格式：Markdown 列表项，重要事实带日期前缀 [YYYY-MM-DD]。"
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "section": {
                "type": "string",
                "description": "记忆分类，如：用户画像、工作习惯、重要事实、偏好指令",
            },
            "content": {
                "type": "string",
                "description": "要追加的记忆内容，Markdown 格式",
            },
        },
        "required": ["section", "content"],
    },
}

memory_rewrite_def: dict[str, Any] = {
    "name": "memory_rewrite",
    "description": (
        "整理和重写整个记忆文件。当记忆内容出现重复、过时或需要重新组织时调用。"
        "传入整理后的完整 Markdown 内容，将替换现有记忆。谨慎使用。"
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "content": {
                "type": "string",
                "description": "整理后的完整记忆内容，Markdown 格式，必须以 '# PineClaw Memory' 开头",
            },
        },
        "required": ["content"],
    },
}


# --- Tool Handlers ---

async def memory_append_handler(memory_store: MemoryStore, args: dict[str, Any]) -> str:
    section = args["section"]
    content = args["content"]

    current_text = memory_store.get_memory_text()
    if f"## {section}" in current_text:
        append_text = f"- {content}"
    else:
        append_text = f"\n## {section}\n- {content}"

    success = await memory_store.append(append_text)
    if success:
        return json.dumps({"status": "ok", "message": f"已记住：{content}"}, ensure_ascii=False)
    return json.dumps(
        {"status": "cached", "message": "记忆写入飞书失败，已缓存在本地，将在下次重试"},
        ensure_ascii=False,
    )


async def memory_rewrite_handler(memory_store: MemoryStore, args: dict[str, Any]) -> str:
    content = args["content"]

    if not content.startswith("# PineClaw Memory"):
        return json.dumps(
            {"error": "记忆内容必须以 '# PineClaw Memory' 开头"},
            ensure_ascii=False,
        )

    success = await memory_store.replace(content)
    if success:
        return json.dumps({"status": "ok", "message": "记忆已整理并更新"}, ensure_ascii=False)
    return json.dumps(
        {"status": "failed", "message": "记忆覆写飞书失败，已回滚"},
        ensure_ascii=False,
    )


def register_memory_tools(tool_manager: Any, memory_store: MemoryStore) -> None:
    """Register memory_append and memory_rewrite tools."""
    tool_manager.register(
        name="memory_append",
        definition=memory_append_def,
        handler=lambda args: memory_append_handler(memory_store, args),
        category="memory",
    )
    tool_manager.register(
        name="memory_rewrite",
        definition=memory_rewrite_def,
        handler=lambda args: memory_rewrite_handler(memory_store, args),
        category="memory",
    )

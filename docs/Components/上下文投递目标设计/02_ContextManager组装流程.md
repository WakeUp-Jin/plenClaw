# ContextManager 组装流程

## 概览

`ContextManager` 是上下文的"总调度"，Agent 调用 `get_context()` 时触发全部组装逻辑。

**文件**: `src/core/context/manager.py`

## 组装步骤

### Step 1: _collect_parts() — 收集各模块的 ContextParts

按顺序调用每个模块的 `format()`，收集到两个列表里：

```python
def _collect_parts(self) -> tuple[list[SystemPart], list[ContextItem]]:
    all_system: list[SystemPart] = []
    all_messages: list[ContextItem] = []

    for parts in [
        self._system_prompt.format(),
        self._long_term.format() if self._long_term else ContextParts(),
        self._short_term.format(),
    ]:
        all_system.extend(parts.system_parts)
        all_messages.extend(parts.message_items)

    return all_system, all_messages
```

**顺序很重要**：

| 顺序 | 模块 | system_parts 内容 | message_items 内容 |
|------|------|-------------------|-------------------|
| 1 | SystemPromptContext | 核心提示词 | — |
| 2 | LongTermMemoryContext | 用户记忆 | — |
| 3 | ShortTermMemoryContext | 压缩摘要（如有） | 对话消息 |

这个顺序决定了最终 system message 内部各段落的排列。

### Step 2: get_context() — 渲染合并

```python
def get_context(self) -> list[dict[str, Any]]:
    system_parts, message_items = self._collect_parts()
    messages: list[dict[str, Any]] = []

    # 合并 system_parts 为 1 条 system message
    if system_parts:
        rendered = SYSTEM_PART_SEPARATOR.join(
            part.render() for part in system_parts if part.content.strip()
        )
        messages.append({"role": "system", "content": rendered})

    # message_items 逐个转为 LLM message dict
    messages.extend(item.to_message() for item in message_items)

    return self._sanitize(messages)
```

1. 对 `system_parts` 列表中的每个 `SystemPart` 调用 `render()`，渲染为 XML 标签文本
2. 用 `"\n\n"` 分隔符拼接所有渲染后的文本，组成一条 `role="system"` 消息
3. 对 `message_items` 中的每个 `ContextItem` 调用 `to_message()`，逐个转为 dict 放入消息列表
4. 最后 `_sanitize()` 确保 tool_calls/tool 消息配对正确

### Step 3: _sanitize() — 消息清理

调用 `sanitize_messages()` 确保：

- 每个带 `tool_calls` 的 assistant 消息都有完整的 tool 响应
- 不存在孤立的 tool 消息（找不到对应的 tool_call_id）

## 最终输出示例

```python
[
    {
        "role": "system",
        "content": (
            "<system_prompt>\n"
            "你是 PineClaw，一个AI 助手...\n"
            "</system_prompt>\n"
            "\n"
            '<long_term_memory description="以下是你对用户的长期记忆，请基于这些信息个性化回复">\n'
            "用户偏好：中文回复，简洁风格\n"
            "</long_term_memory>\n"
            "\n"
            '<conversation_summary description="以下是之前对话的压缩摘要">\n'
            "之前讨论了上下文模块的架构设计...\n"
            "</conversation_summary>"
        ),
    },
    {"role": "user", "content": "继续讨论"},
    {"role": "assistant", "content": "好的..."},
    # ...
]
```

只有 **1 条** system message，所有 system 级内容都通过 XML 标签区分。

## Token 估算

`estimate_tokens()` 复用 `_collect_parts()`，将 system_parts 合并为一个 `ContextItem(role="system")` 后与 message_items 一起计算 token 总量。

这是一种**近似估算**，用于判断"当前上下文是否接近阈值，需要触发压缩"，不用于实际计费。实际 token 数和费用以 LLM API 返回的 `usage` 为准。

```python
def _build_context_items(self) -> list[ContextItem]:
    """返回 ContextItem 列表（用于 token 估算等场景）。"""
    system_parts, message_items = self._collect_parts()
    items: list[ContextItem] = []
    if system_parts:
        rendered = SYSTEM_PART_SEPARATOR.join(
            part.render() for part in system_parts if part.content.strip()
        )
        items.append(ContextItem(
            role="system",
            content=rendered,
            source="merged_system",
            priority=MessagePriority.CRITICAL,
        ))
    items.extend(message_items)
    return items
```

## 完整数据流图

```
           ┌─────────────────────────┐
           │   Agent.run()           │
           │   调用 ctx.get_context()│
           └────────────┬────────────┘
                        │
                        ▼
         ┌──────────────────────────────┐
         │      _collect_parts()        │
         │                              │
         │  SystemPromptContext.format() │──→ ContextParts(system_parts=[SP1])
         │  LongTermMemoryContext.format()──→ ContextParts(system_parts=[SP2])
         │  ShortTermMemoryContext.format()─→ ContextParts(system_parts=[SP3],
         │                              │                  message_items=[...])
         └──────────────┬───────────────┘
                        │
              ┌─────────┴──────────┐
              │                    │
              ▼                    ▼
     list[SystemPart]       list[ContextItem]
     [SP1, SP2, SP3]        [item1, item2, ...]
              │                    │
              ▼                    ▼
    SP.render() + join        item.to_message()
              │                    │
              ▼                    ▼
    1 条 system msg          N 条 conversation msg
              │                    │
              └─────────┬──────────┘
                        │
                        ▼
                 sanitize_messages()
                        │
                        ▼
              list[dict] → 发送给 LLM
```

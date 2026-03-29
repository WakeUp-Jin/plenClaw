# PineClaw 记忆模块需求实现文档

---

## 一、设计理念

### 1.1 模块定位

记忆模块是 PineClaw 的核心基础设施，赋予 Agent 跨时间的持续记忆能力。它采用 **Skill 规范** 存储在 `~/.pineclaw/skills/memory/` 下，用户拥有完全控制权，可以迁移到任何支持 Skill 加载的 Agent 系统。

### 1.2 核心思想

模仿人类记忆的运作方式：

- **长期记忆**：存储稳定的、经过沉淀的重要信息（用户指令、画像、决策、兴趣）
- **短期记忆**：保留近期的交互细节，通过分层压缩实现自然的"遗忘"
- **无会话概念**：个人助手 Agent 的陪伴是永久长期的，不是任务驱动的短期交互

### 1.3 4 层渐进式披露

| 层级 | 内容 | 加载方式 |
|------|------|----------|
| **第 1 层** | SKILL.md 元信息 | Skill 扫描时自动读取 frontmatter |
| **第 2 层** | SKILL.md 正文 | `always_load_content: true`，自动内联到 system prompt |
| **第 3 层** | 长期记忆文件 | `user_instructions.md` 必加载；其他 3 个由 Agent 按需 ReadFile |
| **第 4 层** | 短期记忆文件 | 基于 Token 预算自动加载，从最近往回 |

---

## 二、文件结构

```
~/.pineclaw/skills/memory/                        # Skill 根目录
  SKILL.md                                        # 层1+层2：元信息 + 文件索引
  long_term/                                      # 层3：长期记忆
    user_instructions.md                          # 用户对 Agent 的明确指令和规则
    user_profile.md                               # 用户基本信息和个人画像
    facts_and_decisions.md                        # 用户确认的事实和重要决策
    topics_and_interests.md                       # 用户的兴趣和关注领域
  short_term/                                     # 层4：短期记忆
    2026-03/
      2026-03-29.jsonl                            # 今天的完整对话记录（ContextItem 序列化）
      2026-03-28.jsonl
      week_03-17_to_03-23.summary.md              # 周摘要
    2026-02/
      month_2026-02.summary.md                    # 月摘要
      week_02-24_to_03-02.summary.md
      2026-02-28.jsonl                            # 原文永久保留
    year_2025.summary.md                          # 年摘要
  update_logs/
    2026-03-29.update.md                          # 长期记忆更新日志
```

### 关键设计决策

- **日记录是完整的原始对话**：每条 `.jsonl` 记录是一个 `ContextItem.to_dict()` 的序列化结果，包含 role、content、tool_calls、thinking、usage 等全部字段，不是摘要
- **摘要与原文同目录**：周摘要、月摘要直接放在对应月份文件夹中，不设独立的归档文件夹
- **年摘要放在 short_term/ 根目录**
- **无 state.json**：不再需要追踪活跃文件夹，按日期自动组织

---

## 三、SKILL.md 设计

### 3.1 实现方式

```yaml
---
name: "用户记忆"
type: memory
always_load_content: true
description: "用户的记忆模块。包含用户指令、偏好画像、事实决策、兴趣话题和完整交互历史。"
---
```

`always_load_content: true` 是记忆 Skill 区别于所有其他 Skill 的关键标志。

### 3.2 加载机制

`SkillMeta` 新增了两个字段：

```python
@dataclass
class SkillMeta:
    name: str
    description: str
    location: Path
    always_load_content: bool = False  # 新增
    body: str = ""                     # 新增：存储正文
```

`scanner.py` 在解析 SKILL.md 时：

1. 读取 frontmatter 中的 `always_load_content` 字段
2. 如果为 `true`，将 SKILL.md 正文存入 `SkillMeta.body`
3. `build_catalog()` 将正文直接内联到 catalog XML 的 `<content>` 标签中

这样 Agent 不需要额外调用 ReadFile 就能获得记忆模块的文件索引。

### 3.3 正文内容

正文包含：

- 长期记忆文件索引表（文件名、说明、加载策略）
- `user_instructions.md` 标记为每次必加载（已通过 LongTermMemoryContext 注入 system prompt）
- 其他 3 个文件的按需加载条件说明
- 短期记忆的组织方式和加载策略
- 可用的记忆工具清单

---

## 四、短期记忆

### 4.1 存储层：ShortMemoryStore

**文件**：`src/storage/short_memory_store.py`

**核心变更**（相对于旧版时间戳文件夹模式）：

- 废弃 `YYYYMMDD_HHMMSS/history.jsonl` 模式，改为 `YYYY-MM/YYYY-MM-DD.jsonl`
- 去掉 `load_all()`、`load_from_line()`、`save_checkpoint()`、`load_checkpoint()`、`rotate()` 等旧方法
- `IContextStorage` 接口精简为只保留 `append()`

**公开 API**：

| 方法 | 说明 |
|------|------|
| `append(message)` | 追加到当天 .jsonl，跨天自动切换文件 |
| `load_today()` | 读取今天的完整记录 |
| `load_daily(date)` | 读取指定日期的记录 |
| `get_daily_path(date)` | 获取某天的 .jsonl 路径 |
| `list_month_dirs()` | 列出所有月份文件夹（按时间排序） |
| `list_daily_files(month_dir)` | 列出某月所有 .jsonl |
| `list_summaries(month_dir)` | 列出某月所有 .summary.md |
| `list_year_summaries()` | 列出所有年摘要 |
| `get_all_dates_descending()` | 所有有记录的日期，最新在前 |
| `is_covered_by_summary(date, summaries)` | 判断某天是否被摘要覆盖 |
| `find_covering_summary(date, summaries)` | 返回覆盖该天的摘要文件 |
| `save_summary(path, content)` | 写入摘要文件 |
| `read_summary(path)` | 读取摘要文件 |
| `count_today_lines()` | 当天记录行数 |

### 4.2 上下文模块：ShortTermMemoryContext

**文件**：`src/core/context/modules/short_term_memory.py`

**核心变更**：

#### 基于 Token 预算的分层加载

构造函数接收 `context_window` 和 `initial_load_ratio`（默认 0.60）。

`_load_memory()` 的加载逻辑：

```
初始加载预算 = context_window × initial_load_ratio

从最新日期开始倒序扫描：
  1. 如果该天被某个摘要覆盖 → 加载摘要（同一摘要只加载一次）
  2. 否则 → 加载该天的 .jsonl 原始记录
  3. 每加载一份，累加 token 消耗
  4. 预算用完 → 停止

最后检查年摘要，在预算允许时加载。
```

#### 两阶段压缩

`compress()` 方法采用两阶段策略：

**第一阶段：磁盘级压缩**（`_try_disk_compression`）

- 找出今天和昨天之外、尚未被摘要覆盖的日期
- 取最早的连续 7 天（不足 7 天也可以）
- 调用 `ContextCompressor.compress_to_week_summary()` 生成周摘要
- 摘要写入磁盘，然后重新执行 `_load_memory()` 刷新内存

**第二阶段：内存级压缩**（`_try_intra_day_compression`）

- 当磁盘级压缩无法执行（所有历史日记录都已被摘要覆盖）但仍超预算时触发
- 对当前 turn 之前的内存中 items 做 LLM 摘要
- 摘要存入 `_intra_day_summary`，作为 SystemPart 输出

#### 压缩触发条件

`needs_compression()` 的阈值从旧版的 80% 改为 **85%**（`CompressionConfig.compression_threshold = 0.85`）。

### 4.3 压缩器：ContextCompressor

**文件**：`src/core/context/utils/compressor.py`

新增三个多层摘要方法：

| 方法 | 输入 | 侧重点 |
|------|------|--------|
| `compress_to_week_summary` | 连续 N 天的 .jsonl 文件路径 | 事件完整性，按时间线梳理本周发生了什么 |
| `compress_to_month_summary` | 本月日记录路径 + 周摘要文本 | 核心决策和变化，用日记录避免周摘要的"稀释" |
| `compress_to_year_summary` | 月摘要文本列表 | 最重要的里程碑，输入月摘要是上下文窗口成本最优解 |

保留旧的 `compress_with_llm()` 方法用于日内溢出的内存级压缩。

### 4.4 CompressionConfig 扩展

```python
@dataclass
class CompressionConfig:
    context_window: int = 128000
    compression_threshold: float = 0.85      # 从 0.8 上调
    compress_keep_ratio: float = 0.3
    initial_load_ratio: float = 0.60         # 新增
    days_per_week_summary: int = 7           # 新增
```

---

## 五、长期记忆

### 5.1 存储层：LocalMemoryStore

**文件**：`src/storage/memory_store.py`

**核心变更**（相对于旧版单文件 `memory.md`）：

- 管理 4 个独立 `.md` 文件：`user_instructions`、`user_profile`、`facts_and_decisions`、`topics_and_interests`
- 基础目录改为 `~/.pineclaw/skills/memory/long_term/`
- 内存缓存：所有 4 个文件的内容在初始化时加载到 `_cache` 字典

**公开 API**：

| 方法 | 说明 |
|------|------|
| `read_file(name)` | 读取指定文件（优先从缓存） |
| `write_file(name, content)` | 直接覆写（无 diff 校验） |
| `safe_write(name, new_content)` | 带 diff 校验的覆写 |
| `append_to_file(name, content)` | 追加内容 |
| `is_empty(name)` | 检查文件是否为空 |
| `reload(name)` | 强制从磁盘重新加载 |
| `list_nonempty_files()` | 列出有内容的文件名 |

**diff 校验机制**（`safe_write`）：

提取新旧文件中的结构性标识符（Markdown 标题、**粗体**列表项），对比是否有条目丢失。如果发现条目消失，拒绝写入并返回详细信息。

```python
@staticmethod
def _extract_entry_ids(content: str) -> set[str]:
    """识别：## Section Name、- **Label**: ..."""
```

**设计决策：不设备份机制**，保持简洁。diff 校验已经能防止幻觉导致的数据丢失。

### 5.2 4 个长期记忆文件

| 文件 | 职责 | 加载方式 |
|------|------|----------|
| `user_instructions.md` | 用户对 Agent 的明确指令和规则 | **LongTermMemoryContext 每次注入 system prompt** |
| `user_profile.md` | 用户基本信息和个人画像 | Agent 按需 ReadFile |
| `facts_and_decisions.md` | 用户确认的事实和重要决策 | Agent 按需 ReadFile |
| `topics_and_interests.md` | 用户的兴趣和关注领域 | Agent 按需 ReadFile |

### 5.3 上下文模块：LongTermMemoryContext

**文件**：`src/core/context/modules/long_term_memory.py`

**核心变更**：

- **只加载 `user_instructions.md`**，作为 `SystemPart` 注入 system prompt
- 其他 3 个文件不由 ContextManager 加载，而是由 Agent 根据 SKILL.md 正文中的索引信息自主使用 ReadFile 工具按需读取
- 文件不存在时返回空 `ContextParts`，不报错

---

## 六、记忆工具体系

### 6.1 工具总览

| 工具 | 用途 | 注册位置 |
|------|------|----------|
| `memory` | append / rewrite 操作 | `memory_tools.py` |
| `read_memory` | 读取指定长期记忆文件 | `memory_tools.py` |
| `edit_memory` | 精确局部编辑 | `edit_memory_tool.py` |

三个工具在 `register_memory_tools()` 中统一注册。

### 6.2 memory 工具

```python
{
    "action": "append" | "rewrite",
    "file": "user_instructions" | "user_profile" | "facts_and_decisions" | "topics_and_interests",
    "content": "Markdown 内容"
}
```

- `append`：调用 `LocalMemoryStore.append_to_file()`
- `rewrite`：调用 `LocalMemoryStore.safe_write()`（带 diff 校验）

### 6.3 read_memory 工具

```python
{
    "file": "user_instructions" | "user_profile" | "facts_and_decisions" | "topics_and_interests"
}
```

返回文件内容的 JSON，空文件返回 `"(空文件)"`。

### 6.4 edit_memory 工具

**统一替换模型**：所有增删改操作都映射为 `old_string` → `new_string`。

```python
{
    "file": "...",
    "old_string": "要替换的原文（添加时留空）",
    "new_string": "替换后的内容（删除时留空）"
}
```

**匹配策略**：

1. **精确匹配**：`content.count(old_string)`
   - 恰好 1 次 → 执行替换
   - 0 次 → 降级到宽松匹配
   - ≥ 2 次 → 返回 `ambiguous_match` 错误
2. **宽松匹配**（降级）：逐行 trim 后比较，处理行首行尾空白差异

**错误类型**：

| error_type | 含义 | Agent 应采取的行动 |
|------------|------|-------------------|
| `file_not_found` | 无效文件名 | 检查 file 参数 |
| `not_found` | old_string 未匹配 | 先 read_memory 确认内容 |
| `ambiguous_match` | 匹配到多处 | 加更多上下文到 old_string |
| `no_change` | old/new 相同 | 检查参数 |

---

## 七、长期记忆定时更新系统

### 7.1 架构

每天定时触发，并行启动 4 个专职 LOW 模型 Agent，每个只负责一个文件的更新判断。

```
APScheduler 定时触发（默认 23:30）
    │
    ▼
检查当天是否有日记录 ── 无 → 跳过
    │
    有
    │
    ▼
读取当天日记录全文 + 4 个长期记忆文件当前内容
    │
    ▼
╔═══════════════════════════════════════════╗
║  asyncio.gather 并行启动 4 个更新 Agent    ║
║                                           ║
║  · user_instructions Agent                ║
║  · user_profile Agent                     ║
║  · facts_and_decisions Agent              ║
║  · topics_and_interests Agent             ║
╚═══════════════════════╤═══════════════════╝
                        │
                        ▼
               收集结果 + diff 校验
                        │
                        ▼
               生成更新日志
```

### 7.2 调度器：MemoryUpdateScheduler

**文件**：`src/scheduler/memory_updater.py`

- 使用 APScheduler 的 `AsyncIOScheduler` + `CronTrigger`
- 触发时间在 `config.json` 中配置：`memory.long_term.update_schedule`
- 提供 `run_now()` 方法用于手动触发/测试
- `apscheduler` 未安装时优雅降级（只打日志，不崩溃）

### 7.3 更新 Agent：memory_update_agent

**文件**：`src/core/agent/memory_update_agent.py`

每个更新 Agent 不是完整的 Agent（没有工具循环），只是一次 `simple_chat` 调用：

**输入**：

```
1. 专属系统提示词（识别什么信息应该写入该文件）
2. 该长期记忆文件的当前全文
3. 今日短期记忆日记录全文
```

**输出**：

- 需要更新 → 输出更新后的完整文件内容，通过 `safe_write()` 写入
- 无需更新 → 回复「无需更新」

**4 个 Agent 的专属提示词**：

| Agent | 识别目标 |
|-------|---------|
| user_instructions | 用户说的「以后都要…」、「记住不要…」等祈使句 |
| user_profile | 用户透露的个人信息、职业、技术背景，推断信息标注 `[推断]` |
| facts_and_decisions | 技术决策、架构选择、用户确认的事实 |
| topics_and_interests | 反复讨论的话题和兴趣领域（需要一定频率才写入） |

### 7.4 更新日志

每次更新生成日志写入 `update_logs/YYYY-MM-DD.update.md`，格式示例：

```markdown
# 记忆更新日志 2026-03-29

更新时间: 2026-03-29T23:30:05

- **facts_and_decisions**: ✅ 已更新 — ok
- **topics_and_interests**: ⏭️ 无变化 — no update needed
- **user_instructions**: ✅ 已更新 — ok
- **user_profile**: ⏭️ 无变化 — no update needed
```

---

## 八、系统集成

### 8.1 settings.py 变更

路径全部迁移到 `~/.pineclaw/skills/memory/`：

```python
@property
def short_term_dir(self) -> Path:
    return get_pineclaw_home() / "skills" / "memory" / "short_term"

@property
def long_term_dir(self) -> Path:
    return get_pineclaw_home() / "skills" / "memory" / "long_term"

@property
def update_log_dir(self) -> Path:
    return get_pineclaw_home() / "skills" / "memory" / "update_logs"
```

新增配置：

```python
@dataclass
class LongTermMemoryConfig:
    update_schedule: str = "23:30"
    max_file_size_tokens: int = 3000
    enable_diff_check: bool = True
```

`ensure_pineclaw_dirs()` 更新为创建 `skills/memory/{long_term,short_term,update_logs}` 目录，不再创建旧的 `memory/` 目录。

### 8.2 main.py 变更

启动流程新增：

1. `ShortTermMemoryContext` 构造时传入 `context_window` 和 `initial_load_ratio`
2. 初始化 `MemoryUpdateScheduler` 并 `await start()`
3. 首次启动时删除旧的 `~/.pineclaw/memory/` 目录

关闭流程新增：

1. `await _memory_scheduler.stop()`

### 8.3 ContextManager 变更

`compress()` 方法的注释更新，反映新的两阶段压缩策略。其他逻辑不变——`LongTermMemoryContext` 只加载 `user_instructions.md`，其他文件的按需加载由 Agent 自身完成。

### 8.4 Agent 变更

`_compress_history()` 的 summarize_fn 提示词增强，要求保留关键决策、文件路径、技术选型和未完成任务。

---

## 九、依赖

```toml
# pyproject.toml
dependencies = [
    ...
    "apscheduler>=3.10",
]
```

---

## 十、代码文件清单

### 新建文件

| 文件 | 说明 |
|------|------|
| `~/.pineclaw/skills/memory/SKILL.md` | Skill 元信息 + 文件索引正文 |
| `src/core/tool/edit_memory_tool.py` | edit_memory 工具实现 |
| `src/core/agent/memory_update_agent.py` | 4 个 LOW 模型更新 Agent |
| `src/scheduler/__init__.py` | scheduler 包 |
| `src/scheduler/memory_updater.py` | APScheduler 定时更新调度器 |

### 重写文件

| 文件 | 核心变更 |
|------|----------|
| `src/storage/short_memory_store.py` | 时间戳文件夹 → 按天 .jsonl |
| `src/storage/memory_store.py` | 单 memory.md → 4 独立文件 + diff 校验 |
| `src/core/context/modules/short_term_memory.py` | Token 预算加载 + 两阶段压缩 |
| `src/core/context/modules/long_term_memory.py` | 只加载 user_instructions.md |
| `src/core/context/utils/compressor.py` | 新增周/月/年三层摘要方法 |
| `src/core/tool/memory_tools.py` | 3 个工具统一注册 |

### 修改文件

| 文件 | 核心变更 |
|------|----------|
| `src/storage/base.py` | IContextStorage 精简为只保留 append() |
| `src/core/context/types.py` | CompressionConfig 新增 initial_load_ratio、days_per_week_summary |
| `src/core/skill/types.py` | SkillMeta 新增 always_load_content + body |
| `src/core/skill/scanner.py` | 解析 always_load_content，内联正文到 catalog |
| `src/config/settings.py` | 路径迁移 + LongTermMemoryConfig |
| `src/core/context/manager.py` | compress() 注释更新 |
| `src/core/agent/agent.py` | summarize_fn 提示词增强 |
| `src/main.py` | 集成调度器 + 清理旧目录 |
| `pyproject.toml` | 添加 apscheduler 依赖 |

---

## 十一、完整交互时序

### 11.1 启动时

```
应用启动
  │
  ▼
ensure_pineclaw_dirs() 创建 skills/memory/ 目录树
  │
  ▼
ShortMemoryStore 初始化，创建今日 .jsonl 文件
  │
  ▼
ShortTermMemoryContext 初始化：
  基于 Token 预算从磁盘加载历史记录（最新优先）
  │
  ▼
LocalMemoryStore 初始化，缓存 4 个长期记忆文件
  │
  ▼
LongTermMemoryContext 初始化（只读取 user_instructions.md）
  │
  ▼
Skill scanner 扫描发现 memory SKILL：
  always_load_content=true → 正文内联到 catalog XML
  │
  ▼
MemoryUpdateScheduler.start()：注册每日定时任务
  │
  ▼
删除旧的 ~/.pineclaw/memory/ 目录（如存在）
```

### 11.2 每轮对话

```
用户发来消息
  │
  ▼
用户消息 → ContextItem → append 到 ShortTermMemoryContext + 当日 .jsonl
  │
  ▼
get_context() 组装消息序列：
  system prompt（含 user_instructions + SKILL catalog + 历史摘要）
  + 已加载的 ContextItem 列表
  │
  ▼
LLM 生成回复（可能使用 read_memory/edit_memory 工具）
  │
  ▼
助手回复 → ContextItem → append
  │
  ▼
needs_compression()？（已用容量 ≥ 85%？）
  │
  YES → compress()：
  │     先尝试磁盘级周摘要压缩
  │     不行则回退到内存级日内压缩
  │
  NO → 等待下一条消息
```

### 11.3 每日 23:30

```
APScheduler 触发
  │
  ▼
读取今日 .jsonl → 转为文本
  │
  ▼
并行调用 4 个 LOW 模型 Agent：
  每个 Agent 判断是否需要更新对应的长期记忆文件
  │
  ▼
safe_write() 带 diff 校验写入
  │
  ▼
生成 update_logs/YYYY-MM-DD.update.md
```

---

## 十二、配置参数汇总

```json
{
  "memory": {
    "short_term": {
      "compression_threshold": 0.85,
      "compress_keep_ratio": 0.3,
      "initial_load_ratio": 0.60
    },
    "long_term": {
      "update_schedule": "23:30",
      "max_file_size_tokens": 3000,
      "enable_diff_check": true
    }
  }
}
```

---

## 十三、与旧需求文档的差异

本文档基于实际实现的代码，以下是相对于早期需求文档（`记忆模块实现文档.md`、`长期记忆的详细实现.md`）的主要差异：

| 维度 | 早期设计 | 实际实现 |
|------|---------|---------|
| 长期记忆文件数量 | 7 个（含 corrections、project_context、interaction_patterns） | **4 个** |
| 日记录内容 | 摘要格式（Markdown，含重要性标注 🔴🟡🟢） | **完整 ContextItem 序列化的 .jsonl** |
| 长期记忆加载 | 3 个必加载 + 4 个按需 | **只有 user_instructions 必加载**，其他按需 |
| 月摘要输入 | 周摘要 | **日记录 + 周摘要**（避免稀释） |
| 备份机制 | 每次写入前备份 5 个版本 | **无备份**，依靠 diff 校验 |
| 更新方式 | 交互中实时更新 | **每日定时更新**（APScheduler） |
| 存储位置 | `~/.pineclaw/memory/` | **`~/.pineclaw/skills/memory/`**（Skill 规范） |
| 会话概念 | 有（session） | **无**（永久陪伴） |
| Skill 加载 | Agent 按需读取 SKILL.md | **always_load_content 自动内联** |

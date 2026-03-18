# Claude Agent SDK 实现：官方 SDK 集成 Skill

## 概述

Claude Agent SDK 是 Anthropic 官方提供的 Agent 开发工具包，专门用于**程序化控制 Claude Code 的 Agent 循环**。
它提供了自动化的 tool_use 循环、Hooks 拦截机制、以及通过 MCP 注册自定义工具的能力。

> **重要限制**：Claude Agent SDK 底层依赖 Claude Code CLI，
> **只支持 Anthropic 模型**（Claude Sonnet/Opus/Haiku）。
> 无法切换到 OpenAI、Google 等其他提供商。

**记录本文档的价值**：即使不能直接使用，其设计哲学（特别是 Hooks 机制和 MCP 工具系统）值得参考。

---

## 安装

```bash
# Python
pip install anthropic

# TypeScript
npm install @anthropic-ai/claude-code
```

---

## 核心概念

### Agent 主循环

SDK 自动处理 tool_use 循环，无需手动编写 `while stop_reason == "tool_use"` 的逻辑：

```
User Input
    ↓
SDK query() 函数
    ↓
Claude 评估 → 需要工具？
    ├── Yes → 执行工具 → 结果返回 Claude → 继续评估
    └── No  → 返回最终答案
```

### 五种消息类型

| 消息类型 | 说明 |
|---------|------|
| `SystemMessage` | Session 生命周期事件（init、compact_boundary） |
| `ToolUseMessage` | LLM 请求调用工具 |
| `ToolResultMessage` | 工具执行完成，结果返回 |
| `FieldUpdateMessage` | 字段更新事件 |
| `AgentFinishMessage` | Agent 完成任务 |

---

## 基础用法

### TypeScript

```typescript
import { query, type SDKMessage } from "@anthropic-ai/claude-code";

async function runAgent(userInput: string): Promise<string> {
  const messages: SDKMessage[] = [];
  let finalResponse = "";

  // query() 返回异步迭代器，自动处理 tool_use 循环
  for await (const message of query({
    prompt: userInput,
    options: {
      allowedTools: ["Read", "Write", "Edit", "Bash"],
      maxTurns: 20,
    }
  })) {
    messages.push(message);

    if (message.type === "assistant") {
      finalResponse = message.message.content
        .filter(b => b.type === "text")
        .map(b => b.text)
        .join("");
    }

    // 可以在这里处理流式输出
    if (message.type === "tool_use") {
      console.log(`[工具] ${message.tool_name}: ${JSON.stringify(message.tool_input)}`);
    }
  }

  return finalResponse;
}
```

### Python（通过 subprocess 调用）

Claude Agent SDK 的 Python 接口通过调用 Claude Code CLI 实现：

```python
import subprocess
import json
from typing import Generator

def query_claude_agent(
    prompt: str,
    allowed_tools: list[str] = None,
    system_prompt: str = None,
    max_turns: int = 20,
) -> Generator[dict, None, None]:
    """
    调用 Claude Agent SDK（通过 claude CLI 的 JSON 模式）。
    注意：需要安装 claude CLI 并认证。
    """
    cmd = ["claude", "--output-format", "json", "--max-turns", str(max_turns)]

    if allowed_tools:
        cmd += ["--allowedTools", ",".join(allowed_tools)]

    if system_prompt:
        cmd += ["--system-prompt", system_prompt]

    cmd += [prompt]

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    for line in process.stdout:
        line = line.strip()
        if line:
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                pass

    process.wait()
```

---

## Hooks 机制（最有价值的设计参考）

Hooks 是 Claude Agent SDK 最独特的设计——在工具调用的关键节点拦截和控制：

```typescript
import { query } from "@anthropic-ai/claude-code";

for await (const message of query({
  prompt: "重构整个项目",
  options: {
    allowedTools: ["Read", "Write", "Edit", "Bash"],

    // PreToolUse Hook：工具调用前拦截
    hooks: {
      PreToolUse: [
        async (event) => {
          // 拦截危险的 bash 命令
          if (event.tool_name === "Bash") {
            const cmd = event.tool_input.command as string;
            if (cmd.includes("rm -rf") || cmd.includes("DROP TABLE")) {
              console.warn(`[拦截] 危险命令: ${cmd}`);
              return {
                decision: "block",
                reason: "包含危险操作，已阻止执行"
              };
            }
          }

          // 记录所有工具调用
          console.log(`[PreToolUse] ${event.tool_name}`);
          return { decision: "allow" };
        }
      ],

      // PostToolUse Hook：工具调用后处理
      PostToolUse: [
        async (event) => {
          // 记录执行结果
          console.log(`[PostToolUse] ${event.tool_name} 完成`);
          // 可以修改返回结果
          return event.tool_result;
        }
      ]
    }
  }
})) {
  // 处理消息流
}
```

**这个 Hook 机制的价值**：在自建系统中，可以仿照这个设计实现权限控制层。

---

## 自定义工具（MCP 方式）

Claude Agent SDK 通过 **MCP（Model Context Protocol）** 注册自定义工具：

### 进程内 MCP（In-Process）

```typescript
import { query, createSdkMcpServer } from "@anthropic-ai/claude-code";

// 创建进程内 MCP 服务器（不需要启动外部进程）
const mcpServer = createSdkMcpServer({
  name: "custom-tools",
  tools: [
    {
      name: "deploy",
      description: "Deploy the application to a target environment",
      inputSchema: {
        type: "object" as const,
        properties: {
          environment: {
            type: "string",
            enum: ["staging", "production"]
          },
          version: { type: "string" }
        },
        required: ["environment"]
      },
      handler: async ({ environment, version }) => {
        // 实际部署逻辑
        console.log(`Deploying ${version} to ${environment}...`);
        return {
          content: [{
            type: "text",
            text: `Successfully deployed to ${environment}`
          }]
        };
      }
    }
  ]
});

// 在 query 中使用自定义工具
for await (const message of query({
  prompt: "部署到 staging 环境",
  options: {
    mcpServers: [mcpServer],
    allowedTools: [
      "Read", "Write", "Edit", "Bash",
      "mcp__custom-tools__deploy"  // 命名格式：mcp__服务名__工具名
    ]
  }
})) {
  // 处理消息
}
```

### 外部进程 MCP（subprocess stdio）

```typescript
// 启动外部 MCP 服务器（适合隔离执行）
const externalMcp = {
  type: "stdio" as const,
  command: "python",
  args: ["/path/to/your/mcp_server.py"],
  env: { PYTHONPATH: "/path/to/lib" }
};

for await (const message of query({
  prompt: "...",
  options: {
    mcpServers: [externalMcp],
  }
})) {}
```

---

## Skill 系统集成（需自建）

Claude Agent SDK 没有内置 Skill 系统，需要手动实现并注入到 system prompt：

```typescript
import { query } from "@anthropic-ai/claude-code";
import * as fs from "fs";
import * as path from "path";
import * as yaml from "js-yaml";

// ─── Skill 系统（需自建）────────────────────────────

interface SkillMeta {
  name: string;
  description: string;
  version?: string;
}

interface Skill {
  meta: SkillMeta;
  dir: string;
  body?: string;
}

function loadSkills(skillsDir: string): Skill[] {
  if (!fs.existsSync(skillsDir)) return [];

  return fs.readdirSync(skillsDir)
    .filter(d => fs.statSync(path.join(skillsDir, d)).isDirectory())
    .map(dir => {
      const skillMdPath = path.join(skillsDir, dir, "SKILL.md");
      if (!fs.existsSync(skillMdPath)) return null;

      const content = fs.readFileSync(skillMdPath, "utf-8");
      const frontmatterMatch = content.match(/^---\n([\s\S]*?)\n---/);
      if (!frontmatterMatch) return null;

      const meta = yaml.load(frontmatterMatch[1]) as SkillMeta;
      return { meta, dir: path.join(skillsDir, dir) };
    })
    .filter(Boolean) as Skill[];
}

function detectTriggered(skills: Skill[], userInput: string): Skill[] {
  const input = userInput.toLowerCase();
  return skills.filter(skill => {
    const phrases = skill.meta.description.match(/"([^"]+)"/g)
      ?.map(p => p.replace(/"/g, "")) ?? [];
    return phrases.some(p => input.includes(p.toLowerCase()));
  });
}

function loadBody(skill: Skill): string {
  if (skill.body) return skill.body;
  const content = fs.readFileSync(path.join(skill.dir, "SKILL.md"), "utf-8");
  skill.body = content.replace(/^---[\s\S]*?---\n/, "").trim();
  return skill.body;
}

function buildSkillContext(triggered: Skill[]): string {
  if (!triggered.length) return "";
  return "\n\n---\n## Loaded Skills\n" + triggered.map(skill => {
    let ctx = `\n### ${skill.meta.name}\n\n${loadBody(skill)}`;

    // 告知脚本路径
    const scriptsDir = path.join(skill.dir, "scripts");
    if (fs.existsSync(scriptsDir)) {
      const scripts = fs.readdirSync(scriptsDir);
      if (scripts.length > 0) {
        ctx += "\n\n**可用脚本（使用 Bash 工具执行）：**\n";
        ctx += scripts.map(s =>
          `- \`${s}\`: \`bash ${path.join(scriptsDir, s)}\``
        ).join("\n");
      }
    }

    return ctx;
  }).join("\n");
}

// ─── 集成到 Claude Agent SDK ─────────────────────────

const BASE_SYSTEM = "You are a helpful coding agent.";
const skills = loadSkills("./skills");

async function runWithSkills(userInput: string): Promise<string> {
  // 1. 触发 Skill 并构建 system prompt
  const triggered = detectTriggered(skills, userInput);
  const systemPrompt = BASE_SYSTEM + buildSkillContext(triggered);

  let finalText = "";

  // 2. 使用 Claude Agent SDK（自动处理 tool_use 循环）
  for await (const message of query({
    prompt: userInput,
    options: {
      systemPrompt,                      // 注入 Skill 内容
      allowedTools: ["Read", "Write", "Edit", "Bash"],
      maxTurns: 20,
    }
  })) {
    if (message.type === "assistant") {
      finalText = message.message.content
        .filter((b: any) => b.type === "text")
        .map((b: any) => b.text)
        .join("");
    }
  }

  return finalText;
}
```

---

## 子代理（Multi-Agent）

Claude Agent SDK 支持子代理模式，每个子代理可以有不同的 system prompt 和工具集：

```typescript
import { query } from "@anthropic-ai/claude-code";

// 子代理：专门负责代码审查
async function codeReviewAgent(code: string): Promise<string> {
  let result = "";
  for await (const message of query({
    prompt: `审查以下代码：\n\n${code}`,
    options: {
      systemPrompt: "You are an expert code reviewer. Focus on bugs, security, and performance.",
      allowedTools: ["Read"],  // 只读权限
      maxTurns: 5,
    }
  })) {
    if (message.type === "assistant") {
      result = message.message.content
        .filter((b: any) => b.type === "text")
        .map((b: any) => b.text)
        .join("");
    }
  }
  return result;
}

// 主代理：调用子代理
async function mainAgent(userInput: string) {
  for await (const message of query({
    prompt: userInput,
    options: {
      allowedTools: [
        "Read", "Write", "Edit", "Bash",
        "mcp__sub-agents__code_review"  // 注册为自定义工具
      ],
      mcpServers: [
        createSdkMcpServer({
          name: "sub-agents",
          tools: [{
            name: "code_review",
            description: "Review code using a specialized sub-agent",
            inputSchema: {
              type: "object" as const,
              properties: { code: { type: "string" } },
              required: ["code"]
            },
            handler: async ({ code }) => ({
              content: [{ type: "text", text: await codeReviewAgent(code) }]
            })
          }]
        })
      ]
    }
  })) {
    // 处理消息
  }
}
```

---

## 与自建实现的设计对比

### Claude Agent SDK 的设计借鉴点

| 设计点 | Claude Agent SDK | 自建实现 |
|--------|-----------------|---------|
| **Tool Use 循环** | SDK 自动处理 | 需手写 while 循环 |
| **Hooks 机制** | PreToolUse / PostToolUse | 在 execute_tool() 里手动加判断 |
| **工具注册** | MCP 标准（跨进程） | Python dict schema |
| **子代理** | 递归 query() 调用 | 递归调用 run_agent() |
| **Skill 系统** | 无内置，需自建 | 自建（约 150 行） |
| **多模型** | ❌ 仅 Anthropic | ✅ 任意支持 tool_use 的模型 |

### 如何把 Hook 理念移植到自建系统

```python
# 自建版本的 "Hook" 机制
class ToolHooks:
    async def pre_tool_use(self, tool_name: str, inputs: dict) -> dict | None:
        """
        返回 None 表示允许执行。
        返回 {"blocked": True, "reason": "..."} 表示阻止。
        """
        if tool_name == "bash":
            cmd = inputs.get("command", "")
            if "rm -rf" in cmd:
                return {"blocked": True, "reason": "危险命令被阻止"}
        return None

    async def post_tool_use(self, tool_name: str, result: str) -> str:
        """可以修改工具返回结果"""
        return result


# 在 execute_tool 中使用
hooks = ToolHooks()

async def execute_tool_with_hooks(name: str, inputs: dict) -> str:
    blocked = await hooks.pre_tool_use(name, inputs)
    if blocked:
        return f"[blocked]: {blocked['reason']}"

    result = execute_tool(name, inputs)
    return await hooks.post_tool_use(name, result)
```

---

## 局限性总结

```
Claude Agent SDK
    ├── ✅ 自动 tool_use 循环（省代码）
    ├── ✅ Hooks 机制（精细控制）
    ├── ✅ MCP 工具系统（进程隔离）
    ├── ✅ 子代理支持（官方设计）
    ├── ❌ 只支持 Anthropic 模型
    ├── ❌ 没有内置 Skill 系统（需自建）
    ├── ❌ 依赖 Claude Code CLI（需安装）
    └── ❌ Python 支持为 subprocess 包装，非原生
```

**结论**：如果你能用 Anthropic 模型，Claude Agent SDK 可以省去写 tool_use 循环的工作；
但 Skill 系统无论如何都需要自建，其核心逻辑与 `01_自建实现.md` 完全一致。

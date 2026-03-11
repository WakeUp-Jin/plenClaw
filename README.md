# PineClaw

基于飞书协同空间的轻量级 AI Agent。在飞书单聊中与机器人对话，它能帮你操作文档、多维表格、云空间、任务——就像一个住在飞书里的私人助理。

## 它能做什么

- **对话**：在飞书单聊中发消息，Agent 智能回复
- **文档操作**：创建、读取、修改飞书云文档
- **多维表格**：创建表格、增删改查记录、管理字段
- **云空间浏览**：像 `ls` 一样列出文件夹内容，创建文件夹
- **任务管理**：创建飞书任务、任务列表，查询和更新状态
- **长期记忆**：自动记住你的偏好和重要信息，存储在飞书云文档中

## 架构

```
用户 ←→ 飞书机器人（单聊 p2p）←→ PineClaw Agent
                                      │
                            ┌─────────┼─────────┐
                            │         │         │
                        Context     LLM       Tool
                        上下文模块   大模型     工具模块
                        │                     │
                        ├─ 系统提示词          ├─ 飞书 IM 消息（3）
                        ├─ 长期记忆            ├─ 云文档（5）
                        ├─ 会话历史            ├─ 多维表格（7）
                        └─ 工具序列            ├─ 云空间（4）
                                              ├─ 任务（4）
                                              └─ 记忆（2）
```

三模块架构：**Context**（上下文管理）/ **LLM**（大模型调用 + 工具循环）/ **Tool**（25 个工具），由 **SimpleAgent** 编排。

## 快速开始

### 前置条件

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) 包管理器
- 飞书开放平台企业自建应用（需开启机器人能力）

### 1. 克隆并安装依赖

```bash
git clone <repo-url> PineClaw
cd PineClaw
uv sync
```

### 2. 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env`，填入：

```env
# 飞书应用（从飞书开放平台获取）
FEISHU_APP_ID=cli_xxxxxxxxxxxxxxx
FEISHU_APP_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# LLM（支持 DeepSeek、OpenAI 等 OpenAI 兼容接口）
LLM_API_KEY=sk-xxxxxxxx
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_MODEL=deepseek-chat
```

### 3. 配置飞书开放平台

1. 在 [飞书开放平台](https://open.feishu.cn/) 创建企业自建应用
2. 开启 **机器人** 能力
3. 配置事件订阅 → 添加事件 `im.message.receive_v1`，选择 **长连接** 模式
4. 申请权限：`im:message`、`im:message:send_as_bot`、`docs:doc`、`docx:document`、`bitable:app`、`drive:drive`、`task:task`
5. 发布应用并通过管理员审核

### 4. 启动

```bash
python main.py
```

启动后在飞书中找到机器人，直接发消息即可。

### Docker 部署

```bash
cp .env.example .env
# 编辑 .env 填入配置
docker compose up -d
```

## 项目结构

```
PineClaw/
├── main.py                     # 入口：组装模块，启动服务
├── pyproject.toml              # 依赖管理
├── config/settings.py          # 配置（从 .env 加载）
│
├── core/
│   ├── llm/                    # LLM 模块
│   │   ├── services/openai_service.py   # OpenAI 兼容调用
│   │   └── utils/tool_loop.py           # 工具调用循环
│   ├── context/                # 上下文模块
│   │   ├── manager.py                   # 上下文管理器
│   │   └── modules/                     # 系统提示/会话/记忆/工具序列
│   ├── tool/                   # 工具模块
│   │   ├── manager.py                   # 工具注册与执行
│   │   ├── feishu/                      # 23 个飞书 API 工具
│   │   └── memory_tools.py             # 2 个记忆工具
│   └── agent/simple_agent.py   # Agent 编排
│
├── channels/feishu/            # 飞书 Channel（WebSocket 长连接）
├── memory/                     # 记忆模块（飞书云文档 + 本地缓存）
├── api/                        # FastAPI 路由（健康检查/调试/Webhook）
└── docs/                       # 设计文档
```

## 技术栈

| 组件 | 选型 |
|------|------|
| 语言 | Python 3.12+ |
| 包管理 | uv |
| API 框架 | FastAPI + uvicorn |
| 飞书 SDK | lark-oapi |
| LLM | OpenAI 兼容接口（DeepSeek / OpenAI / ...） |
| 容器化 | Docker |

## 设计文档

- [总体架构设计](docs/architecture.md)
- [飞书工具封装设计](docs/feishu-tools-design.md)
- [记忆模块设计](docs/memory-design.md)

## License

MIT

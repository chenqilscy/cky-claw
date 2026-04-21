# Kasaya CLI 使用说明

> 版本：v0.1.0
> 日期：2026-04-15

## 1. 简介

Kasaya CLI（`kasaya`）是 Kasaya 平台的命令行交互工具，提供终端环境下的 Agent 对话、管理和运行能力。

**核心功能**：
- 🗣️ **交互式 Agent 对话**：在终端中与 Agent 实时对话
- 🔐 **登录认证**：安全认证到 Kasaya 后端
- 🤖 **Agent 管理**：查看 Agent 列表和详情
- 🔌 **Provider 管理**：查看厂商列表、测试连通性
- ▶️ **运行 Agent**：发送单条消息并获取 Agent 回复

---

## 2. 安装

### 从 PyPI 安装

```bash
pip install kasaya-cli
```

### 从源码安装（开发者）

```bash
cd kasaya-cli
uv sync
```

### 系统要求

- Python ≥ 3.12
- 依赖：typer（CLI 框架）、rich（格式化输出）、kasaya

---

## 3. 快速开始

### 3.1 登录

```bash
kasaya login
```

交互式输入用户名和密码，成功后 JWT Token 自动保存。

也可以通过环境变量配置：

```bash
export KASAYA_URL=http://localhost:8000    # 后端地址
export KASAYA_TOKEN=your-jwt-token         # 认证 Token
```

### 3.2 开始对话

```bash
kasaya chat
```

进入交互式对话模式，与默认 Agent 进行多轮对话。

### 3.3 查看版本

```bash
kasaya version
```

---

## 4. 命令详解

### 4.1 `kasaya chat` — 交互式对话

在终端中与 AI Agent 进行交互式多轮对话。

```bash
kasaya chat [OPTIONS]
```

**参数**：

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `--model` | string | `gpt-4o-mini` | 使用的模型名称 |
| `--instructions` | string | — | Agent 的系统指令 |
| `--name` | string | — | Agent 名称 |
| `--max-turns` | int | `10` | 最大对话轮数 |
| `--api-key` | string | — | LLM API Key |

**示例**：

```bash
# 默认模型对话
kasaya chat

# 指定模型
kasaya chat --model claude-sonnet-4-20250514

# 自定义 Agent 角色
kasaya chat --instructions "你是一个 Python 专家，擅长 FastAPI 和 SQLAlchemy"

# 限制轮数
kasaya chat --max-turns 5
```

**内置命令**（对话中使用）：

| 命令 | 说明 |
|------|------|
| `exit` / `quit` | 退出对话 |
| `clear` | 清屏 |
| `Ctrl+C` | 中断当前输出 |

**输出格式**：使用 Rich Live 流式渲染，支持 Markdown 格式化显示。

---

### 4.2 `kasaya login` — 登录认证

```bash
kasaya login [OPTIONS]
```

**参数**：

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `--url` | string | `http://localhost:8000` | Kasaya 后端地址 |

**流程**：

1. 提示输入用户名
2. 提示输入密码（不回显）
3. 调用 `POST /api/v1/auth/login` 获取 JWT Token
4. Token 保存到环境变量 `KASAYA_TOKEN`

**示例**：

```bash
# 登录本地后端
kasaya login

# 登录远程后端
kasaya login --url https://kasaya.example.com
```

---

### 4.3 `kasaya agent` — Agent 管理

#### 列出 Agent

```bash
kasaya agent list [OPTIONS]
```

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `--limit` | int | `20` | 每页数量 |
| `--offset` | int | `0` | 起始偏移 |
| `--url` | string | — | 后端地址 |
| `--token` | string | — | JWT Token |

**输出**：Rich Table 格式

```
┌──────────────┬────────────────┬─────────────┬──────┬──────────────┐
│ ID           │ 名称           │ 模型         │ 状态 │ 创建时间      │
├──────────────┼────────────────┼─────────────┼──────┼──────────────┤
│ a1b2c3d4...  │ code-reviewer  │ gpt-4o      │ 启用 │ 2026-04-10   │
│ e5f6g7h8...  │ data-analyst   │ claude-3.5  │ 启用 │ 2026-04-12   │
└──────────────┴────────────────┴─────────────┴──────┴──────────────┘
```

#### 查看 Agent 详情

```bash
kasaya agent get <agent-id> [OPTIONS]
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `agent-id` | string | Agent 的 UUID |
| `--url` | string | 后端地址 |
| `--token` | string | JWT Token |

---

### 4.4 `kasaya provider` — Provider 管理

#### 列出厂商

```bash
kasaya provider list [OPTIONS]
```

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `--limit` | int | `20` | 每页数量 |
| `--url` | string | — | 后端地址 |
| `--token` | string | — | JWT Token |

**输出**：

```
┌──────────────┬──────────┬────────┬──────┬───────────────────────┐
│ ID           │ 名称     │ 类型   │ 状态 │ Base URL               │
├──────────────┼──────────┼────────┼──────┼───────────────────────┤
│ p1q2r3s4...  │ OpenAI   │ openai │ 启用 │ https://api.openai.com │
│ t5u6v7w8...  │ Kimi     │ custom │ 启用 │ https://api.moonshot.. │
└──────────────┴──────────┴────────┴──────┴───────────────────────┘
```

#### 测试厂商连通性

```bash
kasaya provider test <provider-id> [OPTIONS]
```

**输出**：

```
✅ 连通性测试成功
├── 延迟：245ms
├── 模型：gpt-4o-mini
└── 响应：正常
```

或：

```
❌ 连通性测试失败
└── 错误：Connection refused (api.openai.com:443)
```

---

### 4.5 `kasaya run` — 运行 Agent

发送单条消息给指定 Agent，获取回复。

```bash
kasaya run <agent-id> "<message>" [OPTIONS]
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `agent-id` | string | Agent 的 UUID |
| `message` | string | 发送的消息内容 |
| `--url` | string | 后端地址 |
| `--token` | string | JWT Token |

**流程**：

1. 创建一个新 Session（`POST /api/v1/sessions`）
2. 发送消息（`POST /api/v1/sessions/{id}/messages`）
3. 轮询 Session 状态直到 Agent 回复完成
4. 输出 Agent 的最终回复

**示例**：

```bash
kasaya run a1b2c3d4 "帮我审查这段代码的安全性"
```

---

### 4.6 `kasaya version` — 版本信息

```bash
kasaya version
```

输出：

```
kasaya-cli v0.1.0
```

---

## 5. 配置

### 5.1 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `KASAYA_URL` | Kasaya 后端 API 地址 | `http://localhost:8000` |
| `KASAYA_TOKEN` | JWT 认证 Token | — |

### 5.2 优先级

命令行参数 > 环境变量 > 默认值

```bash
# 环境变量方式
export KASAYA_URL=https://kasaya.example.com
export KASAYA_TOKEN=eyJhbG...
kasaya agent list

# 命令行参数方式（覆盖环境变量）
kasaya agent list --url https://kasaya.example.com --token eyJhbG...
```

---

## 6. 典型使用场景

### 场景 1：日常 Agent 对话

```bash
# 登录
kasaya login

# 使用 Claude 模型交互
kasaya chat --model claude-sonnet-4-20250514 --instructions "你是一个代码审查专家"
```

### 场景 2：CI/CD 中自动运行 Agent

```bash
# 在 CI 脚本中无交互运行
export KASAYA_TOKEN=$CI_KASAYA_TOKEN
kasaya run $AGENT_ID "请审查最新的 PR 变更"
```

### 场景 3：快速测试 Provider 配置

```bash
# 查看所有 Provider
kasaya provider list

# 测试某个 Provider 的连通性
kasaya provider test p1q2r3s4-xxxx-xxxx-xxxx-xxxxxxxxxxxx
```

---

## 7. 帮助

```bash
kasaya --help           # 全局帮助
kasaya chat --help      # chat 命令帮助
kasaya agent --help     # agent 子命令帮助
kasaya provider --help  # provider 子命令帮助
```

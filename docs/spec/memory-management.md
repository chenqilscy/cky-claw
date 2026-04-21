# Kasaya 记忆管理功能文档

> 版本：v1.0
> 日期：2026-04-15

## 1. 功能定位

**记忆管理**（Memory Management）是 Kasaya 平台的核心能力之一，让 AI Agent 能够在多轮对话和多次运行之间积累并利用"经验"。

核心价值：
- **Agent 不再"健忘"**：跨会话记住用户偏好、历史决策、过往经验
- **越用越懂你**：自动从对话中提取关键信息存储为记忆
- **有选择地遗忘**：通过衰减机制，旧的、不再相关的记忆自然淡化

---

## 2. 记忆类型

Kasaya 支持三种记忆类型：

| 类型 | 标识 | 说明 | 示例 |
|------|------|------|------|
| **用户档案** | `user_profile` | 用户的偏好、习惯和个人信息 | "用户偏好使用 Python + FastAPI 技术栈" |
| **历史摘要** | `history_summary` | 长对话的自动压缩摘要 | "用户在 3 月 15 日讨论了数据库迁移方案" |
| **结构化事实** | `structured_fact` | Agent 执行中积累的明确数据 | "项目使用 PostgreSQL 16 + Redis 7" |

---

## 3. 记忆数据模型

每条记忆包含以下信息：

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | UUID | 记忆唯一标识 |
| `user_id` | string | 用户隔离标识 |
| `type` | enum | 记忆类型（上述三种） |
| `content` | text | 记忆文本内容（1-10000 字符） |
| `confidence` | float | 置信度（0.0-1.0），表示记忆的可靠程度 |
| `agent_name` | string | 产生该记忆的 Agent 名称 |
| `source_session_id` | string | 来源会话 ID |
| `tags` | string[] | 分类标签（用于检索） |
| `metadata` | JSON | 自定义扩展信息 |
| `access_count` | int | 访问次数（热度排序 / LRU） |
| `embedding` | float[] | 向量表示（供语义检索使用，可选） |
| `created_at` | datetime | 创建时间 |
| `updated_at` | datetime | 最后更新时间 |

---

## 4. 方案架构

记忆系统分布在三个层：

```
┌─────────────────────────────────────────────────────────┐
│                    Frontend (React)                       │
│  MemoryPage: 列表/搜索/创建/编辑/删除/衰减               │
└──────────────────────┬──────────────────────────────────┘
                       │ REST API
┌──────────────────────▼──────────────────────────────────┐
│                    Backend (FastAPI)                      │
│  memories API: 10 个端点                                  │
│  memory_service: CRUD + 搜索 + 衰减                      │
│  MemoryEntry ORM → PostgreSQL memory_entries 表           │
└──────────────────────┬──────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────┐
│              Framework (kasaya)                │
│  MemoryBackend ABC → InMemory / Postgres 两种实现         │
│  MemoryExtractionHook: 运行结束后自动提取记忆              │
│  MemoryRetriever: 检索相关记忆并注入 Agent 上下文          │
└─────────────────────────────────────────────────────────┘
```

---

## 5. 核心机制

### 5.1 记忆存储与检索

**存储**：记忆通过以下三种方式产生：

1. **手动创建**：管理员在 MemoryPage 手动添加（适用于预置知识）
2. **自动提取**（MemoryExtractionHook）：Agent 运行结束后，Hook 自动分析输出，提取有价值的信息存为记忆
3. **API 创建**：外部系统通过 REST API 写入记忆

**检索**：

1. **关键词搜索**：`POST /api/v1/memories/search` — 按内容关键词模糊匹配
2. **标签搜索**：`POST /api/v1/memories/search-by-tags` — 按标签 OR 匹配
3. **列表过滤**：`GET /api/v1/memories` — 按类型、用户、Agent 筛选

### 5.2 记忆注入 Agent 上下文

`MemoryRetriever` 在 Agent 运行之前从后端检索相关记忆，格式化后注入 System Message：

```
## 用户记忆

以下是关于当前用户的历史记忆，请据此提供更精准的服务：

- [用户档案] 用户偏好使用 Python + FastAPI 技术栈（置信度: 0.95）
- [结构化事实] 项目数据库为 PostgreSQL 16（置信度: 0.90）
- [历史摘要] 用户在上次对话中讨论了 Docker 部署方案（置信度: 0.75）
```

注入规则：
- 过滤低置信度记忆（默认阈值 0.3）
- 按置信度 × 访问热度排序
- 受 Token 预算限制（不会无限注入）

### 5.3 记忆置信度衰减

随着时间推移，旧记忆的置信度会自然降低，模拟"遗忘"效果：

**线性衰减**（LINEAR）：

$$\text{new\_confidence} = \max(0, \text{confidence} - \text{rate})$$

**指数衰减**（EXPONENTIAL）— 艾宾浩斯遗忘曲线：

$$\text{new\_confidence} = \text{confidence} \times e^{-\lambda \times \text{days}}$$

其中 $\lambda$ 为衰减系数，$\text{days}$ 为记忆创建至今的天数。

**触发方式**：
- 手动触发：`POST /api/v1/memories/decay`，指定时间阈值 + 衰减参数
- 定时任务：可配置 SchedulerEngine 定期执行

---

## 6. 用户使用指南

### 6.1 通过 Web UI 管理记忆

**访问路径**：侧边栏 → 知识与记忆 → 记忆管理

#### 查看记忆列表

打开记忆管理页面，可以看到所有记忆条目的表格：

| 列 | 说明 |
|----|------|
| 类型 | 标签显示：用户档案（蓝色）/ 历史摘要（绿色）/ 结构化事实（金色） |
| 内容 | 记忆文本内容的截断预览 |
| 置信度 | 进度条显示（≥0.7 绿色 / 0.4-0.7 橙色 / <0.4 红色） |
| 用户 | 记忆所属用户 |
| Agent | 产生该记忆的 Agent |
| 创建时间 | 记忆创建时间 |
| 操作 | 编辑 / 删除 |

支持按类型、用户、Agent 筛选。

#### 创建记忆

1. 点击"新建记忆"按钮
2. 填写表单：
   - **记忆类型**：选择 用户档案 / 历史摘要 / 结构化事实
   - **用户 ID**：指定记忆归属的用户
   - **内容**：输入记忆文本（1-10000 字符）
   - **置信度**：设置初始置信度（默认 1.0）
   - **标签**：添加分类标签（可选）
   - **Agent 名称**：关联的 Agent（可选）
3. 点击"确定"保存

#### 编辑记忆

1. 在列表中找到目标记忆，点击"编辑"按钮
2. 修改内容、置信度或其他字段
3. 点击"确定"保存

#### 触发衰减

1. 在页面工具栏找到"衰减"按钮
2. 设置参数：
   - **时间阈值**：衰减多久之前的记忆
   - **衰减速率**：每次衰减的幅度
   - **衰减模式**：线性 / 指数
3. 点击执行

### 6.2 通过 REST API 使用

#### 创建记忆

```bash
POST /api/v1/memories
Content-Type: application/json

{
  "type": "user_profile",
  "content": "用户偏好使用 Python 技术栈",
  "confidence": 0.95,
  "user_id": "user-001",
  "agent_name": "code-assistant",
  "tags": ["preference", "tech-stack"]
}
```

#### 搜索记忆

```bash
POST /api/v1/memories/search
Content-Type: application/json

{
  "user_id": "user-001",
  "query": "Python 技术栈",
  "limit": 10
}
```

#### 按标签搜索

```bash
POST /api/v1/memories/search-by-tags
Content-Type: application/json

{
  "user_id": "user-001",
  "tags": ["preference"],
  "limit": 10
}
```

#### 触发衰减

```bash
POST /api/v1/memories/decay
Content-Type: application/json

{
  "before": "2026-04-01T00:00:00Z",
  "rate": 0.05,
  "mode": "exponential"
}
```

#### 删除用户全部记忆（GDPR 合规）

```bash
DELETE /api/v1/memories/user/{user_id}
```

### 6.3 Agent 自动记忆

当 Agent 配置了 `MemoryExtractionHook` 后，每次对话结束时会自动：

1. 分析 Agent 的输出内容
2. 提取有价值的信息（用户偏好、事实、决策等）
3. 创建为对应类型的记忆条目
4. 下次对话时，`MemoryRetriever` 注入相关记忆到 Agent 上下文

用户无需手动操作，Agent 会自动越来越了解用户。

---

## 7. API 端点汇总

| 端点 | 方法 | 功能 |
|------|------|------|
| `/api/v1/memories` | GET | 列出记忆（支持 user_id/type/agent_name 筛选） |
| `/api/v1/memories` | POST | 创建记忆 |
| `/api/v1/memories/{id}` | GET | 获取单条记忆详情 |
| `/api/v1/memories/{id}` | PUT | 更新记忆 |
| `/api/v1/memories/{id}` | DELETE | 删除记忆 |
| `/api/v1/memories/user/{user_id}` | DELETE | 删除用户全部记忆（GDPR） |
| `/api/v1/memories/search` | POST | 关键词搜索 |
| `/api/v1/memories/search-by-tags` | POST | 标签搜索 |
| `/api/v1/memories/count/{user_id}` | GET | 统计用户记忆数量 |
| `/api/v1/memories/decay` | POST | 批量衰减置信度 |

---

## 8. 与其他模块的关系

| 关联模块 | 关系 |
|----------|------|
| **Session** | `source_session_id` 关联来源对话 |
| **Agent** | `agent_name` 标识产生记忆的 Agent |
| **Context Engineering (S1)** | MemoryRetriever 是 ContextSource 之一 |
| **Compliance (N6)** | `delete_by_user` 支持 Right-to-Erasure 合规 |
| **Runner** | 通过 MemoryExtractionHook + MemoryRetriever 全自动闭环 |

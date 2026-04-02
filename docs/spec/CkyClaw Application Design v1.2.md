# CkyClaw 应用层技术设计方案 v1.2

## 文档信息

| 字段 | 内容 |
|------|------|
| 版本 | v1.2.0 |
| 日期 | 2026-04-02 |
| 状态 | 进行中 |
| 维护人 | CkyClaw Team |
| 依赖 | CkyClaw PRD v2.0、CkyClaw Framework Design v2.0 |

---

## 定位说明

本文档描述 **CkyClaw 应用层**的技术设计，覆盖 PRD 中框架层之上的企业级功能：

| 层级 | 文档 | 职责 |
|------|------|------|
| CkyClaw Framework | 《CkyClaw Framework Design v2.0》 | Agent 运行时库（Agent/Runner/Tool/Session/Tracing…） |
| **CkyClaw 应用层** | **本文档** | Web UI、IM 渠道、APM 仪表盘、监督面板等业务功能 |
| PRD 总纲 | 《CkyClaw PRD v2.0》 | 产品需求定义 |

---

## 一、IM 渠道详细设计

### 1.1 架构概览

IM 渠道系统采用 **Channel Adapter + MessageBus** 模式，将外部渠道协议差异封装在 Adapter 内部，内部统一使用标准消息格式。

```
                     外部渠道
    ─────────────────────────────────
    │  Telegram  │  Slack  │ 飞书  │  Web │  自定义  │
    └─────┬──────┘─────┬───┘───┬───┘───┬──┘────┬─────┘
          │            │       │       │       │
    ┌─────▼──────┐ ┌───▼───┐ ┌▼───┐ ┌─▼──┐ ┌──▼──────┐
    │ Telegram   │ │ Slack │ │Lark│ │Web │ │ Custom  │
    │ Adapter    │ │Adapter│ │Adpt│ │Adpt│ │ Adapter │
    └─────┬──────┘ └───┬───┘ └┬───┘ └─┬──┘ └──┬──────┘
          └────────────┴──────┴───────┴───────┘
                           │
                   ┌───────▼─────────┐
                   │   MessageBus    │  ← Redis Streams
                   └───────┬─────────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
     ┌────────────┐ ┌──────────┐ ┌───────────┐
     │ Session    │ │ Channel  │ │ Delivery  │
     │ Router     │ │ Manager  │ │ Tracker   │
     └─────┬──────┘ └──────────┘ └───────────┘
           │
           ▼
    CkyClaw Framework Runner
```

### 1.2 核心组件

#### 1.2.1 ChannelAdapter 接口

每个 IM 渠道实现统一的 `ChannelAdapter` 接口：

| 方法 | 说明 |
|------|------|
| `start()` | 启动渠道监听（长轮询 / WebSocket / Webhook Server） |
| `stop()` | 优雅关闭 |
| `send(channel_user_id, outbound_msg)` | 向渠道用户发送消息 |
| `health_check() → bool` | 渠道连通性检查 |
| `parse_inbound(raw) → InboundMessage` | 将渠道原始消息转为标准格式 |
| `format_outbound(outbound_msg) → raw` | 将标准输出转为渠道原生格式 |

#### 1.2.2 标准消息格式

```python
@dataclass
class InboundMessage:
    channel: str              # "telegram" | "slack" | "lark" | "web" | ...
    channel_user_id: str      # 渠道内的用户唯一标识
    channel_chat_id: str      # 渠道内的会话标识（群 / 私聊）
    text: str                 # 纯文本内容
    attachments: list[Attachment]  # 附件（图片、文件）
    metadata: dict            # 渠道特定元数据（message_id、thread_id…）
    timestamp: datetime

@dataclass
class OutboundMessage:
    text: str                 # Markdown 格式回复
    attachments: list[Attachment]
    stream_chunks: list[str] | None  # 流式分段（仅 Web/SSE）
    metadata: dict
```

#### 1.2.3 MessageBus

基于 **Redis Streams** 的异步消息总线，解耦渠道 I/O 与 Agent 执行：

| 配置 | 说明 |
|------|------|
| Stream Key | `channel:{channel}:inbound`、`channel:{channel}:outbound` |
| Consumer Group | `ckyclaw-workers`（支持多实例消费） |
| 消息保留 | 7 天（`MAXLEN ~100000`） |
| 确认模式 | 处理完成后 `XACK`，失败回到 Pending |
| 死信 | 3 次重试失败 → `channel:dead-letter` |

### 1.3 渠道实现规范

| 渠道 | 传输协议 | 接收方式 | 流式输出 | 特殊处理 |
|------|---------|---------|---------|---------|
| **Web** | HTTP SSE + REST | 直接 HTTP 请求 | SSE 逐 Token | 无需 Adapter（直连 API） |
| **Telegram** | HTTPS | 长轮询（`getUpdates`） | 不支持；分段发送（每 500 字符或 3s 间隔） | Markdown → Telegram MarkdownV2 转义 |
| **Slack** | WebSocket | Socket Mode | 不支持；`chat.update` 增量追加 | Markdown → Slack mrkdwn（Block Kit） |
| **飞书/Lark** | HTTPS | 事件订阅回调 | 不支持；分段更新卡片消息 | Markdown → 飞书富文本 / 消息卡片 |
| **企业微信** | HTTPS | 回调接口 | 不支持；分段推送 | Markdown → 企微 Markdown（子集） |
| **自定义** | 用户实现 | 用户实现 | 用户实现 | 继承 `ChannelAdapter` 基类 |

### 1.4 Session 映射

IM 消息到达后，SessionRouter 按以下规则映射到 CkyClaw Framework Session：

```
映射键 = channel + ":" + channel_chat_id + ":" + agent_name

查找流程:
1. 查 Redis 缓存 channel_session_map:{映射键} → session_id
2. 命中 → 加载 Session
3. 未命中 → 查 PostgreSQL channel_sessions 表
4. 仍无 → 自动创建新 Session，写回缓存

特殊规则:
- Telegram 群组: channel_chat_id = group_id（群内所有用户共享一个 Session）
- Telegram 私聊: channel_chat_id = user_id
- Slack: channel_chat_id = channel_id + ":" + thread_ts（线程级隔离）
- 超时重建: Session 超过 idle_timeout（默认 24h）自动关闭，下次消息创建新 Session
```

**channel_sessions 表：**

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| channel | VARCHAR(32) | 渠道类型 |
| channel_chat_id | VARCHAR(256) | 渠道会话 ID |
| agent_name | VARCHAR(128) | 关联的 Agent |
| session_id | UUID | FK → Session |
| user_id | UUID | FK → User（渠道用户绑定后） |
| created_at | TIMESTAMP | 创建时间 |
| last_active_at | TIMESTAMP | 最后活跃时间 |

索引：`UNIQUE(channel, channel_chat_id, agent_name)`

### 1.5 消息格式转换

Agent 输出为 Markdown。各渠道 Adapter 执行以下转换：

| Markdown 语法 | Telegram | Slack | 飞书 |
|--------------|----------|-------|------|
| `**bold**` | `*bold*` | `*bold*` | `<b>bold</b>` |
| `` `code` `` | `` `code` `` | `` `code` `` | `<code>code</code>` |
| ` ```block``` ` | ` ```block``` ` | ` ```block``` ` | 代码块卡片 |
| `[text](url)` | `[text](url)` | `<url\|text>` | `<a href="url">text</a>` |
| `- item` | `- item` | `• item` | 无序列表标签 |
| 表格 | 转文本对齐 | 不支持 → 转代码块 | 表格卡片 |

### 1.6 非流式渠道的长消息处理

IM 渠道对单条消息有长度限制，且不支持服务端 SSE。采用 **分段推送** 策略：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `segment_max_chars` | 500 | 单段最大字符数 |
| `segment_interval_sec` | 3.0 | 两段之间最小间隔 |
| `typing_indicator` | true | 分段间发送「正在输入」状态 |
| `merge_final` | true | Agent 执行结束后，将分段合并为一条完整消息（Slack `chat.update`/ 飞书卡片更新） |

流程：Runner 产生流式 Token → Channel Outbound Handler 缓冲 → 达到 `segment_max_chars` 或 Agent 结束 → 调用 `adapter.send()` 发出一段 → 循环。

### 1.7 渠道健康检查与重连

| 机制 | 说明 |
|------|------|
| 定时心跳 | ChannelManager 每 60 秒调用 `adapter.health_check()` |
| 自动重启 | 连续 3 次心跳失败 → 调用 `adapter.stop()` + `adapter.start()` |
| 退避重试 | 重启失败 → 指数退避（30s / 60s / 120s / 300s max） |
| 告警 | 渠道 down > 5 分钟 → 发送告警（APM 告警通道） |
| 状态展示 | ChannelConfig.status 字段反映实时状态（running / degraded / down） |

### 1.8 渠道用户绑定

IM 用户首次交互时，需要与 CkyClaw 用户身份关联：

| 步骤 | 说明 |
|------|------|
| 1. 首次消息 | Adapter 解析出 channel_user_id |
| 2. 查绑定表 | `channel_user_bindings` 是否有 (channel, channel_user_id) 记录 |
| 3a. 已绑定 | 直接获取 user_id，附加到 RunContext |
| 3b. 未绑定 | 回复引导消息："请输入 `/bind <token>` 绑定您的 CkyClaw 账号" |
| 4. 绑定 | 用户在 CkyClaw Web 端生成一次性 bind token → 在 IM 中输入 `/bind <token>` → 写入绑定表 |
| 5. 匿名访问 | 可配置允许匿名访问（不绑定也可对话，但不可审计到具体用户） |

---

## 二、前端 UI 详细设计

### 2.1 技术栈确认

| 维度 | 方案 | 理由 |
|------|------|------|
| 框架 | React 18+ | 生态成熟、团队熟悉 |
| 构建 | Vite 5 | 开发体验好、ESBuild 快速编译 |
| 组件库 | Ant Design 5 | 企业后台组件齐全 |
| 状态管理 | Zustand | 轻量、无模板代码、TS 友好 |
| 路由 | React Router 6 | 标准选型 |
| 实时通信 | EventSource (SSE) + WebSocket | SSE → 对话流式；WS → 监督面板 |
| 图表 | ECharts 5 | APM/Token 审计图表 |
| DAG 可视化 | ReactFlow | 执行流程图渲染 |
| HTTP 客户端 | ky / axios | API 封装 |
| 国际化 | react-i18next | 中英文切换 |

### 2.2 项目结构

```
frontend/
├── public/
├── src/
│   ├── main.tsx                      # 入口
│   ├── App.tsx                       # 根组件（MainLayout + Router）
│   │
│   ├── layouts/
│   │   ├── MainLayout.tsx            # 侧边栏 + 顶栏 + 内容区
│   │   └── AuthLayout.tsx            # 登录/注册布局
│   │
│   ├── pages/                        # 页面组件（与路由一一对应）
│   │   ├── chat/                     # 对话页
│   │   │   ├── ChatPage.tsx
│   │   │   ├── ChatSidebar.tsx       # 历史对话列表
│   │   │   └── ChatWindow.tsx        # 对话主窗口
│   │   ├── agents/                   # Agent 管理
│   │   │   ├── AgentListPage.tsx
│   │   │   └── AgentEditPage.tsx
│   │   ├── executions/               # 执行监控
│   │   │   ├── ExecutionListPage.tsx
│   │   │   └── ExecutionDetailPage.tsx
│   │   ├── supervision/              # 监督中心
│   │   │   ├── SupervisionPage.tsx
│   │   │   └── ApprovalQueuePage.tsx
│   │   ├── apm/                      # APM 仪表盘
│   │   │   ├── DashboardPage.tsx
│   │   │   ├── TracePage.tsx
│   │   │   ├── AlertPage.tsx
│   │   │   └── TokenAuditPage.tsx
│   │   ├── settings/                 # 系统设置
│   │   │   ├── ProviderPage.tsx
│   │   │   ├── UserPage.tsx
│   │   │   └── ChannelPage.tsx
│   │   └── auth/
│   │       └── LoginPage.tsx
│   │
│   ├── components/                   # 通用组件
│   │   ├── chat/
│   │   │   ├── MessageList.tsx       # 消息列表（虚拟滚动）
│   │   │   ├── MessageBubble.tsx     # 单条消息气泡
│   │   │   ├── StreamingText.tsx     # 流式文本渲染
│   │   │   ├── ToolCallCard.tsx      # 工具调用展示卡片
│   │   │   └── HandoffIndicator.tsx  # Handoff 事件标记
│   │   ├── execution/
│   │   │   ├── TraceGraph.tsx        # 执行流程图（ReactFlow）
│   │   │   ├── SpanDetail.tsx        # Span 详情面板
│   │   │   └── SpanTimeline.tsx      # Span 瀑布图
│   │   ├── apm/
│   │   │   ├── MetricCard.tsx        # 指标卡片
│   │   │   ├── TrendChart.tsx        # 趋势折线图
│   │   │   ├── BreakdownChart.tsx    # 分布饼图/柱状图
│   │   │   └── AlertRuleForm.tsx     # 告警规则表单
│   │   └── common/
│   │       ├── MarkdownRenderer.tsx  # Markdown 渲染
│   │       ├── JsonViewer.tsx        # JSON 展示
│   │       └── TimeRange.tsx         # 时间范围选择器
│   │
│   ├── stores/                       # Zustand 状态管理
│   │   ├── authStore.ts              # 认证状态
│   │   ├── chatStore.ts              # 对话状态（当前会话、消息列表）
│   │   ├── agentStore.ts             # Agent 列表、当前编辑
│   │   ├── supervisionStore.ts       # 监督面板状态
│   │   └── apmStore.ts              # APM 数据
│   │
│   ├── services/                     # API 封装
│   │   ├── api.ts                    # 基础 HTTP 客户端（拦截器、认证头）
│   │   ├── agentService.ts
│   │   ├── chatService.ts
│   │   ├── executionService.ts
│   │   ├── supervisionService.ts
│   │   ├── apmService.ts
│   │   └── tokenAuditService.ts
│   │
│   ├── hooks/                        # 自定义 Hooks
│   │   ├── useSSE.ts                 # SSE 流式连接
│   │   ├── useWebSocket.ts           # WebSocket 连接
│   │   └── useAuth.ts               # 认证守卫
│   │
│   ├── utils/
│   │   ├── formatters.ts             # 日期、Token 数格式化
│   │   └── constants.ts
│   │
│   └── styles/
│       └── theme.ts                  # Ant Design 主题定制
│
├── index.html
├── vite.config.ts
├── tsconfig.json
└── package.json
```

### 2.3 路由表

| 路由 | 页面 | 权限 |
|------|------|------|
| `/login` | LoginPage | 公开 |
| `/chat` | ChatPage | User+ |
| `/chat/:sessionId` | ChatPage（指定会话） | User+ |
| `/agents` | AgentListPage | Developer+ |
| `/agents/new` | AgentEditPage | Developer+ |
| `/agents/:name/edit` | AgentEditPage | Developer+ |
| `/executions` | ExecutionListPage | Developer+ |
| `/executions/:runId` | ExecutionDetailPage | Developer+ |
| `/supervision` | SupervisionPage | Operator+ |
| `/supervision/approvals` | ApprovalQueuePage | Operator+ |
| `/apm` | DashboardPage | Operator+ |
| `/apm/traces` | TracePage | Operator+ |
| `/apm/traces/:traceId` | TracePage（详情） | Operator+ |
| `/apm/alerts` | AlertPage | Operator+ |
| `/apm/token-audit` | TokenAuditPage | Operator+ |
| `/teams` | TeamListPage | Developer+ |
| `/teams/new` | TeamEditPage | Developer+ |
| `/teams/:name/edit` | TeamEditPage | Developer+ |
| `/scheduled-runs` | ScheduledRunListPage | Developer+ |
| `/batch-runs` | BatchRunListPage | Developer+ |
| `/apm/evaluation` | AgentEvaluationPage | Operator+ |
| `/settings/providers` | ProviderPage | Admin |
| `/settings/users` | UserPage | Admin |
| `/settings/channels` | ChannelPage | Admin |
| `/settings/config` | ConfigChangePage | Admin |
| `/settings/i18n` | I18nSettingsPage | Admin |

### 2.4 对话界面设计

#### 2.4.1 布局

```
┌──────────────────────────────────────────────────────────────────┐
│ TopBar: 登录用户 | 通知铃铛 | 设置                                │
├──────────┬──────────────────────────────────────┬────────────────┤
│ Sidebar  │          ChatWindow                  │  DetailPanel   │
│          │                                      │  (可折叠)      │
│ Agent选择│  ┌──────────────────────────────┐    │                │
│          │  │ MessageList (虚拟滚动)       │    │ Span 详情      │
│ 历史对话 │  │                              │    │ 工具调用详情   │
│ 列表     │  │ ├ User: 你好                 │    │ Handoff 历史   │
│          │  │ ├ Agent: [streaming...]       │    │ Token 统计     │
│          │  │ ├ [ToolCallCard: web_search]  │    │                │
│          │  │ └ [HandoffIndicator]          │    │                │
│ 新建对话 │  │                              │    │                │
│          │  └──────────────────────────────┘    │                │
│          │  ┌──────────────────────────────┐    │                │
│          │  │ InputBar: 文本输入 + 发送    │    │                │
│          │  │ 附件上传 | 快捷命令          │    │                │
│          │  └──────────────────────────────┘    │                │
└──────────┴──────────────────────────────────────┴────────────────┘
```

#### 2.4.2 SSE 流式渲染

```
前端 SSE 事件流处理:

EventSource 连接: GET /api/v1/sessions/{id}/run?stream=true

事件类型        →  前端处理
─────────────────────────────────────────
agent_start     →  显示 Agent 名称 + "思考中" 图标
text_delta      →  追加文本到 StreamingText 组件（16ms 批量刷新）
tool_call_start →  插入 ToolCallCard（状态: calling）
tool_call_end   →  更新 ToolCallCard（状态: done + 结果摘要）
handoff         →  插入 HandoffIndicator（A → B）
agent_end       →  移除 "思考中" 图标
run_end         →  标记对话结束，启用输入框
error           →  显示错误提示，提供重试按钮
```

**性能优化：**

| 策略 | 说明 |
|------|------|
| 批量 DOM 更新 | 使用 `requestAnimationFrame` 合并 16ms 内的 text_delta |
| 虚拟滚动 | MessageList 使用 `react-virtuoso`，仅渲染可视区域消息 |
| 懒加载附件 | 图片/文件仅在进入视口时加载 |
| 消息缓存 | 已加载的历史消息缓存在 chatStore，切换会话不重复请求 |

#### 2.4.3 工具调用展示

ToolCallCard 组件展示 Agent 的工具调用过程：

```
┌─────────────────────────────────────────────┐
│ 🔧 web_search                    ✅ 成功    │
│ ─────────────────────────────────────────── │
│ 查询: "CkyClaw Framework 最新版本"          │
│ 耗时: 1.2s                                 │
│ [展开查看详情 ▼]                            │
│   参数: {"query": "...", "max_results": 5}  │
│   结果: [{"title": "...", "url": "..."}]    │
└─────────────────────────────────────────────┘
```

### 2.5 执行流程图设计

#### 2.5.1 Trace → ReactFlow 映射

将后端返回的 Trace/Span 数据映射为 ReactFlow 的节点和边：

| Span 类型 | ReactFlow 节点样式 | 说明 |
|-----------|-------------------|------|
| `agent` | 蓝色圆角矩形 | 显示 Agent 名称 + 状态 + 耗时 |
| `llm` | 紫色椭圆 | 显示模型名称 + Token 数 |
| `tool` | 绿色矩形 | 显示工具名称 + 耗时 + 状态 |
| `handoff` | 橙色箭头连接 | 从源 Agent → 目标 Agent |
| `guardrail` | 红色菱形 | 显示护栏名称 + 通过/拦截 |

映射规则：
- 每个 Span 对应一个节点
- `parent_span_id` 关系转为从父到子的有向边
- Handoff Span 额外生成一条跨 Agent 的水平边
- 节点 Y 轴按 `start_time` 排列（时间流从上到下）

#### 2.5.2 实时更新

执行过程中，流程图通过 SSE 事件增量更新：

| 事件 | 图更新 |
|------|--------|
| `agent_start` | 新增 Agent 节点（脉冲动画表示执行中） |
| `tool_call_start` | 新增 Tool 节点 + 连接边（loading 动画） |
| `tool_call_end` | 更新 Tool 节点状态（✅ / ❌） |
| `handoff` | 新增 Handoff 边 + 新 Agent 节点 |
| `run_end` | 所有节点停止动画 |

### 2.6 监督面板设计

#### 2.6.1 布局

```
┌──────────────────────────────────────────────────────────────────┐
│ 监督中心                                        筛选: Agent ▼   │
├───────────────────┬──────────────────────────────────────────────┤
│ 活跃会话列表      │  实时对话流                                   │
│                   │                                              │
│ ● user-1 / triage│  User: 帮我分析一下这个数据                   │
│   Agent: triage   │  Agent: 好的，我来调用数据分析工具…            │
│   运行: 45s       │  [ToolCallCard: query_database]               │
│                   │  [⚠️ 审批请求: 写入操作 write_file]           │
│ ○ user-2 / sales │  ┌──────────────────────────────┐            │
│   Agent: sales    │  │ 审批: 确认执行 write_file？  │            │
│   空闲            │  │ 参数: {"path": "/tmp/..."}   │            │
│                   │  │ [✅ 批准]  [❌ 拒绝]  [📝 修改] │          │
│                   │  └──────────────────────────────┘            │
│                   ├──────────────────────────────────────────────┤
│                   │  操作栏:                                      │
│                   │  [⏸ 暂停] [📝 注入消息] [🔄 接管] [📊 Trace] │
└───────────────────┴──────────────────────────────────────────────┘
```

#### 2.6.2 WebSocket 事件

监督面板通过 WebSocket 接收实时事件：

| WebSocket 事件 | 说明 |
|---------------|------|
| `session_active` | 新会话开始 |
| `session_end` | 会话结束 |
| `message` | 新消息（用户输入 / Agent 输出） |
| `tool_call` | 工具调用（含参数和结果） |
| `handoff` | Handoff 事件 |
| `approval_request` | 新审批请求 |
| `approval_resolved` | 审批已处理 |
| `session_paused` | 会话被暂停 |
| `session_resumed` | 会话被恢复 |
| `session_taken_over` | 会话被接管 |

连接地址：`ws://{host}/api/v1/supervision/ws?token={jwt}`

### 2.7 主题与响应式

| 维度 | 方案 |
|------|------|
| 主题 | Ant Design ConfigProvider 定制主色调；支持亮色/暗色模式切换 |
| 响应式 | 最小支持宽度 1280px（企业后台场景），不优先移动端 |
| 国际化 | 默认中文，react-i18next 管理翻译 key；首版仅中英两种 |
| 无障碍 | 遵循 WCAG 2.1 AA 级（颜色对比度 4.5:1、键盘可操作） |

---

## 三、APM 仪表盘详细设计

### 3.1 仪表盘架构

```
┌────────────────────────────────────────────────────┐
│                  APM Dashboard                      │
│                                                     │
│  ┌───────────┐  ┌────────────┐  ┌──────────────┐  │
│  │ Overview  │  │ Trace View │  │ Alert Center │  │
│  │ 指标卡片  │  │ 链路追踪   │  │ 告警管理     │  │
│  │ 趋势图    │  │ 瀑布图     │  │ 规则配置     │  │
│  │ 排名表    │  │ Span 详情  │  │ 告警历史     │  │
│  └─────┬─────┘  └─────┬──────┘  └──────┬───────┘  │
│        └──────────────┼─────────────────┘          │
│                       │                             │
│              ┌────────▼────────┐                    │
│              │  APM Service    │  ← 后端查询层      │
│              └────────┬────────┘                    │
│                       │                             │
│           ┌───────────┼───────────┐                 │
│           ▼           ▼           ▼                 │
│     Jaeger/Tempo  PostgreSQL    Redis               │
│    (Trace/Span)   (AlertRule    (实时指标缓存)      │
│     + Prometheus    +TokenAudit)                     │
└────────────────────────────────────────────────────┘
```

### 3.2 仪表盘页面模块

#### 3.2.1 概览页（DashboardPage）

```
┌──────────────────────────────────────────────────────────────────┐
│                    时间范围: [最近1小时 ▼]  [自动刷新: 30s ▼]     │
├──────────┬──────────┬──────────┬──────────┬──────────────────────┤
│ 活跃 Run │ 成功率   │ P95 延迟 │ 当日成本 │ Token 消耗           │
│   12     │  97.3%   │  4.2s    │ $23.50   │ 1.2M tokens          │
├──────────┴──────────┴──────────┴──────────┴──────────────────────┤
│                                                                   │
│  ┌─ 任务趋势 ──────────────────┐  ┌─ 成本趋势 ───────────────┐  │
│  │  [折线图: 成功/失败/超时]    │  │  [折线图: 按厂商分色]     │  │
│  │  X: 时间  Y: 数量            │  │  X: 时间  Y: 金额(USD)    │  │
│  └──────────────────────────────┘  └───────────────────────────┘  │
│                                                                   │
│  ┌─ Agent 排名 ────────────────┐  ┌─ 活跃告警 ───────────────┐  │
│  │  Agent         调用  成功率  │  │  ⚠ 任务失败率 > 5%       │  │
│  │  triage          234   98%   │  │  ⚠ gpt-4o P95 > 3s       │  │
│  │  data-analyst     89   95%   │  │  🔴 MCP server-1 断连     │  │
│  │  code-executor    56   100%  │  │                           │  │
│  └──────────────────────────────┘  └───────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

#### 3.2.2 链路追踪页（TracePage）

| 组件 | 说明 |
|------|------|
| 搜索栏 | 按 trace_id / agent / 状态 / 时间范围 / 最小耗时筛选 |
| Trace 列表 | 表格展示：trace_id、Agent、状态、耗时、Span 数、Token、时间 |
| Span 瀑布图 | 选中 Trace 后展示 Span 时间线（横向瀑布图，颜色区分类型） |
| Span 详情 | 点击 Span 后展示：类型、名称、耗时、输入/输出、Token、错误信息 |

**瀑布图渲染规则：**

```
时间轴 ──────────────────────────────────────────────►

Agent: triage    ██████████████                        8.2s
  LLM: gpt-4o       ████████                           3.1s
  Handoff              ██                               0.1s
Agent: analyst              ████████████████████        5.0s
  LLM: gpt-4o                 ██████                    2.0s
  Tool: query_db                  ████████              2.1s
  Tool: gen_chart                          ████         1.5s
  LLM: gpt-4o                                  ████    0.8s

颜色: 🟦 Agent  🟪 LLM  🟩 Tool  🟧 Handoff  🟥 Error
```

### 3.3 告警引擎

#### 3.3.1 告警规则评估

```
告警引擎运行在后端，独立于前端：

┌──────────────────────────────────────────────┐
│                Alert Engine                   │
│                                              │
│  ┌────────────────┐    ┌─────────────────┐   │
│  │ Rule Evaluator │───►│ Alert Dispatcher│   │
│  │ (定时调度)     │    │                 │   │
│  └────────┬───────┘    └────────┬────────┘   │
│           │                     │            │
│    查询 Prometheus/         发送通知:          │
│    PostgreSQL             - WebSocket推送     │
│    评估指标阈值           - 邮件              │
│    比较持续时间           - Webhook           │
│                          - 站内消息           │
└──────────────────────────────────────────────┘
```

#### 3.3.2 评估周期

| 严重度 | 评估间隔 | 说明 |
|--------|---------|------|
| critical | 15 秒 | 高优先级规则实时评估 |
| warning | 60 秒 | 标准评估频率 |
| info | 300 秒 | 低优先级 |

#### 3.3.3 告警状态机

```
               触发条件满足
  inactive ──────────────────► firing
      ▲                           │
      │                           │ 持续时间满足
      │           恢复             ▼
      └────────────────────── pending
                                  │
                                  │ 持续 duration 后
                                  ▼
                               active ──► 发送通知
                                  │
                                  │ 恢复
                                  ▼
                               resolved ──► 发送恢复通知
```

#### 3.3.4 告警数据模型

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| rule_id | UUID | FK → AlertRule |
| status | ENUM | inactive / firing / pending / active / resolved |
| metric_type | VARCHAR | task / agent / tool / cost |
| metric_value | FLOAT | 触发时的指标值 |
| threshold | FLOAT | 告警阈值 |
| scope_type | VARCHAR | global / org / team / agent / tool |
| scope_id | VARCHAR | 作用域标识 |
| fired_at | TIMESTAMP | 触发时间 |
| resolved_at | TIMESTAMP | 恢复时间 |
| notification_sent | BOOLEAN | 是否已发送通知 |

### 3.4 成本控制引擎

#### 3.4.1 预算检查点

成本控制在 Agent 执行链路中设置**两个检查点**：

| 检查点 | 时机 | 检查内容 |
|--------|------|---------|
| **Pre-Run 检查** | `Runner.run()` 入口 | 用户/团队/组织当前累计消耗 vs 预算上限 |
| **Per-LLM 检查** | 每次 LLM 调用结束后 | 累加本次 Token 消耗，检查是否超过阈值 |

```
Pre-Run 检查流程:
1. 查 Redis 缓存: budget:{org_id}:{period} → {used, limit}
2. 缓存未命中 → 查 PostgreSQL 聚合当期消耗（或 ClickHouse，若启用）→ 回写 Redis（TTL 5 min）
3. used / limit >= 1.0 → 拒绝执行（BudgetExhaustedError）
4. used / limit >= 0.95 → 强制降级模型（RunConfig.model_override）
5. used / limit >= 0.80 → 标记 warning 级别预算告警

Per-LLM 检查:
1. LLM Span 结束 → 提取 token_usage
2. Redis INCRBY budget:{org_id}:{period} delta
3. 链路内累计 > 单次 Run 上限 → 终止当前 Run（RunBudgetExceededError）
```

#### 3.4.2 预算层级

| 层级 | Redis Key 模式 | 预算周期 | 默认值 |
|------|---------------|---------|--------|
| 组织级 | `budget:{org_id}:monthly:{YYYYMM}` | 月 | 无上限 |
| 团队级 | `budget:{org_id}:{team_id}:monthly:{YYYYMM}` | 月 | 继承组织 |
| 用户级 | `budget:{user_id}:daily:{YYYYMMDD}` | 日 | 100K tokens |
| 单次 Run | RunConfig.max_cost_usd / max_tokens | 单次 | 10K tokens |

#### 3.4.3 模型降级执行器

| 降级策略 | 说明 |
|---------|------|
| 同厂商降级 | gpt-4o → gpt-4o-mini（维护能力映射表） |
| 跨厂商降级 | gpt-4o → deepseek-chat（按能力等级匹配） |
| 禁止策略 | 管理员可标记特定 Agent 不允许降级（safety-critical 场景） |

降级映射表存储在 `model_downgrade_map` 配置：

| 原模型 | 降级模型 | 能力损失评估 |
|--------|---------|-------------|
| gpt-4o | gpt-4o-mini | 中等（复杂推理能力下降） |
| claude-3.5-sonnet | claude-3.5-haiku | 中等 |
| deepseek-v3 | deepseek-chat | 低 |

### 3.5 Token 审计页面设计

Token 审计页面为 APM 仪表盘的子页面，基于 PRD 9.5.5 节的视图组件：

```
┌──────────────────────────────────────────────────────────────────┐
│ Token 审计                 时间: [本月 ▼]  [导出 CSV]  [导出 Excel]│
├──────────┬──────────┬──────────┬──────────┬──────────────────────┤
│ 总Token  │ 总费用   │ 日均消耗 │ 活跃用户 │ 预算使用率           │
│ 1.2M     │ $156.30  │  40K/day │  23      │ ████████░░ 78%       │
├──────────┴──────────┴──────────┴──────────┴──────────────────────┤
│                                                                   │
│  ┌─ 消耗趋势 ──────────────────┐  ┌─ 维度分布 ───────────────┐  │
│  │ [折线图: 按日/周/月]         │  │ [饼图: 按 Agent]          │  │
│  │ 可切换: 总量/按 Agent/按模型 │  │ 切换: Agent/模型/厂商/团队│  │
│  └──────────────────────────────┘  └───────────────────────────┘  │
│                                                                   │
│  ┌─ Top-10 排名 ───────────────┐  ┌─ 审计日志 ───────────────┐  │
│  │ 维度: [用户 ▼]              │  │ 筛选: Agent / 模型 / 用户 │  │
│  │  1. 张三    245K   $32.10   │  │ 时间 | Agent | 模型 | ... │  │
│  │  2. 李四    189K   $24.70   │  │ 10:23 | triage | gpt-4o  │  │
│  │  ...                        │  │ 10:21 | analyst| gpt-4o  │  │
│  └──────────────────────────────┘  └───────────────────────────┘  │
│                                                                   │
│  ┌─ 预算进度 ──────────────────────────────────────────────────┐  │
│  │ 组织: CkyClaw     ████████████████░░░░ $156/$200 (78%)      │  │
│  │ 团队: 研发团队     ██████████░░░░░░░░░ $89/$150  (59%)      │  │
│  │ 团队: 运营团队     ████░░░░░░░░░░░░░░░ $42/$100  (42%)      │  │
│  └─────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

### 3.6 指标查询层

APM Service 根据部署配置自动选择查询后端：

| 部署模式 | Trace/Span 查询 | Token 统计 | Metrics 查询 |
|---------|-------------|---------|----------|
| **MVP（PostgreSQL）** | SQL 查询 `spans` 表 | SQL 查询 `token_usage_summary` | SQL 查询 `spans` 聚合 |
| **生产（OTel 栈）** | Jaeger/Tempo API | SQL 查询 PostgreSQL | PromQL 查询 Prometheus |
| **大规模（+ClickHouse）** | ClickHouse SQL | ClickHouse 物化视图 | PromQL 查询 Prometheus |

**PostgreSQL 查询模板（MVP 默认）：**

| 查询类型 | SQL 模板 | 缓存策略 |
|---------|-------|----------|
| 概览指标 | `SELECT count(*), avg(duration_ms), sum((token_usage->>'total_tokens')::int) FROM spans WHERE ...` | Redis 30s |
| 趋势数据 | `SELECT date_trunc('hour', created_at) as t, count(*) FROM spans GROUP BY t` | Redis 60s |
| Top-N | `SELECT agent_name, sum(total_tokens) FROM token_usage_log GROUP BY agent_name ORDER BY 2 DESC LIMIT $1` | Redis 60s |
| Trace 列表 | `SELECT * FROM spans WHERE parent_span_id IS NULL AND ... ORDER BY created_at DESC LIMIT $1 OFFSET $2` | 不缓存 |
| Span 详情 | `SELECT * FROM spans WHERE trace_id = $1 ORDER BY start_time` | 不缓存 |
| Token 统计 | 直接查询 `token_usage_summary` 表 | Redis 300s |

**Prometheus 查询模板（OTel 栈启用时）：**

| 查询类型 | PromQL 模板 |
|---------|-------------|
| 任务成功率 | `sum(rate(ckyclaw_run_total{status="completed"}[5m])) / sum(rate(ckyclaw_run_total[5m]))` |
| P95 延迟 | `histogram_quantile(0.95, sum(rate(ckyclaw_run_duration_bucket[5m])) by (le))` |
| Token 速率 | `sum(rate(ckyclaw_tokens_total[5m])) by (model)` |
| 成本趋势 | `sum(increase(ckyclaw_cost_usd_total[1h])) by (provider)` |

**查询安全：** 所有 SQL 查询使用参数化（PostgreSQL `$1` 占位符 / ClickHouse `{param:Type}` 语法），防止 SQL 注入。

---

## 四、通知系统设计

### 4.1 通知架构

```
事件源                  通知引擎                    通知渠道
────────              ──────────                  ──────────
审批请求   ─┐
告警触发   ─┤        ┌──────────────┐           ┌── 站内消息
执行完成   ─┼───────►│ Notification │──────────►├── 邮件 (SMTP)
系统事件   ─┤        │   Engine     │           ├── Webhook
配额预警   ─┘        └──────┬───────┘           └── IM 渠道回推
                            │
                     按用户偏好路由
                     按角色权限过滤
                     按频率限制去重
```

### 4.2 通知类型与渠道

| 通知类型 | 默认渠道 | 可配置渠道 | 频率限制 |
|---------|---------|-----------|---------|
| 审批请求 | 站内 + 邮件 | + Webhook + IM | 无限制（实时） |
| 告警（critical） | 站内 + 邮件 + Webhook | + IM | 同一规则 5 分钟去重 |
| 告警（warning） | 站内 | + 邮件 | 同一规则 15 分钟去重 |
| 执行完成 | 站内 | + 邮件 | 同一 Agent 1 分钟合并 |
| 预算预警 | 站内 + 邮件 | + Webhook | 每级别每天 1 次 |
| 系统通知 | 邮件 | — | 不重复 |

### 4.3 用户通知偏好

用户可在设置页自定义通知偏好：

| 设置项 | 说明 |
|--------|------|
| 邮件通知开关 | 全局启用/禁用邮件 |
| 审批通知方式 | 站内 / 邮件 / 两者 |
| 告警通知方式 | 按严重度分别配置 |
| 免打扰时段 | 设置时间段内仅保留站内消息 |
| Webhook URL | 个人 Webhook 地址（用于自建机器人） |

---

## 五、Agent Team 管理页面设计

### 5.1 Team 列表页（TeamListPage）

| 组件 | 说明 |
|------|------|
| Team 卡片列表 | 每张卡片展示：Team 名称、协议类型标签、成员数、描述、内置/自定义标识 |
| 协议筛选 | 按 Sequential / Parallel / Debate / RoundRobin / Broadcast 筛选 |
| 新建 Team | 按钮 → 跳转 TeamEditPage；或选择内置模板快速克隆 |
| 模板库入口 | 内置模板浏览区域，展示 6 个内置 Team（附协议图标和成员组成预览） |

### 5.2 Team 编辑页（TeamEditPage）

| 区域 | 说明 |
|------|------|
| 基本信息 | name、display_name、description |
| 协议选择 | 下拉选择协议类型；选择后动态展示该协议的配置项（如 debate 显示 max_rounds 和 Judge 选择） |
| 成员管理 | 从已注册 Agent 列表中选择成员、分配角色说明、拖拽排序（sequential 模式下顺序重要） |
| 终止条件 | max_rounds、timeout_seconds、consensus_threshold（按协议动态显示相关字段） |
| 结果策略 | last / concat / vote / judge / custom |
| 测试区域 | Playground 式测试——输入文本 → 执行 Team → 查看各成员 Agent 输出和最终结果 |

### 5.3 Team Trace 视图

在 APM Trace 详情页中，Team 执行展示为可展开的层级结构：
- Team Span 展示为一个父节点（标注协议类型和轮次数）
- 展开后显示各成员 Agent 的子 Span
- Debate 模式按轮次分组显示

---

## 六、Agent 评估仪表盘设计

### 6.1 评估概览页（AgentEvaluationPage）

| 组件 | 说明 |
|------|------|
| Agent 质量排名 | 按综合评分排序的 Agent 列表（任务成功率 × 用户好评率），支持按周/月切换 |
| 质量趋势图 | 折线图——各 Agent 的质量分变化趋势（ECharts） |
| 负面反馈列表 | 用户给出 thumbs_down 的 Run 列表（含对话摘要、Agent 名称、时间） |
| 版本对比面板 | 选择 Agent → 对比不同版本的指标（雷达图：成功率/好评率/Token 效率/延迟/工具成功率） |

### 6.2 反馈采集组件

| 位置 | 组件 |
|------|------|
| 对话页 | 每条 Agent 回复下方的 👍/👎 按钮 + "添加反馈" 展开文字输入框 |
| 执行详情页 | Run 级别的整体反馈按钮 |
| IM 渠道 | 回复末尾附加反馈引导文本（如"回复 👍 表示满意"） |

**反馈数据流：** 用户点击 → `POST /runs/{run_id}/feedback` → 写入 `run_feedback` 表 → 评估报表异步聚合。

---

## 七、定时与批量任务管理页面设计

### 7.1 定时任务列表页（ScheduledRunListPage）

| 组件 | 说明 |
|------|------|
| 任务列表 | 表格展示：Agent 名称、Cron 表达式（附人类可读说明）、下次执行时间、启停状态、最近执行状态 |
| 启停开关 | 行内 Toggle 开关，即时启用/禁用 |
| 新建定时任务 | 表单：选择 Agent → Cron 表达式（可视化 Cron 编辑器）→ 输入模板 → 通知配置 |
| 执行历史 | 展开行显示该定时任务的历史 Run 列表（含状态、时长、Token 消耗） |

### 7.2 批量任务列表页（BatchRunListPage）

| 组件 | 说明 |
|------|------|
| 任务列表 | 表格展示：Agent 名称、总项数、进度条、状态、创建时间 |
| 新建批量任务 | 表单：选择 Agent → 上传 JSON/CSV 文件 → 设置并行度 → 提交 |
| 进度视图 | 展开行显示：已完成 / 失败 / 进行中 / 待处理 的实时计数 + 失败项详情 |
| 取消操作 | 状态为 running 时显示"取消"按钮，确认后取消未开始的项 |

---

## 八、配置变更管理页面设计

### 8.1 概述

配置变更管理页面（ConfigChangePage）为管理员提供系统配置的可视化管理、变更审计和一键回滚能力。对应 API：`GET /api/v1/config/changes`、`PUT /api/v1/config/{key}`、`POST /api/v1/config/rollback`。

### 8.2 配置变更历史页（ConfigChangePage）

| 组件 | 说明 |
|------|------|
| 筛选栏 | 配置项键名（下拉 + 搜索）、操作人（下拉）、时间范围（日期选择器） |
| 变更列表 | ProTable 分页表格：时间、配置项、旧值、新值、操作人、变更说明 |
| Diff 查看 | 行内展开，对长文本（如 JSON 配置、Instructions）使用左右对比 Diff 视图 |
| 回滚按钮 | 每行末尾"回滚到此版本"按钮，二次确认弹窗后调用 `POST /api/v1/config/rollback` |
| 配置编辑 | 表头"编辑配置"按钮，抽屉表单：键名（只读）→ 当前值 → 新值 → 变更说明 → 提交调用 `PUT /api/v1/config/{key}` |

### 8.3 交互规则

| 规则 | 说明 |
|------|------|
| 回滚确认 | 弹窗显示：配置项、当前值、将恢复的值，需输入配置键名确认 |
| 即时生效 | 配置更新后通过 WebSocket 推送 Toast 通知："配置 {key} 已更新" |
| 操作审计 | 每次编辑和回滚操作自动记录变更日志 |
| 权限控制 | 仅 Admin 角色可访问；回滚操作额外要求二次身份验证 |

## 九、国际化设置页面设计

### 9.1 概述

国际化设置页面（I18nSettingsPage）为管理员提供 Agent Instructions 多语言版本管理和系统 UI 语言配置。对应 API：`GET/POST /api/v1/agents/{name}/locales`、`PUT/DELETE /api/v1/agents/{name}/locales/{locale}`。

### 9.2 Agent Instructions 多语言管理

| 组件 | 说明 |
|------|------|
| Agent 选择器 | 顶部下拉框选择目标 Agent |
| 语言版本列表 | 表格展示：语言标识（如 zh-CN）、是否默认、最后更新时间、操作（编辑 / 删除） |
| 新增语言版本 | 按钮 → 抽屉表单：语言标识（BCP 47 下拉）→ Instructions 编辑器（Markdown 支持）→ 是否设为默认 |
| 编辑 Instructions | 点击行 → 全屏 Markdown 编辑器，支持预览模式 |
| 删除确认 | 二次确认弹窗；默认语言版本禁止删除（按钮置灰 + Tooltip 提示） |

### 9.3 语言优先级说明

| 场景 | 语言选择逻辑 |
|------|------|
| 用户通过 Web UI 调用 Agent | 使用浏览器 `Accept-Language` 匹配最佳语言版本，无匹配则 fallback 到默认版本 |
| 用户通过 IM 渠道调用 Agent | 使用渠道消息附带的 `locale` 字段，无则 fallback 到默认版本 |
| API 直接调用 | 通过请求头 `X-Locale` 指定，无则 fallback 到默认版本 |

### 9.4 交互规则

| 规则 | 说明 |
|------|------|
| 默认语言保护 | 标记为默认的语言版本不可删除，切换默认前需先设置其他版本为默认 |
| Instructions 预览 | 编辑器右侧实时预览渲染后的 Markdown |
| 批量导入 | 支持上传 JSON 文件批量导入多语言 Instructions（格式：`{ "zh-CN": "...", "en-US": "..." }`） |

---

*文档版本：v1.2.0*
*最后更新：2026-04-02*
*作者：CkyClaw Team*

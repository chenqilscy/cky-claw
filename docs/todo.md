# CkyClaw 待办事项与演进规划

> 本文件记录 CkyClaw 项目的当前状态、未来演进方向和历史交付归档。
>
> 最后更新：2026-04-13 · 文档版本 v3.8.0

---

## 一、当前关键指标

| 指标 | 数值 |
|------|------|
| 测试通过 | **4233+**（Backend 1969 + Framework 1782 + Frontend 441 + CLI 41） |
| 测试覆盖率 | Backend **98%** · Framework **100%** |
| Alembic 迁移 | **51** 个（0001–0051） |
| API 路由模块 | **43** 个 |
| 前端页面 | **31** 个（React.lazy 懒加载） |
| 前端测试文件 | **49** 个 |
| 前端测试数 | **441** 个（Vitest） |
| CI Job | **6** 个 GitHub Actions + **5** Stage Jenkinsfile |
| TypeScript 错误 | **0** |
| Backend mypy | **0** 错误（166 源文件） |
| Framework mypy | **0** 错误（92 源文件） |
| ruff E501 | **0** |
| Playwright E2E | **32** 个烟雾测试 |

---

## 二、已知问题与技术债务

| # | 问题 | 状态 | 说明 |
|---|------|:----:|------|
| D1 | `test_ws_approvals.py` 导入失败 | ✅ 已修复 | `_broadcast` → `_broadcast_to` 同步更新 |
| D2 | `test_api_coverage.py` 140 错误 | ✅ 已修复 | 审计中间件 mock + JWT 篡改 + 广播修复 |
| D3 | 4 个 Framework 集成测试需 LLM Key | ⏭️ 已知 | 需要真实 LLM API Key，CI 中 skip，非阻塞 |
| D4 | 前端 vitest 超长耗时 | ✅ 已修复 | `css: false` + `include` 精确匹配 |
| D5 | pre-commit hooks 未在 CI 中运行 | ✅ 已修复 | 新增 `pre-commit/action@v3.0.1` CI Job |
| D6 | IM/OAuth token 无缓存 | ✅ 已修复 | Redis 统一缓存 `token_cache.py` |
| D7 | 日志缺少 request_id | ✅ 已修复 | `contextvars` + `_RequestIDFilter` |
| D8 | Framework 边界无守卫 | ✅ 已修复 | 3 个 AST 扫描测试确保零反向依赖 |

---

## 三、未完成功能

### 3.1 F 系列功能现状

| # | 功能 | 状态 | 说明 |
|---|------|:----:|------|
| F1 | 全链路启动验证 | ✅ | 25/25 API 验证通过 |
| F2 | **Kubernetes 部署** | ❌ | Helm Chart / Kustomize + HPA + PDB + Ingress |
| F3 | 日志聚合 | ✅ | Promtail→Loki + request_id + AlertRule |
| F4 | **Agents SDK 兼容层** | ❌ | OpenAI Agents SDK 适配器（优先级最低） |
| F5 | 流式输出端到端优化 | ✅ | RAF 批处理 + tool_call/handoff UI |
| F6 | Agent 自动评估 Pipeline | ✅ | LLM-as-Judge 7 维评分 |
| F7 | Agent 调试器 | ✅ | DebugController + 3 检查点 + WebSocket |
| F8 | 高级 Prompt Editor | ✅ | 模板变量引擎 render/validate/extract + 前端编辑器 |
| F9 | 移动端适配 | ✅ | useResponsive Hook + 审批/对话/仪表盘/布局 4 页面响应式 |
| F10 | **SSO SAML 2.0** | ❌ | 企业 SAML 单点登录集成 |
| F11 | 数据导出/报表 | ✅ | CSV 流式导出 + 注入防护 |
| F12 | 多环境管理 | ✅ | 环境 CRUD + 绑定 + 发布 + Diff + Runner 环境感知 |

**完成率：9/12（75%）。剩余 3 项：F2、F4、F10。**

### 3.2 各项详细分析

#### F2: Kubernetes 部署（P1 — 生产就绪）

**优先级**：P1（上生产的硬性要求）

**交付物**：
- [ ] Helm Chart（backend/frontend/db/redis 四服务）
- [ ] values.yaml（环境变量注入 + Secret 引用）
- [ ] HPA 水平弹性（基于 CPU/内存 + 自定义 metrics）
- [ ] PDB（Pod Disruption Budget，升级不中断）
- [ ] Ingress（Nginx/Traefik + TLS + 路径路由）
- [ ] ConfigMap / Secret 管理
- [ ] Kustomize overlays（dev / staging / prod）
- [ ] Health Check probes（liveness + readiness + startup）
- [ ] 部署文档

**前置条件**：Docker 镜像已有 Dockerfile，docker-compose 已就绪。

#### F4: Agents SDK 兼容层（P3 — 最低优先级）

**优先级**：P3（锦上添花，除非有客户显式要求）

**交付物**：
- [ ] Adapter 类：SDK Agent → CkyClaw Agent 映射
- [ ] 工具转换：SDK function schema → FunctionTool
- [ ] Handoff 映射：SDK transfer → CkyClaw Handoff
- [ ] Runner 桥接：SDK Runner → CkyClaw Runner
- [ ] 兼容性测试（SDK 示例直接运行）

**风险**：OpenAI SDK 频繁迭代，维护成本高。

#### F10: SSO SAML 2.0（P2 — 企业能力）

**优先级**：P2（企业客户需求驱动）

**交付物**：
- [ ] SAML 2.0 SP（Service Provider）实现
- [ ] IdP 元数据解析 + 证书管理
- [ ] SSO 登录流程：SP-Initiated + IdP-Initiated
- [ ] SLO（Single Logout）
- [ ] 属性映射（email/name/role → CkyClaw User）
- [ ] 前端 SSO 登录按钮 + 回调页
- [ ] 对接测试（Azure AD / Okta / OneLogin）

---

## 四、PRD 差距分析（对比 Hermes + Harness + NextCrab）

> 基于 [compare-report/Harness&Hermes Agent.md](compare-report/Harness&Hermes%20Agent.md) 深度分析。

### 4.1 竞品启示项落地状态

报告中提出的 12 项行动建议，逐项检查 CkyClaw 当前落地情况：

| # | 方向 | 来源 | CkyClaw 状态 | 说明 |
|---|------|------|:----:|------|
| 1 | 5 层上下文压缩 | Harness | ✅ 已有 | S1 ContextBuilder + ContextBudget + ContextSource + HistoryTrimmer 2 策略 |
| 2 | Artifact Store | Harness | ✅ 已有 | RunConfig.artifact_store + artifact_threshold（Token 外部化） |
| 3 | Cache-First Prompt | Harness | ✅ 已有 | RunConfig.system_prompt_prefix（KV 缓存友好前缀） |
| 4 | 结构化 Handoff | Harness | ✅ 已有 | Handoff + InputFilter + 深度循环检测 |
| 5 | Learning Loop | Hermes | ✅ 已有 | S5 LearningLoop + RunReflector + 版本回滚检查 |
| 6 | Circuit Breaker | NextCrab | ✅ 已有 | S3 CircuitBreaker + RetryBudget + FallbackChainProvider |
| 7 | ToolGateway 中间件 | NextCrab | ✅ 已有 | S3 ToolMiddleware Pipeline（洋葱模型） |
| 8 | Event Journal | NextCrab | ✅ 已有 | S4 EventStore + EventProjector + Replay 引擎 |
| 9 | 三 Agent Harness | Anthropic | ✅ 已有 | E3 PlanEvaluator 三角审查 + PlanGuard 集成 |
| 10 | **Skill Factory** | Hermes | ✅ 已有 | E1 SkillFactory + AST 白名单 + 元工具 + 持久化 |
| 11 | **Soul 成长模型** | NextCrab | ✅ 已有 | E2 MaturityModel 四维评分 + 四级成长 + 能力解锁 |
| 12 | **多终端 + 消息网关** | Hermes | ✅ 已有 | E4 TerminalBackend + E5 Telegram/Discord 适配器 |

**差距汇总**：12 项中 **12 项全部覆盖**（E1-E5 填补后零差距）。

### 4.2 Hermes 多终端 + 消息网关深度分析

Boss 要求重点分析 Hermes 的多终端架构：

```
                    ┌─────────────────┐
                    │   Hermes Core   │
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
     ┌────────┴──┐  ┌───────┴───────┐  ┌───┴────────┐
     │ Terminal   │  │ Web/TUI      │  │ Messaging  │
     │ Backends   │  │              │  │ Gateway    │
     │            │  │              │  │            │
     │ • Rich     │  │ • Web UI     │  │ • Telegram │
     │ • Plain    │  │ • Textual    │  │ • Discord  │
     │ • Simple   │  │              │  │ • Slack    │
     │ • Prompt   │  │              │  │ • WhatsApp │
     │ • IPython  │  │              │  │ • Signal   │
     │ • Custom   │  │              │  │            │
     └────────────┘  └──────────────┘  └────────────┘
```

**CkyClaw vs Hermes 终端覆盖对比**：

| 终端类型 | Hermes | CkyClaw | 差距 |
|---------|:------:|:-------:|------|
| Web UI | ✅ | ✅ React SPA | — |
| CLI | ❌ | ✅ ckyclaw-cli | CkyClaw 领先 |
| Rich Terminal | ✅ | ✅ PlainTerminalBackend | E4 TerminalBackend ABC |
| Plain/Prompt Terminal | ✅ | ✅ PlainTerminalBackend | E4 实现 |
| IPython/Notebook | ✅ | ❌ | 数据科学场景 |
| Textual TUI | ✅ | ❌ | 终端图形界面 |
| Telegram | ✅ | ✅ TelegramAdapter | E5 实现 |
| Discord | ✅ | ✅ DiscordAdapter | E5 实现 |
| Slack | ✅ | ✅ IM 适配器 | — |
| WhatsApp | ✅ | ❌ | 海外社交 |
| Signal | ✅ | ❌ | 隐私社交 |
| 企微/钉钉/飞书 | ❌ | ✅ IM 适配器 | CkyClaw 国内领先 |
| 微信公众号 | ❌ | ✅ IM 适配器 | CkyClaw 国内领先 |
| 自定义 Webhook | ❌ | ✅ IM 适配器 | CkyClaw 灵活性领先 |

**分析结论**：
1. **CkyClaw 国内渠道远超 Hermes**（企微/钉钉/飞书/微信是 Hermes 完全没有的）
2. **CkyClaw CLI 是 Hermes 没有的独立包**
3. Hermes 的 Terminal backends 面向开发者/研究者场景（Rich/IPython/Textual），CkyClaw 以 Web UI 为主交互面
4. 海外社交（Telegram/Discord/WhatsApp/Signal）是 CkyClaw 的空白，但**不是中国企业 AI 团队的刚需**

**建议优先级**：
- P3：Terminal backends（Rich/Textual）— 开发者体验提升，但 CLI 已覆盖核心场景
- P3：Telegram/Discord — 仅在出海业务需要时考虑
- **不建议**：WhatsApp/Signal — 中国用户基本不用

---

## 五、演进方向（Next Wave）

### 5.1 v3.x S 系列（全部完成 ✅）

| Phase | 核心交付 | 状态 |
|-------|---------|:----:|
| S1 上下文工程 | ContextBuilder + ContextBudget + ContextSource | ✅ |
| S2 记忆三分类 | Episodic / Semantic / Procedural | ✅ |
| S3 LLM 容错 | CircuitBreaker + RetryBudget + ToolMiddleware | ✅ |
| S4 事件溯源 | EventStore + EventProjector + Replay | ✅ |
| S5 自改进闭环 | LearningLoop + RunReflector | ✅ |
| S6 取消+检查点 | CancellationToken + RunRegistry + Resume | ✅ |
| S7 智能编排 | PlanGuard + Mailbox 通信 | ✅ |

### 5.2 v4.x 新演进（基于竞品差距分析）

| # | Phase | 核心交付 | 优先级 | 依赖 |
|---|-------|---------|:------:|------|
| E1 | ~~**Skill Factory**~~ | ✅ 完成 — SkillFactory + SkillDefinition + AST 白名单 + 元工具 + 持久化 | P1 | S5 LearningLoop |
| E2 | ~~**Agent Maturity Model**~~ | ✅ 完成 — MaturityModel 四维评分 + 四级成长(Newborn→Expert) + 能力解锁 + 自动升降级 | P2 | S5 + Memory |
| E3 | ~~**Planning-Evaluation 分离**~~ | ✅ 完成 — PlanEvaluator 三角审查 + PlanGuard 集成 + 自定义标准 + async | P2 | S7 PlanGuard |
| E4 | ~~**Terminal Gateway**~~ | ✅ 完成 — TerminalBackend ABC + PlainTerminalBackend + StructuredOutput + OutputType | P3 | CLI |
| E5 | ~~**海外消息网关**~~ | ✅ 完成 — TelegramAdapter + DiscordAdapter + 签名验证 + Webhook 推送 | P3 | IM Channels |

### 5.3 未完成 F 系列优先级排序

| 排名 | 功能 | 优先级 | 理由 |
|:----:|------|:------:|------|
| 1 | F2 Kubernetes 部署 | P1 | 生产上线的硬性前提 |
| 2 | F10 SSO SAML 2.0 | P2 | 企业客户准入门槛 |
| 3 | F4 Agents SDK 兼容层 | P3 | 无客户显式需求，维护成本高 |

---

## 六、已完成能力归档

### 6.1 核心框架（CkyClaw Framework）

| 能力 | 版本 | 说明 |
|------|:----:|------|
| Agent 定义 + as_tool | M0 | Agent 数据类 + as_tool() 包装 |
| Runner Agent Loop | M0 | run / run_sync / run_streamed + max_turns + TaskGroup 并行工具 |
| Handoff 编排 | M0 | 多级递归 + InputFilter + 循环检测 |
| Guardrails 三级护栏 | M0 | Input/Output/Tool × Regex/Keyword/LLM |
| Approval 审批 | M0 | suggest/auto-edit/full-auto + HttpApprovalHandler |
| Tracing 链路追踪 | M0 | Agent/LLM/Tool/Handoff/Guardrail Span + PostgresTraceProcessor |
| Session 持久化 | M0 | InMemory/Postgres + HistoryTrimmer |
| MCP 集成 | M0 | stdio/sse/http + 命名空间隔离 |
| Tool 系统 | M0 | FunctionTool + ToolGroup + ToolRegistry + ToolSearchTool + Hosted Tools |
| Multi-Provider | M0 | LiteLLMProvider + 10+ 厂商适配 |
| output_type 结构化输出 | v2.1 | Agent.output_type + Runner JSON 解析 |
| Dynamic Instructions | v2.2 | str/sync/async callable |
| Memory 记忆系统 | v2.2 | Framework + Backend + Frontend 全栈 |
| Skill 技能系统 | v2.2 | Framework + Backend + Frontend 全栈 |
| Agent Team 协作 | v2.3 | Sequential/Parallel/Coordinator + UI 可视化 |
| Sandbox 沙箱 | v2.6 | SandboxConfig + LocalSandbox |
| Guardrail 并行 | v2.1 | RunConfig.guardrail_parallel + TaskGroup |
| Runner 重试 | v2.1 | max_retries + 指数退避 |
| Tool 并发限流 | v2.1 | Semaphore |
| 条件启用 | v2.1 | Guardrail/Tool/Agent 三级 condition |
| Lifecycle Hooks | M7 | 10 个触发点 + 非阻塞异步 |
| Evolution 自动进化 | M8 | SignalCollector + StrategyEngine + EvolutionHook |
| Checkpoint 机制 | v2.6 | InMemory/Postgres + Runner resume_from |
| Intent Detection | v2.6 | IntentDetector + KeywordIntentDetector + 意图飘移 Hook |
| Cost Router | v2.6 | ModelTierEnum + CostRouter 规则分类器 |
| S1 上下文工程 | v3.0 | ContextBuilder + ContextBudget + ContextSource |
| S2 记忆三分类 | v3.1 | Episodic / Semantic / Procedural |
| S3 LLM 容错 | v3.2 | CircuitBreaker + RetryBudget + ToolMiddleware |
| S4 事件溯源 | v3.2 | EventStore + EventProjector + Replay |
| S5 自改进闭环 | v3.3 | LearningLoop + RunReflector |
| S6 取消+检查点 | v3.3 | CancellationToken + RunRegistry + Resume |
| S7 智能编排 | v3.4 | PlanGuard + Mailbox 通信 |
| F8 模板变量 | v3.4 | render/validate/extract + 前端变量编辑器 |
| F12 Runner 环境感知 | v3.5 | RunConfig.environment + Trace.metadata 自动标记 |

### 6.2 后端（Backend）— 43 路由模块

| 能力 | 说明 |
|------|------|
| Agent CRUD + 版本管理 | 自动快照 + 对比 + 回滚 + YAML/JSON 导入导出 |
| 完整 RBAC | Role ORM + require_permission + 前端 RolePage |
| 多租户 | Organization + get_org_id + 数据隔离加固 |
| OAuth 2.0 | GitHub / 企微 / 钉钉 / 飞书 / Google / Keycloak |
| IM 渠道 6 适配器 | 企微 / 钉钉 / 飞书 / 微信公众号 / Slack / 自定义 Webhook |
| APM 仪表盘 | 聚合 API + ECharts + AlertRule 告警引擎 |
| 定时/批量任务 | SchedulerEngine + cron/interval |
| Token 审计 | 自动采集 + Agent/Model/User 多维统计 + 趋势 API |
| 配置热更新 | ConfigChangeLog + 审计 + 回滚 |
| 环境管理 | Dev/Staging/Prod + 发布/回滚/对比 + Agent 绑定 |
| 模板变量 | prompt_template API + render/validate/extract |
| Agent 评估 | 7 维评分 + 反馈 + 汇总 |
| Agent 国际化 | LocalizedInstructions + locale |
| 灾备策略 | backup/restore/verify 脚本 + cron |
| 深度健康检查 | /health/deep + DB/Redis 探测 |
| Agent 实时状态 | TraceRecord 聚合 + Dashboard 卡片 |
| WebSocket 统一事件 | /api/ws/events + Redis PubSub |
| Span 火焰图 | build_flame_tree + GET /flame |
| Trace 回放 | build_replay_timeline + Timeline 组件 |
| A/B 模型测试 | POST /ab-test 并行调用 |
| Session 消息搜索 | LIKE 通配符转义 |
| Agent 模板 10 个 | 4 垂直模板（code-reviewer/devops/bi-analyst/complaint） |

### 6.3 前端（Frontend）— 31 页面

| 能力 | 说明 |
|------|------|
| Dashboard | 6 统计 + Token 分布 + Guardrail + Span + 自动刷新 + 活动趋势 |
| 对话页 | ChatPage + Drawer/Sider 响应式 + SSE 流式 |
| Agent 管理 | 列表/编辑/版本/Handoff 编排/模板市场/变量编辑器 |
| 审批队列 | ProTable + WebSocket 实时 + 响应式 Dropdown 操作 |
| 环境管理 | 列表/详情/发布/Diff + 全局环境选择器 |
| 移动端适配 | useResponsive Hook + 4 页面响应式优化 |
| 可视化 | ReactFlow（Handoff/Team/Workflow）+ ECharts（Dashboard/APM/Flame） |
| 暗色模式 | themeStore + ConfigProvider |
| Playwright E2E | 32 烟雾测试 + playwright.config + 远程站点配置 |
| pre-commit | ruff + mypy + 6 hooks |
| Vendor 分包 | antd/charts/markdown/flow/query 5 路 manualChunks |

### 6.4 基础设施

| 能力 | 说明 |
|------|------|
| Docker Compose | PG + Redis + Backend + Frontend + 健康检查 + 自动迁移 |
| GitHub Actions | 5 Job（lint-py / lint-fe / test-py / test-fe / build） |
| Jenkinsfile | 5 Stage 容器化流水线 |
| ckyclaw-cli | CLI MVP: login/version/agent/provider + 32 测试 |
| Token 缓存 | Redis 统一缓存层 |
| OTel + Jaeger | OTelTraceProcessor + FastAPI 中间件 + OTel Web SDK 前端追踪 |
| Prometheus + Loki | Promtail 3.0 docker_sd + Loki TSDB + AlertRule + Grafana 数据源 |
| Locust 性能测试 | 12 @task + 10+ API 覆盖 |
| OpenAPI Tags | 43 个 API 分组描述，`/openapi.json` |
| request_id 追踪 | contextvars + 日志 Filter 自动注入 + 响应头回传 |

---

## 七、竞品定位

| 维度 | CkyClaw | 直接依赖 Agents SDK | Hermes Agent |
|------|---------|:---:|:---:|
| 多 Provider（10+） | ✅ | ❌ | ⚠️ OpenRouter |
| 国产模型适配 | ✅ | ❌ | ❌ |
| 数据主权 / 本地部署 | ✅ | ⚠️ | ✅ |
| 企业能力（RBAC/多租户/审计） | ✅ | ❌ | ❌ |
| 三阶段护栏 | ✅ (7 种内置) | ❌ | ❌ (Prompt 约束) |
| 国内 IM (企微/钉钉/飞书) | ✅ | ❌ | ❌ |
| 自创技能 Skill Factory | ✅ | ❌ | ✅ |
| 终端后端 (Rich/TUI) | ✅ | ❌ | ✅ |
| 用户建模 Honcho | ❌ | ❌ | ✅ |

---

## 八、Next Wave v2 演进路线（N1–N7）

> 基于 v3.8 能力差距分析 + 十角色团队评审，下一波演进方向。  
> 排序依据：AI Agent 平台核心性 × 中国企业需求优先级。

### 8.1 总览

| # | Phase | 核心交付 | 优先级 | 状态 |
|---|-------|---------|:------:|:----:|
| N1 | **RAG 知识库** | Embedding + VectorStore + DocumentLoader + ChunkStrategy + RAG Pipeline + KnowledgeBaseTool | **P0** | ✅ Framework + Backend + Frontend(MVP) |
| N2 | **Multi-Modal 消息模型** | ContentBlock 多态消息体 + Message 扩展 + LiteLLM 格式转换 | **P1** | ✅ Framework + Backend + Frontend(MVP) |
| N3 | **Agent Visual Builder** | 拖拽式 Agent 拼装器（工具/护栏/Handoff/MCP 可视化配置） + Canvas→JSON 单向同步 | **P1** | ✅ Phase 1(MVP) |
| N4 | **A2A Protocol** | Agent Card 发现协议 + Task Lifecycle + A2AClient/Server + 隔离适配层 | **P2** | ❌ |
| N5 | **Agent Marketplace** | Agent 模板发布/发现/评分/收藏 + 跨组织共享 + 版本管理 + 一键实例化 | **P2** | ❌ |
| N6 | **Compliance 合规框架** | 数据分类标签 + 保留策略自动执行 + Right-to-Erasure 工作流 + SOC2 控制点映射 + 合规报表 | **P2** | ❌ |
| N7 | **Agent Benchmarking** | 标准化评估套件，E2 成熟度模型的自然延伸 | **P3** | ❌ |

### 8.2 N1: RAG 知识库（P0 — Agent 平台核心原语）

**动机**：知识密集型场景（客服/法律/医疗/技术文档）是 AI Agent 最高频应用，缺少 RAG 等于砍掉 50% 场景。

**Framework 层** — `ckyclaw_framework/rag/`

| 模块 | 职责 |
|------|------|
| `embedding.py` | EmbeddingProvider ABC + LiteLLMEmbeddingProvider（复用 LiteLLM 适配 10+ 厂商） |
| `chunker.py` | ChunkStrategy ABC + FixedSizeChunker + RecursiveCharacterChunker + MarkdownChunker |
| `document.py` | DocumentLoader ABC + TextLoader + MarkdownLoader + PDFLoader（可选 pymupdf4llm） |
| `vector_store.py` | VectorStore ABC + InMemoryVectorStore + PgVectorStore（pgvector 扩展） |
| `pipeline.py` | RAGPipeline：retrieve(query, top_k) → augment(context+prompt) → 返回增强消息 |
| `tool.py` | `@function_tool` 包装的 knowledge_base_search 工具，Agent 可直接调用 |

**Backend 层**

| 模块 | 职责 |
|------|------|
| KnowledgeBase ORM | 知识库元数据（名称/描述/embedding模型/chunk策略） |
| Document ORM | 文档记录（文件名/大小/chunk数/状态） |
| Chunk ORM | 分块记录（content + embedding vector(1536)） |
| REST API | CRUD 知识库 + 上传文档 + 触发索引 + 搜索测试 |
| Agent 绑定 | Agent.knowledge_base_ids 多对多关联 |

**Frontend 层**

| 页面 | 功能 |
|------|------|
| KnowledgeBasePage | ProTable 列表 + 创建/编辑 Modal |
| KnowledgeBaseDetailPage | 文档列表 + 上传 + 索引状态 + 搜索测试面板 |
| AgentEditPage 增强 | 知识库选择器（多选） |

**前置依赖**：
- PostgreSQL 需启用 `pgvector` 扩展
- `MemoryEntry.embedding` 字段已存在，可复用 Embedding 基础设施

### 8.3 N2: Multi-Modal 消息模型（P1 — 现代 AI 基础能力）

**动机**：GPT-4o/Claude 3.5/通义千问-VL 均支持多模态，Framework 消息模型仍为纯文本是硬伤。

**Framework 层** — 扩展消息模型

```
ContentBlock (Union)
├── TextContent      {type: "text", text: str}
├── ImageContent     {type: "image", url: str | None, base64: str | None, media_type: str}
├── AudioContent     {type: "audio", url: str | None, base64: str | None, format: str}
├── FileContent      {type: "file", url: str, filename: str, media_type: str}
└── ToolResultContent {type: "tool_result", tool_call_id: str, output: str}
```

- Runner 消息从 `str` 扩展为 `str | list[ContentBlock]`
- LiteLLMProvider 适配多模态消息格式转换
- Session 持久化支持 ContentBlock JSON 序列化

**Frontend 层**
- ChatPage 支持图片/文件拖拽上传
- 消息气泡渲染 ImageContent（内联预览）、FileContent（下载链接）、AudioContent（播放器）

### 8.4 N3: Agent Visual Builder（P1 — 降低使用门槛）

**动机**：对标 Dify/Coze 的无代码 Agent 构建体验，当前 AgentEditPage 仅为表单。

**交付物（Phase 1 单向同步）**
- ReactFlow 画布：中心 Agent 节点 + 周围可拖入的组件节点（Tool / Guardrail / Handoff / MCP Server）
- 左侧 Palette 面板：可用组件列表（从平台已注册的 Tool/Guardrail/MCP 动态加载）
- 右侧属性面板：选中节点后编辑属性
- Canvas → JSON 单向转换（画布为视图层，JSON 为数据层）
- 保存时生成等效 Agent 配置 JSON，调用现有 Agent CRUD API

**Phase 2 双向同步**（后续优化）
- JSON → Canvas 反向渲染，编辑 JSON 后画布自动更新

### 8.5 N4: A2A Protocol（P2 — 跨平台互操作）

**动机**：Google 2024 发布 Agent-to-Agent 协议，是跨平台 Agent 互操作的未来标准。提前布局可建立先发优势。

**交付物**
- Framework: A2AServer（接收外部 Agent 请求） + A2AClient（调用外部 Agent）
- Agent Card 发现协议实现（/.well-known/agent.json）
- Task 生命周期管理（submitted → working → completed / failed）
- A2AAdapter 隔离层，规范变动时只改适配器
- Backend: A2A 端点注册 + 服务发现 API

### 8.6 N5: Agent Marketplace（P2 — 生态护城河）

**动机**：竞品 Hermes 有 Skill Marketplace、NextCrab 有远端 Marketplace API，CkyClaw 仅有内部模板。

**交付物**
- AgentTemplate 扩展：新增 `published`、`downloads`、`rating`、`author_org_id` 字段
- 发布流程：组织内模板 → 审核 → 公开发布
- 发现机制：分类标签 + 搜索 + 热门排行 + 推荐
- 一键安装：从市场模板实例化 Agent 到当前组织
- 评分评论：用户评分 + 使用反馈

### 8.7 N6: Compliance 合规框架（P2 — 企业准入）

**动机**：企业客户（金融/医疗/政府）需要合规认证才能采购。

**交付物**
- 数据分类标签系统：PII / PHI / 敏感 / 公开，自动标记 + 手动标记
- 数据保留策略：按数据分类 + 时间维度自动清理（Trace / Session / AuditLog）
- Right-to-Erasure 工作流：用户请求 → 自动扫描所有子系统 → 删除/脱敏 → 生成合规报告
- SOC2 控制点映射：将现有安全措施（加密/RBAC/审计）映射到 SOC2 TSC
- 合规仪表盘：控制点完成率 + 数据保留状态 + 删除请求处理队列

### 8.8 N7: Agent Benchmarking（P3 — 量化评估）

**动机**：E2 成熟度模型提供了四维评分，但缺少标准化评估套件。

**交付物**
- BenchmarkSuite：定义评估场景（工具调用准确率 / 多轮对话连贯性 / 拒答合规性 / 幻觉率）
- BenchmarkRunner：自动批量执行 + 结果采集 + 报告生成
- 与 E2 MaturityModel 集成：评测结果自动影响成熟度评分
- Frontend: 评测仪表盘 + 历史对比图表

---

## 九、版本历史

| 版本 | 里程碑摘要 |
|------|-----------|
| M0–M7 | 60+ Phase：Agent 全栈 |
| v2.1–v2.8 | output_type / Memory / Skill / Team / RBAC / APM / Evolution / E2E |
| v3.0–v3.4 | S1–S7 演进路线 + F1–F12 生产功能 |
| v3.5 | F8+F9+F12 完成 + Runner 环境感知 + 文档整理 |
| v3.6 | E1 Skill Factory 完成 |
| v3.7 | E2 Agent 成熟度模型 + E3 规划-评估分离 |
| v3.8 | E4 Terminal Gateway + E5 Telegram/Discord 消息网关（E1-E5 全部完成） |
| v4.0 | N1 RAG 知识库 + N2 Multi-Modal 消息模型（Framework 层完成） |
| v4.1 | N1/N2 Backend+Frontend(MVP) + N3 Visual Builder Phase 1(MVP) |

---

*基于：PRD v2.0.9 / M0–M7 + v2.1–v2.8 + v3.0–v3.8 + v4.0–v4.1 全部完成*

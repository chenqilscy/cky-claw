# CkyClaw 待办事项与演进规划

> 本文件记录 CkyClaw 项目的当前状态、未来演进方向和历史交付归档。
>
> 最后更新：2026-07-07 · 文档版本 v3.1.0

---

## 一、当前关键指标

| 指标 | 数值 |
|------|------|
| 测试通过 | **2958+**（Backend 1740 + Framework 1218） |
| 测试覆盖率 | Backend **98%** · Framework **100%** |
| Alembic 迁移 | **45** 个（0001–0045） |
| API 路由模块 | **37** 个 |
| 前端页面 | **38** 个（React.lazy 懒加载，含 29 菜单页 + 9 非菜单页） |
| 前端测试文件 | **74** 个 |
| CI Job | **6** 个 GitHub Actions + **5** Stage Jenkinsfile |
| TypeScript 错误 | **0** |
| Backend mypy | **0** 错误（166 源文件） |
| Framework mypy | **0** 错误（92 源文件） |
| ruff E501 | **0** |
| Playwright E2E | **33** 个烟雾测试 |

---

## 二、已知问题与技术债务

| # | 问题 | 状态 | 说明 |
|---|------|:----:|------|
| D1 | `test_ws_approvals.py` 导入失败 | ✅ 已修复 | `_broadcast` → `_broadcast_to` 同步更新（commit `82490e9`） |
| D2 | `test_api_coverage.py` 140 错误 | ✅ 已修复 | 审计中间件 mock + JWT 篡改 + 广播修复（commit `82490e9`） |
| D3 | 4 个 Framework 集成测试需 LLM Key | ⏭️ 已知 | 需要真实 LLM API Key，CI 中 skip，非阻塞 |
| D4 | 前端 vitest 超长耗时 | ✅ 已修复 | `css: false` + `include` 精确匹配，耗时大幅降低（commit `82490e9`） |
| D5 | pre-commit hooks 未在 CI 中运行 | ✅ 已修复 | 新增 `pre-commit/action@v3.0.1` CI Job（commit `82490e9`） |

> D1/D2/D4/D5 已在 R17 技术债务修复中全部解决。

---

## 三、未来演进方向

### 3.1 生产就绪（P0）

| # | 功能 | 说明 |
|---|------|------|
| F1 | 全链路启动验证 | PG + Redis + Backend + Frontend 完整功能流程体验、修复 UI/API 缺陷 |
| F2 | Kubernetes 部署 | Helm Chart / Kustomize + HPA + PDB + Ingress |
| F3 | 日志聚合 | 结构化日志 + ELK/Loki 集成 (开源免费方案优先) |

### 3.2 框架能力增强（P1）

| # | 功能 | 说明 |
|---|------|------|
| F4 | Agents SDK 兼容层（优先级最低） | Adapter 允许 OpenAI Agents SDK 的 Agent 定义直接在 CkyClaw 上运行 |
| F5 | 流式输出端到端优化 | Runner run_streamed 的 SSE/WebSocket 推送链路末端优化 |
| F6 | Agent 自动评估 Pipeline | 基于 Evolution Signal + 评估维度的自动化质量评分 |

### 3.3 用户体验（P2）

| # | 功能 | 说明 |
|---|------|------|
| F7 | Agent 调试器 | 交互式单步执行 Agent，查看每步 LLM 输入/输出/工具调用 |
| F8 | 高级 Prompt Editor | 模板变量 + 版本管理 + A/B 测试集成 |
| F9 | 移动端适配 | 关键页面（对话、审批）响应式优化 |

### 3.4 企业能力（P2）

| # | 功能 | 说明 |
|---|------|------|
| F10 | SSO SAML 2.0 | 企业 SAML 单点登录集成 |
| F11 | 数据导出/报表 | Token 使用、Agent 执行 CSV/PDF 导出 |
| F12 | 多环境管理 | Dev/Staging/Prod Agent 配置隔离与发布流程 |

---

## 四、已完成能力归档

> M0–M7 + v2.1–v2.8 全部已完成功能的精简归档。

### 4.1 核心框架（CkyClaw Framework）

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

### 4.2 后端（Backend）— 37 路由模块

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

### 4.3 前端（Frontend）— 38 页面

| 能力 | 说明 |
|------|------|
| Dashboard | 6 统计 + Token 分布 + Guardrail 状态 + Span 分布 + 自动刷新 + 活动趋势 |
| 对话页 | ChatPage + ChatSidebar + MarkdownRenderer + SSE 流式 |
| Agent 管理 | 列表/编辑/版本（色彩 diff）/Handoff 编排/模板市场 |
| 可视化 | ReactFlow（Handoff/Team/Workflow）+ ECharts（Dashboard/APM/Flame） |
| 暗色模式 | themeStore + ConfigProvider |
| Playwright E2E | 33 烟雾测试 + playwright.config |
| pre-commit | ruff + mypy + 6 hooks |
| Vendor 分包 | antd/charts/markdown/flow/query 5 路 manualChunks |

### 4.4 基础设施

| 能力 | 说明 |
|------|------|
| Docker Compose | PG + Redis + Backend + Frontend + 健康检查 + 自动迁移 |
| GitHub Actions | 5 Job（lint-py / lint-fe / test-py / test-fe / build） |
| Jenkinsfile | 5 Stage 容器化流水线 |
| Locust 性能测试 | 12 @task + 10+ API 覆盖 |
| OTel + Jaeger | OTelTraceProcessor + FastAPI 中间件 |
| Prometheus | docker-compose profile + scrape 配置 |

---

## 五、版本历史

| 版本 | 里程碑摘要 |
|------|-----------|
| M0–M7 | 60+ Phase：Agent 全栈（CRUD/Runner/Handoff/Guardrail/Approval/Tracing/Session/MCP/Tools/Hooks/Dashboard/Auth/Docker/CI） |
| v2.1 | output_type + Session 裁剪 + WebSocket 审批 + 前端测试 181 个 |
| v2.2 | Memory + Skill + Dynamic Instructions + 10 模板 |
| v2.3 | Agent Team 全栈 + 审计日志 |
| v2.4 | RBAC + 多租户 + IM 渠道 6 适配器 + OAuth 2.0 |
| v2.5 | OTel/Prometheus/APM 仪表盘 + Agent 评估 |
| v2.6 | 定时任务 + 沙箱 + 配置热更新 + 灾备 + 声明式配置 + Checkpoint + Intent + CostRouter |
| v2.7 | M8 Evolution + 多租户加固 + 火焰图 + 消息搜索 + WebSocket 事件 |
| v2.8 | Trace 回放 + A/B 测试 + Agent diff 增强 + Playwright E2E + pre-commit linter |

---

## 六、竞品定位

CkyClaw Framework 属于 **AI Agent 开发框架（SDK）** 维度。

| 维度 | CkyClaw | 直接依赖 Agents SDK |
|------|---------|:---:|
| 多 Provider（10+） | ✅ | ❌ |
| 国产模型适配 | ✅ | ❌ |
| 数据主权 / 本地部署 | ✅ | ⚠️ |
| 企业能力（RBAC/多租户/审计） | ✅ | ❌ |
| 定制深度 | ✅ 完全掌控 | ⚠️ 受 API 限制 |

详细分析见 [references/competitive-analysis.md](references/competitive-analysis.md)。

---

*基于：PRD v2.0.9 / M0–M7 + v2.1–v2.8 全部完成*

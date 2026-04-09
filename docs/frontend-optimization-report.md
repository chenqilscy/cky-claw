# CkyClaw 前端优化总结报告

> 生成时间：2026-04-09
> 范围：P0 Bug 修复 + P1 架构统一 + P2 体验优化 + Jaeger/Prometheus 可观测性集成

---

## 一、总览

| 阶段 | 任务数 | 完成 | 状态 |
|------|--------|------|------|
| P0: Bug 修复 | 5 | 5 | ✅ 全部完成 |
| P1-1: 共享组件抽取 | 6 | 6 | ✅ 全部完成 |
| P1-2: TanStack Query Hook 生成 | 15+ | 15+ | ✅ 全部完成 |
| P1-3: 页面迁移到 TanStack Query | ~20 | ~20 | ✅ 全部完成 |
| P1-4: CrudTable 统一 | 12 | 12 | ✅ 全部完成 |
| P2-1: Dashboard 响应式 + Skeleton | 1 | 1 | ✅ 完成 |
| P2-2: Chat 响应式侧边栏 | 1 | 1 | ✅ 完成 |
| P2-3: 暗色模式硬编码颜色清理 | 3 | 3 | ✅ 完成 |
| OTel: Jaeger + Prometheus 集成 | 1 | 1 | ✅ 完成 |

**测试结果**：73/73 测试文件, 388/388 测试用例, 0 TypeScript 错误

---

## 二、P0: Bug 修复（5/5）

### P0-1: 颜色常量统一
- 创建 `src/constants/colors.ts`
- 将 `AGENT_STATUS_COLORS`, `STEP_TYPE_TAG_COLORS`, `HEALTH_STATUS_COLORS` 等抽取为常量
- 17 个文件引用统一

### P0-2: Chat 页面主题 Token
- `ChatPage.tsx` 硬编码颜色 → `token.colorBorderSecondary`, `token.colorBgContainer`
- 新增 `useBreakpoint()` 实现移动端自适应

### P0-3: Message API 统一
- 17 个文件从 `message.xxx()` 迁移到 `App.useApp()` 上下文调用
- 消除 `message` 静态方法导致的主题不一致问题

### P0-4: AgentEditPage 静默失败修复
- 保存失败时添加 `catch` 分支显示 `message.error`

### P0-5: Dead Code 清理
- 删除未使用的 store 文件

---

## 三、P1: 架构统一

### P1-1: 共享组件抽取（6 组件）

| 组件 | 路径 | 用途 |
|------|------|------|
| `StatusTag` | `src/components/StatusTag.tsx` | 通用状态标签 |
| `ConfirmDeleteButton` | `src/components/ConfirmDeleteButton.tsx` | 删除确认按钮 |
| `PageCard` | `src/components/PageCard.tsx` | 页面卡片容器 |
| `EmptyPlaceholder` | `src/components/EmptyPlaceholder.tsx` | 空状态占位 |
| `SearchInput` | `src/components/SearchInput.tsx` | 搜索输入框 |
| `CrudTable` | `src/components/CrudTable.tsx` | 泛型 CRUD 表格 |

### P1-2: TanStack Query Hook 生成（15+ 文件）

| Hook 文件 | 覆盖 API |
|-----------|----------|
| `useAgentQueries.ts` | Agent CRUD, list, search |
| `useProviderQueries.ts` | Provider CRUD, toggle, test, rotate |
| `useSessionQueries.ts` | Session CRUD, messages |
| `useTemplateQueries.ts` | Template list, seed, instantiate |
| `useGuardrailQueries.ts` | Guardrail CRUD |
| `useToolGroupQueries.ts` | ToolGroup CRUD |
| `useApprovalQueries.ts` | Approval list, approve, reject |
| `useApmQueries.ts` | APM dashboard data |
| `useTraceQueries.ts` | Trace list, detail |
| `useEvaluationQueries.ts` | Evaluation CRUD, feedback |
| `useWorkflowQueries.ts` | Workflow CRUD, validate |
| `useMCPServerQueries.ts` | MCP Server CRUD, tools |
| `useMemoryQueries.ts` | Memory CRUD |
| `useCheckpointQueries.ts` | Checkpoint list, delete |
| `useSystemQueries.ts` | System info (OTel status) |

### P1-3: 页面迁移到 TanStack Query（~20 页面）

所有页面从直接 `useState` + `useEffect` + service 调用，迁移到 TanStack Query 声明式数据获取。

**测试修复**（4 个文件）：
- `ApmDashboardPage.test.tsx` — `act()` → `waitFor()` 模式修复
- `RunListPage.test.tsx` — 同上
- `ProviderKeyRotation.test.tsx` — 同上（6 个测试）
- `LoginPage.test.tsx` — OAuth error mock 修复

### P1-4: CrudTable 统一（12 页面）

| 已迁移页面 | 路径 |
|-----------|------|
| ScheduledTasks | `scheduled-tasks/ScheduledTasksPage.tsx` |
| IMChannel | `im-channels/IMChannelPage.tsx` |
| Guardrails | `guardrails/GuardrailRulesPage.tsx` |
| ToolGroups | `tool-groups/ToolGroupPage.tsx` |
| Evolution | `evolution/EvolutionPage.tsx` |
| Roles | `roles/RolePage.tsx` |
| Organizations | `organizations/OrganizationPage.tsx` |
| MCPServer | `mcp/MCPServerPage.tsx` |
| Memories | `memories/MemoryPage.tsx` |
| Skills | `skills/SkillPage.tsx` |
| Workflows | `workflows/WorkflowPage.tsx` |
| Teams | `teams/TeamPage.tsx` |

**不适合迁移的页面**（特殊交互模式）：
- AgentList / ProviderList — 编辑走独立页面（navigate）
- Approvals — 审批操作 + WebSocket 实时更新
- Supervision — 暂停/恢复控制
- I18nSettings — Drawer + Agent 选择器
- Templates — 卡片布局（非表格）
- Evaluation — 多 Tab + 只创建不编辑

---

## 四、P2: 体验优化

### P2-1: Dashboard 响应式布局
- 6 个统计卡片：`span={4}` → `xs={12} sm={12} md={8} lg={4}`
- 趋势/排行区域：`span={14}` → `xs={24} lg={14}`
- `<Spin>` → `<Skeleton active paragraph={{ rows: 12 }}>` 骨架屏
- 所有硬编码颜色 → theme tokens（`colorPrimary`, `colorSuccess`, `colorError`）

### P2-2: Chat 响应式侧边栏
- 桌面端（md+）：`<Sider width={280}>` 固定侧边栏
- 移动端（<md）：`<Drawer placement="left" width={280}>` + 汉堡菜单按钮
- 边框颜色 → `token.colorBorderSecondary`
- 选择对话后自动关闭 Drawer

### P2-3: 暗色模式颜色清理
- **Login 页面**：`background: '#f0f2f5'` → `token.colorBgLayout`，`color: '#ff4d4f'` → `token.colorError`
- **Dashboard**：所有 `#1677ff`, `#52c41a`, `#cf1322` → theme tokens
- **APM Dashboard**：硬编码颜色 → `themeToken.colorError/colorWarning/colorSuccess/colorPrimary`

---

## 五、Jaeger + Prometheus 可观测性集成

### 后端
- **`app/core/config.py`**：新增 `jaeger_ui_url`, `prometheus_ui_url` 配置字段
- **`app/api/health.py`**：新增 `GET /system/info` 端点
- **`app/core/otel.py`**：新增 Prometheus metrics ASGI app (`get_metrics_app()`)
- **`app/main.py`**：挂载 `/metrics` 端点
- **`pyproject.toml`**：OTel + prometheus-client 加入主依赖

### 前端
- **`services/systemService.ts`**：`SystemInfo` 接口 + API 调用
- **`hooks/useSystemQueries.ts`**：`useSystemInfo()` TanStack Query hook
- **`pages/apm/ApmDashboardPage.tsx`**：新增"可观测性集成"卡片
  - OTel 状态 Badge（启用/未启用）
  - Jaeger UI 跳转按钮
  - Prometheus UI 跳转按钮

### Docker 部署
- **`docker-compose.yml`**：
  - 后端加入 `1panel-network`（访问已有 Jaeger）
  - Prometheus 服务（`--profile otel`）端口 19090
  - 环境变量：`CKYCLAW_OTEL_ENABLED`, `CKYCLAW_JAEGER_UI_URL`, `CKYCLAW_PROMETHEUS_UI_URL`
- **`docker/prometheus.yml`**：Target 指向 `ckyclaw-backend:8000`

### 验证结果
| 服务 | 地址 | 状态 |
|------|------|------|
| 后端 API | `http://fn.cky:8080` | ✅ healthy |
| 前端 SPA | `http://fn.cky:3000` | ✅ 正常 |
| Jaeger UI | `http://fn.cky:16686` | ✅ 已接收 traces |
| Prometheus | `http://fn.cky:19090` | ✅ 指标采集正常 |
| `/metrics` | `http://fn.cky:8080/metrics/` | ✅ 有效 |
| `/system/info` | `http://fn.cky:8080/system/info` | ✅ OTel=true |

---

## 六、远程 Docker E2E 测试

**23/23 全部通过**

```
--- Auth ---
  [PASS] Health Check
  [PASS] Health Deep
  [PASS] Login
  [PASS] Get /me

--- Agent CRUD ---
  [PASS] Create Agent
  [PASS] List Agents
  [PASS] Get Agent
  [PASS] Update Agent

--- Provider ---
  [PASS] Create Provider
  [PASS] List Providers

--- Tool Groups ---
  [PASS] List Tool Groups

--- Templates ---
  [PASS] Seed Templates
  [PASS] List Templates (14)

--- Session ---
  [PASS] Create Session
  [PASS] Get Session
  [PASS] List Sessions

--- Traces / Token / Guardrails / Approvals ---
  [PASS] List Traces
  [PASS] Token Usage Summary
  [PASS] List Guardrails
  [PASS] List Approvals

--- Dashboard ---
  [PASS] APM Dashboard

--- Cleanup ---
  [PASS] Delete Agent

--- Frontend ---
  [PASS] Frontend index.html
```

---

## 七、修改文件清单

### 新增文件
| 文件 | 用途 |
|------|------|
| `frontend/src/constants/colors.ts` | 颜色常量统一 |
| `frontend/src/components/StatusTag.tsx` | 通用状态标签 |
| `frontend/src/components/ConfirmDeleteButton.tsx` | 删除确认按钮 |
| `frontend/src/components/PageCard.tsx` | 页面卡片容器 |
| `frontend/src/components/EmptyPlaceholder.tsx` | 空状态占位 |
| `frontend/src/components/SearchInput.tsx` | 搜索输入框 |
| `frontend/src/components/CrudTable.tsx` | 泛型 CRUD 表格 |
| `frontend/src/hooks/use*Queries.ts` (15+) | TanStack Query hooks |
| `frontend/src/services/systemService.ts` | System info API |
| `frontend/src/hooks/useSystemQueries.ts` | System info hook |

### 修改文件（关键部分）
- `backend/pyproject.toml` — OTel 依赖
- `backend/Dockerfile` — 恢复单步安装
- `backend/app/core/config.py` — jaeger_ui_url, prometheus_ui_url
- `backend/app/core/otel.py` — Prometheus metrics
- `backend/app/main.py` — /metrics 挂载
- `backend/app/api/health.py` — /system/info
- `docker-compose.yml` — OTel 网络、端口、环境变量
- `docker/prometheus.yml` — target 容器名
- `frontend/src/pages/**/*.tsx` — 约 30+ 页面文件
- `frontend/src/__tests__/**/*.test.tsx` — 4 个测试文件修复

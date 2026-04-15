# CkyClaw 待办清单

> 从 `docs/todo.md` 提取的当前可操作待办项。  
> 已完成项归档于 `docs/todo.md`。  
> 最后更新：2026-04-16

---

## 一、未完成功能（Issue 系列）

| # | 问题 | 状态 | 说明 |
|---|------|:----:|------|
| 10 | 可视化搭建（Visual Builder）功能不完整 | 🔜 延后 | 交互设计未完成，暂不处理 |
| 12 | 工具路线决策：弱化 MCP，统一工具体系 | 📋 产品决策 | 需产品讨论后执行 |
| 14 | 模型厂商：自动同步模型功能 | ✅ 已完成 | "从厂商同步"按钮已在关联模型 Tab 中 |
| 21 | 工具组整体设计需重新规划 | 📋 产品决策 | spec/tool-group-redesign.md 有方案 |
| 22 | 成本路由 Provider 关联逻辑 | ✅ 已修复 | 后端默认 moderate，前端提示优化 |
| 23 | 创建 Agent 步骤拆分 | ✅ 已修复 | 步骤 3 拆分为工具配置 + 编排配置 |

---

## 二、技术债务

| # | 问题 | 优先级 | 说明 |
|---|------|:------:|------|
| D3 | 4 个 Framework 集成测试需 LLM Key | ⏭️ 已知 | CI 中 skip，非阻塞 |

---

## 三、文档任务

| # | 文档 | 优先级 | 状态 |
|---|------|:------:|:----:|
| 17 | 记忆管理功能文档 | P2 | ✅ [memory-management.md](../spec/memory-management.md) |
| 27 | graphify 知识库方案研究 | P2 | ✅ [graphify-knowledge-base-research.md](../spec/graphify-knowledge-base-research.md) |
| 28 | CLI 使用指南 | P2 | ✅ [ckyclaw-cli-guide.md](../ckyclaw-cli-guide.md) |
| 29 | docs 目录整理 + todo.md 迁移 | P3 | ✅ 本文件已更新 |

---

*迁移自 docs/todo.md · 原文件保留为历史归档*

---

## 一、未完成功能（F 系列）

> 2026-04-12 决策：F2/F10/F4 统一标记为"暂不处理（低优先级）"，后续按业务窗口再启动。

### F2: Kubernetes 部署（P1 — 生产就绪）

**状态**：❌ 暂不处理  
**前置**：Docker 镜像已有 Dockerfile，docker-compose 已就绪

| # | 交付物 | 状态 |
|---|--------|:----:|
| 1 | Helm Chart（backend/frontend/db/redis 四服务） | ⬜ |
| 2 | values.yaml（环境变量注入 + Secret 引用） | ⬜ |
| 3 | HPA 水平弹性（CPU/内存 + 自定义 metrics） | ⬜ |
| 4 | PDB（Pod Disruption Budget） | ⬜ |
| 5 | Ingress（Nginx/Traefik + TLS + 路径路由） | ⬜ |
| 6 | ConfigMap / Secret 管理 | ⬜ |
| 7 | Kustomize overlays（dev / staging / prod） | ⬜ |
| 8 | Health Check probes（liveness + readiness + startup） | ⬜ |
| 9 | 部署文档 | ⬜ |

### F10: SSO SAML 2.0（P2 — 企业能力）

**状态**：❌ 暂不处理  
**驱动**：企业客户准入门槛

| # | 交付物 | 状态 |
|---|--------|:----:|
| 1 | SAML 2.0 SP 实现 | ⬜ |
| 2 | IdP 元数据解析 + 证书管理 | ⬜ |
| 3 | SSO 登录流程：SP-Initiated + IdP-Initiated | ⬜ |
| 4 | SLO（Single Logout） | ⬜ |
| 5 | 属性映射（email/name/role → CkyClaw User） | ⬜ |
| 6 | 前端 SSO 按钮 + 回调页 | ⬜ |
| 7 | 对接测试（Azure AD / Okta / OneLogin） | ⬜ |

### F4: Agents SDK 兼容层（P3 — 最低优先级）

**状态**：❌ 暂不处理  
**风险**：OpenAI SDK 频繁迭代，维护成本高

| # | 交付物 | 状态 |
|---|--------|:----:|
| 1 | Adapter 类：SDK Agent → CkyClaw Agent 映射 | ⬜ |
| 2 | 工具转换：SDK function schema → FunctionTool | ⬜ |
| 3 | Handoff 映射：SDK transfer → CkyClaw Handoff | ⬜ |
| 4 | Runner 桥接：SDK Runner → CkyClaw Runner | ⬜ |
| 5 | 兼容性测试（SDK 示例直接运行） | ⬜ |

---

## 二、已知技术债

| # | 问题 | 优先级 | 说明 |
|---|------|:------:|------|
| D3 | 4 个 Framework 集成测试需 LLM Key | ⏭️ 已知 | CI 中 skip，非阻塞 |

---

## 三、待修复 Bug

### 3.1 Cost Router "无匹配 Provider" 问题

**优先级**：P1  
**根因**：ProviderEditPage 前端表单**缺少** `model_tier` 和 `capabilities` 字段 → 所有 Provider 默认 `moderate` 且 capabilities 为空 → CostRouter 能力过滤始终失败  
**详细分析**：[docs/spec/cost-router-analysis.md](../spec/cost-router-analysis.md)

| # | 修复项 | 状态 |
|---|--------|:----:|
| 1 | ProviderEditPage 添加 `model_tier` Select（5 档） | ⬜ |
| 2 | ProviderEditPage 添加 `capabilities` 多选 Select（5 标签） | ⬜ |
| 3 | Provider 列表页显示 tier 和 capabilities 标签 | ⬜ |
| 4 | 补充测试用例 | ⬜ |

### 3.2 前端测试失败（3 个）

| # | 测试文件 | 问题 | 状态 |
|---|----------|------|:----:|
| 1 | MarketplacePage.test.tsx | Mock 数据不完整 | ⬜ |
| 2 | MemoryPage.test.tsx | API Mock 缺失 | ⬜ |
| 3 | ProviderKeyRotation.test.tsx | 时间依赖 | ⬜ |

---

## 四、设计文档待产出

| # | 文档 | 优先级 | 状态 |
|---|------|:------:|:----:|
| 1 | Tool Group 重新设计方案 | P1 | ✅ [tool-group-redesign.md](../spec/tool-group-redesign.md) |
| 2 | Cost Router 分析报告 | P1 | ✅ [cost-router-analysis.md](../spec/cost-router-analysis.md) |
| 3 | 知识库 + graphify 研究 | P2 | ✅ [knowledge-base-graph-design.md §9](../spec/knowledge-base-graph-design.md) |
| 4 | Memory 管理功能文档 | P2 | ✅ [memory-management.md](../spec/memory-management.md) |
| 5 | CLI 使用指南 | P2 | ✅ [ckyclaw-cli-guide.md](../ckyclaw-cli-guide.md) |

---

## 五、优先级排序

| 排名 | 待办项 | 优先级 | 类别 |
|:----:|--------|:------:|------|
| 1 | Cost Router 前端修复 | **P1** | Bug 修复 |
| 2 | 3 个前端测试修复 | **P1** | 测试修复 |
| 3 | F2 Kubernetes 部署 | P1 | 新功能（暂不处理） |
| 4 | F10 SSO SAML 2.0 | P2 | 新功能（暂不处理） |
| 5 | F4 Agents SDK 兼容层 | P3 | 新功能（暂不处理） |

---

*迁移自 docs/todo.md · 原文件保留为历史归档*

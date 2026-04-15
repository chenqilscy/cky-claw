# CkyClaw 文档目录规范

## 目录结构

```
docs/
├── README.md                         ← 本文件：目录规范与导航索引
│
├── spec/                             ← 正式规格文档（PRD、设计文档、数据模型）
│   ├── CkyClaw PRD v2.0.md                    — 总纲（一~三章 + 附录 + 索引）
│   ├── CkyClaw PRD-Agent编排 v2.0.md          — 分册：四~六章
│   ├── CkyClaw PRD-企业能力 v2.0.md           — 分册：七~十章
│   ├── CkyClaw PRD-基础设施 v2.0.md           — 分册：十一~十五章
│   ├── CkyClaw Framework Design v2.0.md       — 框架设计
│   ├── CkyClaw API Design v1.2.md             — API 接口设计
│   ├── CkyClaw Application Design v1.2.md     — 应用层技术设计
│   ├── CkyClaw Data Model v1.3.md             — 数据模型设计
│   ├── CkyClaw Workflow Engine Design v1.0.md — 工作流引擎设计
│   ├── CkyClaw Rust 重写可行性分析 v1.0.md     — Rust 重写可行性分析
│   ├── CkyClaw 前端 UI 优化方案 v1.0.md        — 前端 UI 优化方案
│   ├── CkyClaw 演进方向分析 v1.0.md            — 演进方向分析
│   ├── system-architecture.md                  — 系统架构总览
│   ├── s1-context-engineering.md               — S1 上下文工程设计
│   ├── s2-memory-triclass.md                   — S2 记忆三分类设计
│   ├── F8-Prompt-Editor-Design.md              — F8 Prompt 模板编辑器设计
│   ├── F12-Environment-Management-Design.md    — F12 多环境管理设计
│   ├── knowledge-base-graph-design.md          — 知识库图谱方案 v1.0
│   ├── graphify-knowledge-base-research.md     — graphify 图谱知识库研究报告
│   ├── tool-group-redesign.md                  — 工具组方案重设计
│   ├── cost-router-analysis.md                 — 成本路由测试器分析
│   └── memory-management.md                    — 记忆管理功能文档
│
├── plan/                             ← 迭代计划、里程碑、进度追踪
│   ├── evolution-execution-plan.md   — 演进执行计划
│   ├── evolution-roadmap.md          — 演进路线图
│   ├── mvp-progress.md              — MVP 进度追踪
│   └── todo-list.md                 — 未完成项 & 技术债务追踪
│
├── bugs/                             ← 问题记录与修复日志
│   ├── 2026-04-13.md                — 04-13 问题单
│   ├── 2026-04-14.md                — 04-14 问题单
│   ├── 2026-04-15.MD                — 04-15 问题单
│   └── issue-list.md               — 综合问题清单
│
├── compare-report/                   ← 竞品对比报告
│   ├── Harness&Hermes Agent.md      — Harness & Hermes 深度分析
│   ├── harnees-ckyclaw.md           — Harness vs CkyClaw 对比
│   └── NextCrab vs CkyClaw 架构对比分析.md
│
├── references/                       ← 外部参考资料、技术调研
│   ├── codex-cli-architecture.md    — Codex CLI 架构分析
│   ├── competitive-analysis.md      — 竞品分析汇总
│   └── DeerFlow/                    — DeerFlow 参考资料
│
├── user-guide.md                     — 用户使用指南
├── ckyclaw-cli-guide.md             — CLI 命令行工具使用说明
├── deployment-guide.md               — 部署指南
├── disaster-recovery.md              — 灾难恢复方案
├── response-style.md                 — Agent 输出风格控制说明
├── api-validation.md                 — API 验证报告
├── f3-loki-operations.md            — Loki 日志运维手册
├── project-structure.md              — 项目目录结构说明
├── project-summary-report.md        — 项目总结报告
├── frontend-optimization-report.md  — 前端性能优化报告
└── todo.md                          → (待迁移至 plan/todo-list.md 后删除)
```

## 命名约定

### 规格文档（spec/）

**文件名格式：** `CkyClaw {模块名} v{主版本}.{次版本}.md`

| 规则 | 说明 |
|------|------|
| 前缀 | 统一使用 `CkyClaw` |
| 模块名 | 英文，首字母大写：`PRD`、`Framework Design`、`API Design`、`Application Design`、`Data Model` |
| 版本号 | 文件名中使用 **主版本.次版本**（如 `v2.0`、`v1.3`），与文档内部 `major.minor.patch` 的前两位对齐 |
| 后缀 | `.md`（Markdown） |

**版本同步规则：**
- 文档内部 `| 版本 | v1.3.0 |` 头表和 `*文档版本：v1.3.0*` 尾部 **必须一致**
- 文件名版本 = 内部版本的 `major.minor`（如内部 `v1.3.0` → 文件名 `v1.3`）
- 当 `minor` 版本变更时，重命名文件并更新所有交叉引用
- 当仅 `patch` 版本变更时，不需要重命名文件

### 交叉引用格式

文档间引用使用书名号 + 中文文档名 + 版本号：

```
详见《CkyClaw 数据模型详细设计 v1.3》第三章。
详见《CkyClaw Framework Design v2.0》4.5 节。
```

**中英文映射：**

| 文件名模块 | 交叉引用名 |
|-----------|-----------|
| PRD | CkyClaw PRD |
| Framework Design | CkyClaw Framework Design |
| API Design | CkyClaw API 接口设计 |
| Application Design | CkyClaw 应用层技术设计方案 |
| Data Model | CkyClaw 数据模型详细设计 |

### 参考文档（references/）

- 文件名使用 kebab-case：`competitive-analysis.md`
- 子目录按来源分组：`DeerFlow/`、`OpenAI/` 等
- 不需要版本号

### 计划文档（plan/）

- 文件名格式：`sprint-{N}.md`、`milestone-{name}.md`
- 按时间维度组织

## 当前文档清单

### 规格文档（spec/）

| 文档 | 文件名 | 内部版本 |
|------|--------|---------|
| 产品需求文档（总纲） | CkyClaw PRD v2.0.md | v2.0.9 |
| PRD-Agent 编排分册 | CkyClaw PRD-Agent编排 v2.0.md | v2.0.8 |
| PRD-企业能力分册 | CkyClaw PRD-企业能力 v2.0.md | v2.0.8 |
| PRD-基础设施分册 | CkyClaw PRD-基础设施 v2.0.md | v2.0.8 |
| 框架设计 | CkyClaw Framework Design v2.0.md | v2.0.0 |
| API 接口设计 | CkyClaw API Design v1.2.md | v1.2.0 |
| 应用层技术设计 | CkyClaw Application Design v1.2.md | v1.2.0 |
| 数据模型详细设计 | CkyClaw Data Model v1.3.md | v1.3.0 |
| 工作流引擎设计 | CkyClaw Workflow Engine Design v1.0.md | v1.0.0 |
| 系统架构总览 | system-architecture.md | — |
| 知识库图谱方案 | knowledge-base-graph-design.md | v1.0 |
| 工具组方案重设计 | tool-group-redesign.md | v1.0 |
| 成本路由分析 | cost-router-analysis.md | v1.0 |
| 记忆管理文档 | memory-management.md | v1.0 |

### 运维与指南文档

| 文档 | 文件名 | 说明 |
|------|--------|------|
| 用户指南 | user-guide.md | 平台使用手册 |
| CLI 使用说明 | ckyclaw-cli-guide.md | 命令行工具使用指南 |
| 部署指南 | deployment-guide.md | Docker Compose 部署手册 |
| 灾难恢复 | disaster-recovery.md | 备份与恢复方案 |
| Loki 运维手册 | f3-loki-operations.md | 日志聚合运维 |
| API 验证报告 | api-validation.md | 全链路 API 验证 |

### 分析与报告文档

| 文档 | 文件名 | 说明 |
|------|--------|------|
| 项目总结报告 | project-summary-report.md | 项目整体总结 |
| 前端优化报告 | frontend-optimization-report.md | 前端性能分析报告 |
| Rust 重写分析 | CkyClaw Rust 重写可行性分析 v1.0.md | Rust 重写可行性评估 |
| 演进方向分析 | CkyClaw 演进方向分析 v1.0.md | 项目演进战略 |

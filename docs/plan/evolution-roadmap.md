# CkyClaw 演进路线图

> 基于 Harness 理论、NextCrab 工程实践、Hermes Agent 自改进框架三份对比报告，结合 CkyClaw 现有能力矩阵，制定分阶段演进计划。
>
> 创建日期：2026-04-11 · 版本 v1.0.0

---

## 〇、核心定位（不动摇）

CkyClaw 定位为 **Python 生态 AI Agent 管理与运行平台**，面向中国企业 AI 团队。以下四项是核心竞争力，必须持续加固：

| 优势 | 当前状态 | 竞品对比 |
|------|---------|---------|
| **Python 生态 + LiteLLM 多厂商** | 10+ Provider 原生适配 | Hermes 仅 OpenRouter，NextCrab 独立生态 |
| **三阶段护栏体系** | Input/Output/Tool × 7 种内置 | 比 Hermes Prompt 约束、NextCrab ConfirmPolicy 更系统化 |
| **声明式 Agent 定义** | @dataclass + InstructionsType | 比 Hermes/NextCrab 更简洁 |
| **完整企业能力** | RBAC + 多租户 + OAuth + IM 6 渠道 + 审计 | 竞品无此完整度 |

---

## 一、Gap 分析：三份报告综合诊断

### 1.1 关键能力差距矩阵

| 能力域 | Harness 理论 | NextCrab 实践 | Hermes 特色 | CkyClaw 现状 | 差距等级 |
|--------|:----------:|:----------:|:----------:|:----------:|:------:|
| **上下文压缩** | 5 Tier Cache-First | 5 层压缩管道 | FTS5 Session Search | HistoryTrimmer 2 策略 | 🔴 大 |
| **Artifact 外部化** | Tier 1 核心策略 | 内置文件操作 | 无 | 无 | 🔴 大 |
| **记忆系统** | 文件系统交接 | Soul 三类记忆+成长 | 三类记忆+Skill Factory | 单一 MemoryEntry | 🔴 大 |
| **事件溯源/重放** | Append-only Event Log | Event Journal+Replay | 内置 logging | Trace/Span（无重放） | 🟡 中 |
| **LLM 容错** | — | Circuit Breaker+Fallback | OpenRouter 路由 | 单 Provider 指数退避 | 🟡 中 |
| **工具中间件** | — | ToolGateway 管道 | 工具热加载 | 无中间件概念 | 🟡 中 |
| **取消传播** | — | CancellationToken 级联 | 无 | 靠 max_turns | 🟡 中 |
| **自改进循环** | — | — | Learning Loop+Skill Factory | Evolution 骨架 | 🟡 中 |
| **多 Agent 智能编排** | 三 Agent 分离 | Brain Coordinator | 单 Agent | TeamRunner 3 协议 | 🟢 小 |
| **检查点恢复** | 核心要素 | Event Journal | 无 | Checkpoint 骨架存在 | 🟢 小 |

### 1.2 三份报告共同指向的 Top 5 优先方向

1. **上下文工程升级** — 三份报告都将上下文管理列为最大差距
2. **记忆系统三类化** — NextCrab Soul + Hermes 三类记忆 = 行业共识
3. **LLM 容错 + Circuit Breaker** — 生产环境必备
4. **事件溯源 + Replay** — 可观测性和调试的基础
5. **自改进闭环落地** — Evolution 从骨架到可用

---

## 二、演进路线图

### Phase 1：上下文工程革命（S1 — 2 周）

> **目标**：从 2 策略裁剪升级到 5 Tier 渐进式上下文管理，直接对齐 Harness 理论和 NextCrab 实践。

#### S1.1 — Tier 0-2：工具结果截断 + 延迟淘汰

| 子任务 | 模块 | 说明 |
|--------|------|------|
| **ToolResultBudget** | `runner/` | FunctionTool 新增 `max_result_chars`，超限截断 + 摘要尾部 |
| **大结果外部化（Artifact Store）** | 新模块 `artifacts/` | 工具返回 >8K token 时自动写入文件系统，上下文中只保留引用 ID + 摘要 |
| **延迟淘汰策略** | `session/history_trimmer.py` | 新增 `PROGRESSIVE` 策略：上下文 80% 时淘汰旧工具结果，90% 时淘汰旧用户消息 |

#### S1.2 — Tier 3-4：LLM 摘要压缩 + 全新窗口

| 子任务 | 模块 | 说明 |
|--------|------|------|
| **SUMMARY_PREFIX 实现** | `session/history_trimmer.py` | 调用 LLM 生成历史摘要，作为 system 消息前缀注入 |
| **Fresh Restart 决策器** | `runner/` | 当外部状态充分（Checkpoint + Artifact Store 有数据）时，自动开启全新窗口 |
| **Cache-First Prompt 布局** | `runner/runner.py` | 固定 System Prompt 前缀（instructions + guardrails），追加式历史，禁止动态改写前缀 |

**验收标准**：
- 上下文压缩有 5 层渐进策略，按代价递增自动触发
- 大工具输出不再淹没上下文窗口
- Token 消耗下降 30%+（通过 Artifact 外部化）

---

### Phase 2：记忆系统三类化（S2 — 2 周）

> **目标**：从单一 MemoryEntry 升级为 Episodic / Semantic / Procedural 三类记忆，对齐 Hermes 和 NextCrab，为后续 Learning Loop 打基础。

#### S2.1 — 三类记忆存储

| 记忆类型 | 存储内容 | 检索方式 | 实现要点 |
|----------|---------|---------|---------|
| **Episodic（情景）** | 完整交互事件（按 Session 组织） | 全文搜索（FTS5 或 PostgreSQL tsvector） | 复用现有 Session 数据，新增搜索索引 |
| **Semantic（语义）** | 提取的知识/事实 | 关键词 + 可选向量召回 | 升级 MemoryEntry，新增 embedding 字段 |
| **Procedural（程序性）** | Agent 自创的模式/提示词/工具配置 | 名称 + 标签 | 复用 Skill 系统，新增 auto-created 标记 |

#### S2.2 — 记忆注入管线

| 子任务 | 说明 |
|--------|------|
| **MemoryInjector** | Runner 调用 LLM 前，自动检索相关记忆注入 system 消息 |
| **记忆提取 Hook 增强** | `on_run_end` 时自动分类提取三类记忆 |
| **记忆衰减 + 容量管理** | 参考 NextCrab 每日衰减 0.98 + 容量上限 + 归档 |
| **跨会话检索 API** | Backend 新增 `/api/v1/memories/search` 全文+语义联合检索 |

**验收标准**：
- Agent 可自动积累三类记忆
- 跨会话对话时 Agent 能引用历史知识
- 前端 Memory 页面展示三类记忆并支持搜索

---

### Phase 3：LLM 容错 + 工具中间件（S3 — 1.5 周）

> **目标**：生产级 LLM 调用容错 + 工具执行管道化。

#### S3.1 — Circuit Breaker + Fallback Chain

| 子任务 | 模块 | 说明 |
|--------|------|------|
| **CircuitBreaker** | `model/circuit_breaker.py` | 三种状态（Closed/Open/HalfOpen）+ 可配置阈值 |
| **FallbackChain** | `model/fallback.py` | Provider 级降级链：主 Provider → 备用 Provider → 最小模型 |
| **健康探测** | `model/` | 后台异步探测 Provider 健康状态，自动恢复 |

#### S3.2 — ToolGateway 中间件管道

| 子任务 | 模块 | 说明 |
|--------|------|------|
| **ToolMiddleware 抽象** | `tools/middleware.py` | `before_execute` / `after_execute` 异步钩子 |
| **内置中间件** | `tools/` | AuthMiddleware（权限）、CacheMiddleware（结果缓存）、LoopGuardMiddleware（循环检测）、TimeoutMiddleware |
| **中间件管道** | `tools/pipeline.py` | 可插拔管道，按序执行中间件 → 工具 → 逆序后处理 |

**验收标准**：
- Provider 异常时 <1s 自动切换到备用
- 工具执行有统一的权限检查、缓存、循环检测
- Circuit Breaker 状态在 APM Dashboard 可视化

---

### Phase 4：事件溯源 + Replay（S4 — 1.5 周）

> **目标**：所有 Agent 操作持久化为事件日志，支持审计和调试回放。

#### S4.1 — Event Journal

| 子任务 | 模块 | 说明 |
|--------|------|------|
| **EventJournal** | 新模块 `events/` | 全局递增序列号 + 事件类型 + payload + 时间戳 |
| **事件类型**（15+） | `events/types.py` | AGENT_START/END, LLM_CALL, TOOL_CALL, HANDOFF, GUARDRAIL_CHECK, APPROVAL_REQUEST, CHECKPOINT, ERROR, ... |
| **Projector 模式** | `events/projector.py` | 事件订阅者：CostProjector、AuditProjector、MetricsProjector |
| **PostgreSQL 持久化** | `events/postgres.py` | 按 run_id / session_id 索引，支持批量写入 |

#### S4.2 — Replay 能力

| 子任务 | 说明 |
|--------|------|
| **事件回放 API** | Backend `GET /api/v1/runs/{id}/replay` 按时间序返回事件流 |
| **前端回放 Timeline** | 复用现有 SpanWaterfall + 新增事件粒度回放控件 |
| **断点恢复** | 从 Event Journal 任意事件点恢复执行 |

**验收标准**：
- 任何一次 Agent 运行都可完整重放
- 事件日志支持审计查询（按时间/类型/Agent/User）
- 前端可视化回放运行过程

---

### Phase 5：自改进闭环（S5 — 2 周）

> **目标**：Evolution 从骨架升级到可运行闭环，增加 Learning Loop 和 Skill Factory 能力。

#### S5.1 — Evolution 策略引擎完善

| 子任务 | 说明 |
|--------|------|
| **LLM 推理层** | 策略引擎调用 LLM 生成具体 instructions 优化建议 |
| **A/B 评估** | 新旧配置 A/B 对比运行，基于评分差异决定是否采纳 |
| **自动回滚监控** | 后台监控 applied 提案的评分变化，低于阈值自动回滚 |
| **冷却与限频** | cooldown_hours + max_proposals_per_cycle 严格执行 |

#### S5.2 — Learning Loop（参考 Hermes）

| 子任务 | 说明 |
|--------|------|
| **反思 Hook** | `on_run_end` 后 Agent 自动评估本次执行质量 |
| **模式提取** | 从成功案例中提取可复用模式，存入 Procedural Memory |
| **Skill Factory** | Agent 可自主创建新的 Skill 条目（知识包），经审批后注册到 SkillRegistry |
| **安全门** | Agent 创建的 Skill 必须经过 Guardrail 审核 + 人工审批 |

**验收标准**：
- Agent 运行后自动生成优化建议
- 高频成功模式自动沉淀为 Skill
- 优化建议经 A/B 测试验证后自动应用

---

### Phase 6：取消传播 + Checkpoint 自动恢复（S6 — 1 周）

> **目标**：多层级联取消 + 从 Checkpoint 自动恢复执行。

| 子任务 | 模块 | 说明 |
|--------|------|------|
| **CancellationToken** | `runner/cancellation.py` | 层级化取消令牌：Parent → Child 级联传播 |
| **Runner 集成** | `runner/runner.py` | 每次 LLM 调用 / 工具执行前检查 Token 状态 |
| **TeamRunner 集成** | `team/team_runner.py` | 协调者取消时级联取消所有成员 |
| **Checkpoint 自动恢复** | `runner/runner.py` | `Runner.run()` 接收 `resume_from_checkpoint` 参数，自动加载状态继续 |
| **PostgresCheckpointBackend** | `checkpoint/` | 完善 Postgres 实现 |

**验收标准**：
- 取消操作 <100ms 传播到所有子任务
- 崩溃后可从最近 Checkpoint 恢复执行

---

### Phase 7：智能编排升级（S7 — 2 周）

> **目标**：从手动配置升级到 LLM 驱动的自适应编排。

#### S7.1 — Brain Coordinator 模式

| 子任务 | 说明 |
|--------|------|
| **PlanningAgent** | 接收任务后生成 JSON 格式的结构化计划（特性列表 + 依赖 + 验收标准） |
| **自适应策略** | Coordinator 根据任务特征自动选择 Sequential / Parallel / Pipeline |
| **PlanGuard** | 验证计划合理性：依赖无环、预估 Token 不超限、成员能力匹配 |

#### S7.2 — Agent 间持久化通信

| 子任务 | 说明 |
|--------|------|
| **Mailbox** | DB-backed Agent 间消息队列，支持崩溃恢复 |
| **结构化 Handoff 文档** | 跨会话交接标准化：当前状态 + 变更内容 + 已验证项 + 失败原因 + 下一步 |

**验收标准**：
- Coordinator 可自主决定编排策略
- Agent 间通信可追溯、可恢复

---

## 三、优先级排序与时间线

```
2026-04                          2026-05                          2026-06
├─ S1: 上下文工程 ──────────┤
│  (2 周)                   ├─ S3: LLM 容错 ────────┤
├─ S2: 记忆三类化 ─────────┤│  (1.5 周)              ├─ S5: 自改进闭环 ──────────┤
│  (2 周)                   ├─ S4: 事件溯源 ────────┤│  (2 周)                   │
│                           │  (1.5 周)              ├─ S6: 取消+恢复 ────┤      │
│                           │                        │  (1 周)             │      │
│                           │                        │                     ├─ S7: 智能编排 ──────────┤
│                           │                        │                     │  (2 周)                  │
```

### 版本里程碑映射

| 版本 | Phase | 核心交付 |
|------|-------|---------|
| **v3.0** | S1 上下文工程 | 5 Tier 压缩 + Artifact Store + Cache-First Prompt |
| **v3.1** | S2 记忆三类化 | Episodic/Semantic/Procedural + 跨会话检索 |
| **v3.2** | S3 + S4 | Circuit Breaker + ToolMiddleware + Event Journal + Replay |
| **v3.3** | S5 + S6 | Learning Loop + Skill Factory + CancellationToken + Checkpoint 恢复 |
| **v3.4** | S7 | Brain Coordinator + PlanGuard + Mailbox |

---

## 四、技术选型补充

| 新增需求 | 推荐方案 | 理由 |
|---------|---------|------|
| 全文搜索（Episodic 记忆） | PostgreSQL `tsvector` + `GIN` 索引 | 无需引入新依赖，已有 PG |
| 向量检索（Semantic 记忆） | `pgvector` 扩展 | 轻量，不引入新服务 |
| Artifact Store | 本地文件系统 → S3 兼容 API | 先简后丰，MVP 用本地 |
| Event Journal 存储 | PostgreSQL + 按月分区 | 复用现有基础设施 |
| Circuit Breaker | 自研（<200 行） | 避免引入重依赖 |

---

## 五、风险与缓解

| 风险 | 概率 | 影响 | 缓解措施 |
|------|:----:|:----:|---------|
| SUMMARY_PREFIX LLM 调用增加成本 | 高 | 中 | 仅在 Tier 3 触发，设置调用频率限制 |
| Artifact Store 增加存储复杂度 | 中 | 低 | 先用本地文件系统，GC 策略定期清理 |
| Event Journal 写入性能 | 中 | 中 | 批量异步写入 + 按月分区 |
| Skill Factory 安全风险 | 高 | 高 | Agent 创建的 Skill 必须经 Guardrail + 人工审批 |
| Circuit Breaker 误触发 | 中 | 高 | 保守阈值 + HalfOpen 探测 + Dashboard 告警 |

---

## 六、定位守卫验证

每个 Phase 的 PM 验证：

| Phase | AI 场景相关 | 差异化价值 | 用户需求 | 优先级 |
|-------|:----------:|:--------:|:-------:|:-----:|
| S1 上下文工程 | ✅ Agent 长时运行核心 | ✅ 5 Tier 压缩业界领先 | ✅ Token 成本敏感 | **P0** |
| S2 记忆三类化 | ✅ Agent 认知基础 | ✅ 程序性记忆独特 | ✅ 企业知识沉淀 | **P0** |
| S3 LLM 容错 | ✅ 生产稳定性 | ⚠️ 基础能力 | ✅ 国产模型不稳定 | **P1** |
| S4 事件溯源 | ✅ 可观测性核心 | ✅ 回放是调试利器 | ✅ 审计合规 | **P1** |
| S5 自改进 | ✅ Agent 演化核心 | ✅ 自改进差异化 | ⚠️ 高级用户 | **P1** |
| S6 取消+恢复 | ✅ 长时运行基础 | ⚠️ 基础能力 | ✅ 崩溃恢复刚需 | **P1** |
| S7 智能编排 | ✅ 多 Agent 场景 | ✅ LLM 驱动编排 | ⚠️ 高级用户 | **P2** |

---

## 七、与竞品的目标差距对比

完成全部 7 个 Phase 后的 CkyClaw 能力预期：

| 维度 | 当前 CkyClaw | 完成后 CkyClaw | NextCrab | Hermes |
|------|:----------:|:------------:|:-------:|:-----:|
| 上下文管理 | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |
| 记忆系统 | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| LLM 容错 | ⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ |
| 可观测性 | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ |
| 自改进 | ⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ |
| 多 Agent | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ |
| 护栏/安全 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ |
| 企业能力 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐ |

**最终定位**：**上下文工程 + 企业级治理 + 自改进** 三位一体的 Python Agent 平台。

---

## 八、附录：对比报告索引

| 报告 | 路径 | 核心发现 |
|------|------|---------|
| Harness 理论 + CkyClaw 映射 | `docs/compare-report/harnees-ckyclaw.md` | 5 层架构 + Cache-First + 反模式 |
| NextCrab vs CkyClaw 深度对比 | `docs/compare-report/NextCrab vs CkyClaw 架构对比分析.md` | 10 项可借鉴方向 |
| Agent Harness + Hermes + 四平台 | `docs/compare-report/Harness&Hermes Agent.md` | 自改进循环 + 三类记忆 + 短中长期建议 |

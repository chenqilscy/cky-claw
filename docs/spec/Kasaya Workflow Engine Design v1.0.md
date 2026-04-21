# 工作流引擎 — 通过 DAG 编排智能体

> **版本**: v1.0（审查修订版）
> **审查修复**: 2 Critical + 12 Major + 8 Minor，共 22 项

## Context

Kasaya 当前仅有两种 Agent 编排模式：**Handoff**（LLM 驱动的 Agent 间交接）和 **Agent-as-Tool**（LLM 决定何时调用子 Agent）。两者都依赖 LLM 自主决策，无法实现确定性的程序化编排（顺序链、并行扇出/扇入、条件分支、循环迭代）。

本方案在 Kasaya Framework 中新增 **Workflow Engine**，提供声明式 DAG 编排能力，后端提供持久化和 REST API，前端提供可视化拖拽编辑器。

## 数据流设计

**底层机制**：共享 context dict（键值对），所有步骤从中读取输入、写入输出。

**分层便捷**：
- **简单场景（默认）**：AgentStep 的文本输出自动存入 `context["<step_id>_output"]`（值为字符串），下游步骤通过 `{{step_id_output}}` 在 prompt 模板中引用。无需手动配置映射。
- **高级场景**：显式指定 `io.input_keys` / `io.output_keys` 做精确映射，支持并行结果汇聚到不同 key、条件分支基于指定 key 判断。
- **结构化输出**：若 Agent 配置了 `output_type`（Pydantic BaseModel），引擎自动将结构化字段展开为 dict 写入 context，条件表达式可直接引用字段路径（如 `{{analysis_output.sentiment}}`）。
- **并行隔离**：ParallelStep 的子步骤按各自的 `step_id_output` 写入不同 key，不存在冲突。验证器拒绝显式映射到相同 output_key 的并行子步骤。

## 数据模型

### Framework 层 — `kasaya-framework/kasaya/workflow/`

**step.py** — 步骤定义

```python
class StepType(str, Enum):
    AGENT = "agent"              # 执行一个 Agent
    PARALLEL = "parallel"        # 并行执行子步骤
    CONDITIONAL = "conditional"  # 条件分支路由
    LOOP = "loop"                # 循环迭代

class StepStatus(str, Enum):
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"

@dataclass
class StepIO:
    input_keys: dict[str, str]    # context_key -> 步骤内参数名
    output_keys: dict[str, str]   # 结果字段名 -> context_key

@dataclass
class RetryConfig:
    max_retries: int = 2
    delay_seconds: float = 1.0
    backoff_multiplier: float = 2.0

@dataclass
class Step:                       # 基类
    id: str                       # 工作流内唯一
    name: str = ""
    type: StepType = StepType.AGENT
    io: StepIO = field(default_factory=StepIO)
    retry_config: RetryConfig | None = None
    timeout: float | None = None  # 单步骤超时（秒）

@dataclass
class AgentStep(Step):
    agent_name: str = ""          # 运行时通过 agent_resolver 解析
    prompt_template: str = ""     # 支持 {{key}} 插值
    max_turns: int = 10

@dataclass
class ParallelStep(Step):
    # 允许的子步骤类型：AgentStep, ConditionalStep（不允许嵌套 ParallelStep 或 LoopStep）
    sub_steps: list[AgentStep | ConditionalStep] = field(default_factory=list)
    fail_policy: str = "fail_fast"  # "fail_fast" | "collect_all"

@dataclass
class BranchCondition:
    label: str
    condition: str                # 安全表达式：key == 'value'
    target_step_id: str

@dataclass
class ConditionalStep(Step):
    branches: list[BranchCondition] = field(default_factory=list)
    default_step_id: str | None = None
    # 分支路由由 branches 独占定义，出边（edges）仅用于 DAG 拓扑结构和可视化。
    # 运行时路由由 branches[].target_step_id 决定，不在 edges.condition 上重复定义。

@dataclass
class LoopStep(Step):
    # body_steps 按列表顺序**顺序执行**（非子 DAG，不需要 body_edges）
    body_steps: list[AgentStep | ConditionalStep] = field(default_factory=list)
    condition: str = ""           # 循环条件（求值为真则继续）
    max_iterations: int = 10      # 最大迭代次数保护
    iteration_output_key: str = ""  # 迭代结果追加到此 key（list）
```

**嵌套规则**（Fix #3.1）：
- ParallelStep.sub_steps：允许 AgentStep、ConditionalStep（不允许嵌套 ParallelStep 或 LoopStep）
- LoopStep.body_steps：允许 AgentStep、ConditionalStep（不允许嵌套 LoopStep 或 ParallelStep）
- ConditionalStep 分支仅路由到顶层 steps（不路由到其他容器的内部步骤）

**workflow.py** — 工作流定义

```python
@dataclass
class Edge:
    id: str
    source_step_id: str
    target_step_id: str
    # Edge 不含 condition 字段。条件路由由 ConditionalStep.branches 独占控制。
    # Edge 仅表示 DAG 拓扑结构（数据流方向）和可视化连线。

@dataclass
class Workflow:
    name: str
    description: str = ""
    steps: list[Step] = field(default_factory=list)
    edges: list[Edge] = field(default_factory=list)
    input_schema: dict[str, Any] = field(default_factory=dict)   # JSON Schema，执行前验证
    output_keys: list[str] = field(default_factory=list)          # 最终返回的 context key
    metadata: dict[str, Any] = field(default_factory=dict)
    timeout: float | None = None  # 整体超时（秒），None 表示不限制
```

**result.py** — 执行结果

```python
class WorkflowStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

@dataclass
class StepResult:
    step_id: str
    status: StepStatus              # 使用枚举，非裸字符串
    output: dict[str, Any]
    error: str | None
    started_at: datetime | None
    finished_at: datetime | None
    duration_ms: int | None

@dataclass
class WorkflowResult:
    workflow_name: str
    status: WorkflowStatus
    context: dict[str, Any]          # 最终上下文快照
    step_results: dict[str, StepResult]
    trace: Trace | None
    started_at: datetime | None
    finished_at: datetime | None
    duration_ms: int | None
    error: str | None
```

**config.py** — 工作流运行配置

```python
@dataclass
class WorkflowRunConfig:
    """工作流级别运行配置，包装并传递 RunConfig 字段到每个 AgentStep。"""
    # 转发给每个 AgentStep 的 Runner.run() 调用
    model_provider: ModelProvider | None = None
    tool_timeout: float | None = None
    # 工作流级别设置
    workflow_timeout: float | None = None    # 覆盖 Workflow.timeout
    fail_fast: bool = True                   # 遇错即停 vs 尽力完成
    tracing_enabled: bool = True
```

### Backend ORM — `backend/app/models/workflow.py`

**workflow_definitions 表**：
- `id` UUID PK, `name` String(64) unique indexed, `description` Text
- `steps` JSONB, `edges` JSONB, `input_schema` JSONB
- `output_keys` ARRAY(String), `metadata_` JSONB
- `version` Integer default 1（每次更新 +1，旧版本仍可通过 execution 的 snapshot 追溯）
- `is_active` Boolean default true
- `created_by` UUID nullable, `created_at` / `updated_at` DateTime tz

> **设计决策**：Workflow 使用 inline version（version 字段自增），不采用 Agent 的独立版本表模式。
> 原因：Agent 版本表支持 diff 和 rollback，是面向频繁迭代的核心资产。Workflow 定义变更频率低，
> 且 `workflow_executions.workflow_snapshot` 已保存执行时的定义快照，满足审计需求。
> 若未来需要 diff/rollback 功能，再引入 `workflow_definition_versions` 表。

**workflow_executions 表**：
- `id` UUID PK, `workflow_name` String(64) indexed, `workflow_version` Integer
- `status` String(16), `input_context` JSONB, `output_context` JSONB
- `step_results` JSONB, `error` Text nullable
- `workflow_snapshot` JSONB — 执行时的 workflow 定义快照（steps + edges），确保版本更新后仍可追溯
- `trace_id` String(64) nullable indexed
- `idempotency_key` String(128) nullable unique indexed — 幂等键，防止重复提交
- `started_at` / `finished_at` DateTime tz, `duration_ms` Integer nullable
- `created_by` UUID nullable, `created_at` DateTime tz

**TraceRecord 扩展**：在 `traces` 表的 `metadata_` JSONB 中新增 `workflow_execution_id` 字段，关联工作流执行。`workflow_name` 字段直接存储 Workflow.name，语义从"自由标签"变为"工作流实体引用"。

遵循现有模式：Mapped[]/mapped_column 风格，name-based 引用，JSONB 存灵活配置。

## 引擎执行算法

文件：`kasaya-framework/kasaya/workflow/engine.py`

```
WorkflowEngine.run(workflow, context, *, agent_resolver, config, cancel_event)
│
├─ 1. 验证
│   ├─ DAG 结构验证（Kahn 拓扑排序、环检测、孤立边检测）
│   ├─ 嵌套规则验证（Parallel/Loop 内部不允许的步骤类型）
│   ├─ 并行 output_key 冲突检测
│   └─ input_schema 验证（若定义了 JSON Schema，对 context 校验）
│
├─ 2. 初始化
│   ├─ context dict（合并用户输入 + 默认值）
│   ├─ 创建 Trace（workflow_name = workflow.name）
│   └─ 记录 start_time
│
├─ 3. 就绪队列驱动执行（Fix #4.1：不用分层，用 ready-queue）
│   │
│   │  初始化：in_degree 计数器（每个步骤 = 入边数量）
│   │  就绪队列 = [in_degree == 0 的步骤]
│   │  skipped_set = {}  // 被条件跳过的步骤
│   │
│   ├─ while 就绪队列非空:
│   │   ├─ 从就绪队列取出所有就绪步骤
│   │   ├─ 过滤掉 skipped_set 中的步骤
│   │   ├─ 若多个就绪步骤 → asyncio.TaskGroup 并行执行
│   │   ├─ 若单个就绪步骤 → 直接执行
│   │   │
│   │   ├─ 每个步骤完成后（按 type 分发）：
│   │   │
│   │   │   ├─ AgentStep:
│   │   │   │   ├─ 检查 cancel_event（Fix #4.2）
│   │   │   │   ├─ 渲染 prompt_template（{{key}} → context[key]）
│   │   │   │   ├─ await agent_resolver(name) 获取 Agent（Fix #1.5：异步解析）
│   │   │   │   ├─ 构建 RunConfig（Fix #1.2/5.6）：
│   │   │   │   │   workflow_name = workflow.name
│   │   │   │   │   tracing_enabled = False（Fix #2.3：不在 Runner 内建 Trace）
│   │   │   │   │   model_provider = config.model_provider
│   │   │   │   │   tool_timeout = config.tool_timeout
│   │   │   │   ├─ Runner.run(agent=resolved, input=rendered_prompt,
│   │   │   │   │             config=run_config, context=context,
│   │   │   │   │             max_turns=step.max_turns)（Fix #1.1：正确的关键字参数）
│   │   │   │   ├─ 提取输出写入 context：
│   │   │   │   │   默认：context[f"{step_id}_output"] = run_result.output (str)
│   │   │   │   │   结构化输出：展开 output_type 字段到 context
│   │   │   │   │   显式映射：按 io.output_keys 写入
│   │   │   │   └─ 创建 WORKFLOW_STEP Span（Fix #1.3）：
│   │   │   │       name = step.id, metadata = {"step_type": step.type.value}
│   │   │   │
│   │   │   ├─ ParallelStep:
│   │   │   │   ├─ 按顺序执行 sub_steps（顺序，非并行——子步骤可能共享 context）
│   │   │   │   │   （注：sub_steps 内部的并行由 DAG edges 定义，在顶层 ready-queue 中处理）
│   │   │   │   ├─ fail_policy（Fix #4.4）：
│   │   │   │   │   "fail_fast" → 首个失败立即中断，标记 ParallelStep 为 FAILED
│   │   │   │   │   "collect_all" → 全部执行，成功的写入 context，失败的记录 error
│   │   │   │   └─ 合并子步骤输出到 context
│   │   │   │
│   │   │   ├─ ConditionalStep:
│   │   │   │   ├─ 按 branches 顺序求值条件（Fix #3.2：由 branches 独占）
│   │   │   │   ├─ 首个匹配的 branch → 标记 target_step_id 为"应执行"
│   │   │   │   ├─ 其他 branch 的 target_step_id 及其所有下游 → 加入 skipped_set
│   │   │   │   └─ 若无匹配且有 default_step_id → 执行 default
│   │   │   │
│   │   │   └─ LoopStep:
│   │   │       ├─ iteration = 0
│   │   │       ├─ while evaluate(condition, context) 为真 且 iteration < max_iterations:
│   │   │       │   ├─ 检查 cancel_event
│   │   │       │   ├─ 顺序执行 body_steps（Fix #3.3：顺序，非子 DAG）
│   │   │       │   ├─ 追加本次迭代结果到 context[iteration_output_key]（list）
│   │   │       │   └─ iteration += 1
│   │   │       └─ 记录 StepResult 含 iteration_count
│   │   │
│   │   └─ 步骤完成后更新就绪队列：
│   │       for edge in outgoing_edges(step):
│   │           target = edge.target_step_id
│   │           if target not in skipped_set:
│   │               decrement in_degree[target]
│   │               if in_degree[target] == 0:
│   │                   add to ready queue
│   │
│   ├─ 4. 错误处理
│   │   ├─ retry_config：指数退避重试（retry → 重新执行该步骤）
│   │   ├─ 重试耗尽：标记 StepResult.status = FAILED
│   │   └─ config.fail_fast=True → 抛出异常终止工作流
│   │
│   ├─ 5. 取消处理（Fix #4.2）
│   │   ├─ 每个步骤执行前检查 cancel_event.is_set()
│   │   ├─ 若已取消：抛出 WorkflowCancelledError
│   │   ├─ 引擎捕获：标记 WorkflowResult.status = CANCELLED
│   │   └─ 已完成步骤的结果保留在 step_results 中
│   │
│   ├─ 6. 超时处理（Fix #5.4）
│   │   ├─ asyncio.wait_for(engine_loop, timeout=effective_timeout)
│   │   └─ 超时 → 标记 WorkflowResult.status = FAILED, error = "timeout"
│   │
│   └─ 7. 收集结果
│       ├─ 最终 context 快照
│       ├─ 按 output_keys 过滤返回
│       └─ 结束 Trace，记录 duration_ms
```

**agent_resolver 回调签名**（Fix #1.5）：

```python
async def agent_resolver(name: str) -> Agent:
    """异步解析 Agent 名称到完整的 Framework Agent 实例。

    后端实现需完成：加载 AgentConfig → 解析 guardrails → 解析 handoffs
    → 连接 MCP servers → 加载 tool groups → 构建 Agent 实例。
    与 session 执行中的 _build_agent_from_config() 逻辑相同。
    建议提取为共享的 agent_resolver.py 服务。
    """
```

**条件表达式求值**（evaluator.py）：使用 Python `ast` 模块解析，仅允许比较运算（==, !=, >, <, >=, <=）和布尔运算（and, or, not），禁止函数调用、import、属性访问、下标访问之外的复杂表达式。支持 dict key 路径查找（如 `analysis_output.sentiment` → context 嵌套查找）。安全沙箱。

**Tracing 集成**（Fix #2.3）：

- 工作流引擎自己创建**一个** Trace，每个步骤生成一个 `Span(type=WORKFLOW_STEP)`
- 每个 AgentStep 调用 `Runner.run()` 时设置 `RunConfig.tracing_enabled=False`，禁用 Runner 内建的 Trace 创建，避免双重追踪
- 后续可通过给 RunConfig 新增 `parent_trace` 参数，让 Runner 在现有 Trace 内创建子 Span

## API 接口

路由文件：`backend/app/api/workflows.py`，前缀 `/api/v1/workflows`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/workflows` | 列表（分页、搜索） |
| POST | `/workflows` | 创建工作流定义 |
| GET | `/workflows/{name}` | 获取定义 |
| PUT | `/workflows/{name}` | 更新（版本号递增） |
| DELETE | `/workflows/{name}` | 软删除 |
| POST | `/workflows/{name}/execute` | 执行工作流 |
| GET | `/workflows/{name}/executions` | 执行历史列表 |
| GET | `/workflows/executions/{id}` | 执行详情 |
| POST | `/workflows/executions/{id}/cancel` | 取消运行中执行 |

**执行请求体**：
```json
{
  "context": {"topic": "量子计算"},
  "idempotency_key": "optional-unique-key",
  "config_overrides": {
    "workflow_timeout": 300,
    "fail_fast": true
  }
}
```

**执行流程**：
1. POST /execute 立即返回 `execution_id`
2. `idempotency_key` 幂等：若相同 key 的执行已存在，直接返回现有 execution_id（Fix #5.5）
3. 后台 `asyncio.create_task` 运行引擎
4. 活跃任务存储在内存 dict（execution_id → Task），cancel 端点调用 `task.cancel()`（Fix #4.2）
5. 客户端轮询 GET /executions/{id} 获取状态
6. 执行前验证 `input_schema`（JSON Schema 校验）（Fix #5.1）
7. 所有 AgentStep 默认 `approval_mode = FULL_AUTO`（Fix #5.2）

**Workflow 执行 vs Session 执行的关系**（Fix #2.1）：
- Workflow 中的 AgentStep 是**单次调用**（one-shot），不维护对话历史（`session=None`）
- 若需要多轮对话能力，Agent 的 `max_turns` 参数控制内部工具调用轮数
- Workflow 执行不创建 SessionRecord，但通过 Trace 和 SpanRecord 提供完整的可观测性
- 未来可扩展：为 AgentStep 添加 `session_id` 字段，支持绑定已有 Session

**Trace 关联**（Fix #2.2）：
- 工作流引擎创建一个 Trace，`workflow_name = workflow.name`
- Trace 的 `metadata_` 中包含 `{"workflow_execution_id": "<uuid>"}`
- 每个 AgentStep 产生的 Trace（如需独立追踪）通过 `metadata_.parent_trace_id` 关联

Pydantic schemas 在 `schemas/workflow.py`，steps 字段使用 type 判别联合验证。

## 前端页面

### 新增文件

| 文件 | 说明 |
|------|------|
| `services/workflowService.ts` | API 客户端 |
| `pages/workflows/WorkflowListPage.tsx` | ProTable 工作流列表 |
| `pages/workflows/WorkflowEditorPage.tsx` | 可视化 DAG 编辑器（React Flow + dagre） |
| `pages/workflows/WorkflowExecutionPage.tsx` | 执行历史列表 |
| `pages/workflows/WorkflowExecutionDetailPage.tsx` | 执行详情（Timeline + context 查看） |
| `components/workflow/AgentStepNode.tsx` | Agent 节点（蓝色边框） |
| `components/workflow/ParallelStepNode.tsx` | 并行节点（绿色） |
| `components/workflow/ConditionalStepNode.tsx` | 条件节点（橙色） |
| `components/workflow/LoopStepNode.tsx` | 循环节点（紫色） |
| `components/workflow/StepPropertyPanel.tsx` | 步骤属性编辑抽屉 |

### 修改现有文件

- `App.tsx` — 添加 5 条 lazy 路由（/workflows, /workflows/new, /workflows/:name/edit, /workflows/:name/executions, /workflows/executions/:id）
- `layouts/BasicLayout.tsx` — 侧边栏新增 "Workflow 编排" 菜单项（PartitionOutlined）

### DAG 编辑器设计

基于现有 `HandoffEditorPage.tsx` 模式扩展：
- React Flow v12 + dagre 自动布局（TB 方向）
- 多种自定义节点类型（AgentStep/Parallel/Conditional/Loop）
- ConditionalStep 的出边标签显示 branch.condition
- 点击节点打开右侧 Drawer 属性面板（StepPropertyPanel）
- 工具栏：保存、自动布局、验证（环检测 + 嵌套规则 + 引用检查）、添加步骤（下拉选类型）
- 保存时 diff 边集，仅更新有变更的部分

## 实现阶段

### Phase 1: Framework 核心（可独立使用）

**新建文件**（`kasaya-framework/kasaya/workflow/`）：
1. `step.py` — 所有 Step 数据类（含 StepStatus 枚举）
2. `workflow.py` — Workflow, Edge 数据类
3. `result.py` — WorkflowResult, StepResult, WorkflowStatus
4. `config.py` — WorkflowRunConfig
5. `validator.py` — 拓扑排序（Kahn 算法）、环检测、孤立边检测、嵌套规则验证、output_key 冲突检测
6. `serialization.py` — dict ↔ dataclass 序列化（type 字段判别）
7. `evaluator.py` — 安全条件表达式求值
8. `engine.py` — WorkflowEngine 核心执行器（ready-queue + cancel_event + timeout）
9. `__init__.py` — 模块导出

**修改文件**：
- `kasaya/__init__.py` — 新增 `# === Workflow ===` 导出段
- `kasaya/tracing/span.py` — SpanType 新增 `WORKFLOW_STEP = "workflow_step"`

**测试**：每个步骤类型的执行、条件求值、DAG 验证、嵌套规则、output_key 冲突、重试逻辑、取消流程、超时。

完成后开发者可以纯 Python 定义并运行工作流：
```python
from kasaya import Workflow, AgentStep, ParallelStep, WorkflowEngine

wf = Workflow(
    name="research-pipeline",
    steps=[
        AgentStep(id="research", agent_name="researcher",
                  prompt_template="研究主题: {{topic}}"),
        ParallelStep(id="parallel-process", sub_steps=[
            AgentStep(id="summarize", agent_name="writer",
                      prompt_template="总结: {{research_output}}"),
            AgentStep(id="translate", agent_name="translator",
                      prompt_template="翻译: {{research_output}}"),
        ]),
    ],
    edges=[
        Edge(id="e1", source_step_id="research", target_step_id="parallel-process"),
    ],
)
engine = WorkflowEngine()
result = await engine.run(
    wf,
    context={"topic": "量子计算"},
    agent_resolver=my_async_resolver,  # async (name: str) -> Agent
)
```

### Phase 2: Backend 持久化 + API

**新建文件**（`backend/app/`）：
1. `models/workflow.py` — WorkflowDefinition, WorkflowExecution ORM 模型
2. `schemas/workflow.py` — Pydantic 请求/响应 schema（含幂等键、config_overrides）
3. `services/workflow.py` — CRUD + execute + 后台任务管理
4. `services/agent_resolver.py` — 从 AgentConfig 构建完整 Agent 实例的共享逻辑（从 session.py 提取）
5. `api/workflows.py` — FastAPI 路由

**修改文件**：
- `main.py` — 注册 workflows_router
- `models/__init__.py` — 导出新模型
- `alembic/` — 自动生成迁移

**复用**：将 `services/session.py` 中的 `_build_agent_from_config()` 提取到共享的 `services/agent_resolver.py`。

### Phase 3: 前端 CRUD + 执行历史

**新建文件**：
1. `services/workflowService.ts`
2. `pages/workflows/WorkflowListPage.tsx`
3. `pages/workflows/WorkflowExecutionPage.tsx`
4. `pages/workflows/WorkflowExecutionDetailPage.tsx`

**修改**：`App.tsx`（路由）、`BasicLayout.tsx`（侧边栏）

### Phase 4: 前端可视化 DAG 编辑器

**新建文件**：
1. `components/workflow/AgentStepNode.tsx`
2. `components/workflow/ParallelStepNode.tsx`
3. `components/workflow/ConditionalStepNode.tsx`
4. `components/workflow/LoopStepNode.tsx`
5. `components/workflow/StepPropertyPanel.tsx`
6. `pages/workflows/WorkflowEditorPage.tsx`

参考：`pages/agents/HandoffEditorPage.tsx` 的 React Flow + dagre 模式。

## 验证方式

1. **Phase 1 验证**：`cd kasaya-framework && uv run pytest tests/ -q` — 单元测试覆盖每种步骤类型、条件求值、DAG 验证、嵌套规则、重试逻辑、取消、超时
2. **Phase 2 验证**：启动 backend + DB，通过 `http://localhost:8000/docs` 调用 API 创建工作流 → 执行 → 查询执行结果 → 取消执行
3. **Phase 3 验证**：前端访问 `/workflows` 页面，创建/编辑工作流，查看执行历史和详情
4. **Phase 4 验证**：在可视化编辑器中拖拽构建 DAG，保存后执行，验证执行详情中步骤状态与 context 变化

## 审查修复清单

| # | 严重度 | 问题 | 修复 |
|---|--------|------|------|
| 1.1 | Critical | Runner.run() 调用签名与实际不匹配 | 修正为关键字参数，明确 output 是 str |
| 4.1 | Critical | 拓扑分层执行在 ConditionalStep 时会执行跳过的分支 | 改为 ready-queue + skipped_set 驱动 |
| 1.5 | Major | agent_resolver 过于简化 | 改为 async 签名，文档化解析需求，提取共享服务 |
| 2.1 | Major | Workflow 执行不复用 Session 基础设施 | 文档化为有意设计（one-shot），未来可扩展 |
| 2.2 | Major | workflow_name 语义冲突 | Trace.metadata 增加 workflow_execution_id |
| 2.3 | Major | Runner.run() 内建 Trace 导致双重追踪 | AgentStep 设置 tracing_enabled=False |
| 3.1 | Major | ParallelStep/LoopStep 嵌套未定义 | 明确嵌套规则，validator 拒绝违规嵌套 |
| 3.2 | Major | ConditionalStep branches 与 Edge condition 冗余 | 移除 Edge.condition，branches 独占路由 |
| 3.3 | Major | LoopStep body_steps 无边定义 | 文档化为顺序执行，不需要 body_edges |
| 4.2 | Major | 取消机制未定义 | 添加 cancel_event + 内存任务注册表 |
| 4.3 | Major | 并行分支写相同 context key | validator 检测冲突，默认 key 按 step_id 隔离 |
| 4.4 | Major | 并行分支错误处理未定义 | 添加 fail_policy（fail_fast / collect_all） |
| 5.1 | Major | 无工作流级 guardrails | 添加 input_schema JSON Schema 验证 |
| 5.2 | Major | 工作流内 AgentStep 审批流未定义 | 默认 FULL_AUTO，文档化 |
| 1.2 | Minor | RunConfig.workflow_name 未设置 | 引擎构建 RunConfig 时设置 workflow_name |
| 1.3 | Minor | WORKFLOW_STEP span 名称未指定 | name=step.id, metadata 包含 step_type |
| 1.4 | Minor | inline versioning 与 Agent 模式不一致 | 文档化设计决策和理由 |
| 3.4 | Minor | StepResult.status 使用裸字符串 | 改为 StepStatus 枚举 |
| 5.3 | Minor | 无工作流定义版本快照表 | 添加 workflow_snapshot 到 execution 记录 |
| 5.4 | Minor | 无整体超时 | Workflow 添加 timeout 字段 + asyncio.wait_for |
| 5.5 | Minor | 执行端点无幂等性 | 添加 idempotency_key |
| 5.6 | Minor | RunConfig 字段未映射 | 添加 WorkflowRunConfig 包装类 |

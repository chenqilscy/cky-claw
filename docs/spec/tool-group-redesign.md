# CkyClaw 工具组方案重设计

> 版本：v1.1
> 日期：2026-04-15
> 状态：✅ 全部实现完成（Phase 1-4）

## 1. 背景与问题

### 1.1 现状

工具组（ToolGroup）是 CkyClaw Framework 的核心抽象之一，用于将工具按功能域分组管理。当前系统已有完整的 CRUD 能力：

- **Framework 层**：`ToolGroup` 数据类 + `ToolRegistry` 全局注册表 + `FunctionTool` 工具定义
- **Backend 层**：`ToolGroupConfig` ORM + 5 个 REST API（`/api/v1/tool-groups`）
- **Frontend 层**：`ToolGroupPage` 列表管理 + JSON 编辑器 + 启用/禁用开关
- **内置工具组**：6 个 Hosted 组（web-search / code-executor / file-ops / http / database / code-review）

### 1.2 核心问题

| # | 问题 | 影响 |
|---|------|------|
| P1 | 工具定义 JSON 用户不知如何编写 | JSON Schema 门槛高，无引导、无校验提示、无示例模板 |
| P2 | "工具"概念模糊 | MCP Tool / Agent Skill / 内置 Tool / Agent-as-Tool 四种工具来源，用户无法区分 |
| P3 | 条件启用配置难以使用 | `conditions` 字段是自由 JSON，用户不知道有哪些可用参数 |
| P4 | 工具组与 Agent 关联逻辑不直观 | Agent 编辑页的 `tool_groups` 仅为名称列表多选，无法预览组内工具 |

---

## 2. 工具类型明确

### 2.1 四种工具来源

CkyClaw 平台上的"工具"有以下四种来源：

| 来源 | 说明 | 工具组支持 | 配置方式 |
|------|------|:----------:|---------|
| **Hosted Tool**（内置工具） | Framework 内置的 6 组标准工具（web-search 等） | ✅ 已支持 | 系统启动时自动种子（`seed_hosted_tool_groups`）|
| **Custom Tool**（自定义工具） | 用户通过 JSON Schema 定义参数和描述的工具 | ✅ 已支持 | ToolGroupPage JSON 编辑器 |
| **MCP Tool**（MCP 服务工具） | 通过 MCP Server（stdio/sse/http）暴露的外部工具 | ❌ 不在工具组 | Agent 级别直接绑定 `mcp_servers` |
| **Agent-as-Tool** | 将其他 Agent 包装为工具使用 | ❌ 不在工具组 | Agent 级别直接绑定 `agent_tools` |

> **设计原则**：工具组 **仅管理 Hosted + Custom 两类工具**。MCP Tool 和 Agent-as-Tool 各有独立的管理入口和绑定方式，不纳入工具组。

### 2.2 Runner 三路工具合并

Agent 运行时，Runner 从三个来源组合最终工具列表：

```
Agent.tool_groups  ──→ ToolGroup.tools[]  ──→ FunctionTool[]
Agent.mcp_servers  ──→ MCP Client         ──→ FunctionTool[]    ──→ 合并去重 → LLM tools[]
Agent.agent_tools  ──→ Agent.as_tool()    ──→ FunctionTool[]
```

---

## 3. 工具定义 JSON 规范

### 3.1 ToolDefinition Schema

每个工具的 JSON 定义遵循以下结构：

```json
{
  "name": "web_search",
  "description": "搜索互联网并返回相关结果摘要",
  "parameters_schema": {
    "type": "object",
    "properties": {
      "query": {
        "type": "string",
        "description": "搜索关键词"
      },
      "max_results": {
        "type": "integer",
        "description": "最大返回结果数",
        "default": 5
      }
    },
    "required": ["query"]
  }
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|:----:|------|
| `name` | string | ✅ | 工具唯一标识，1-128 字符，小写字母/数字/下划线 |
| `description` | string | ✅ | 工具功能描述，LLM 据此决定是否调用 |
| `parameters_schema` | object | ✅ | 符合 JSON Schema Draft 7 的参数定义 |

### 3.2 parameters_schema 编写指南

`parameters_schema` 是标准的 [JSON Schema](https://json-schema.org/)，LLM Function Calling 会用此 schema 生成参数。

**支持的类型**：

| 类型 | 说明 | 示例 |
|------|------|------|
| `string` | 文本 | `"type": "string"` |
| `integer` | 整数 | `"type": "integer"` |
| `number` | 浮点数 | `"type": "number"` |
| `boolean` | 布尔 | `"type": "boolean"` |
| `array` | 数组 | `"type": "array", "items": {"type": "string"}` |
| `object` | 嵌套对象 | `"type": "object", "properties": {...}` |

**关键字段说明**：

- `properties`：定义每个参数的名称和类型
- `required`：必填参数列表
- `default`：参数默认值
- `description`：参数描述（**强烈建议填写**，帮助 LLM 理解参数含义）
- `enum`：枚举值约束

### 3.3 示例模板

#### 无参数工具

```json
{
  "name": "get_current_time",
  "description": "获取当前服务器时间",
  "parameters_schema": {
    "type": "object",
    "properties": {},
    "required": []
  }
}
```

#### 单参数工具

```json
{
  "name": "translate",
  "description": "将文本翻译为指定语言",
  "parameters_schema": {
    "type": "object",
    "properties": {
      "text": {
        "type": "string",
        "description": "待翻译的文本"
      },
      "target_language": {
        "type": "string",
        "description": "目标语言代码",
        "enum": ["zh", "en", "ja", "ko", "fr", "de"]
      }
    },
    "required": ["text", "target_language"]
  }
}
```

#### 复杂参数工具

```json
{
  "name": "send_email",
  "description": "发送电子邮件",
  "parameters_schema": {
    "type": "object",
    "properties": {
      "to": {
        "type": "array",
        "items": { "type": "string" },
        "description": "收件人邮箱列表"
      },
      "subject": {
        "type": "string",
        "description": "邮件主题"
      },
      "body": {
        "type": "string",
        "description": "邮件正文（支持 Markdown）"
      },
      "cc": {
        "type": "array",
        "items": { "type": "string" },
        "description": "抄送列表"
      },
      "priority": {
        "type": "string",
        "enum": ["low", "normal", "high"],
        "default": "normal",
        "description": "邮件优先级"
      }
    },
    "required": ["to", "subject", "body"]
  }
}
```

---

## 4. 条件启用机制

### 4.1 现状

Framework 层支持两种条件启用：

1. **FunctionTool.condition**：`Callable[[RunContext], bool]`，运行时动态判断
2. **ToolGroupConfig.conditions**：后端 JSONB 字段，存储静态条件规则

### 4.2 可用参数

条件启用规则通过 `RunContext` 注入，以下参数在运行时可用：

| 参数路径 | 类型 | 说明 |
|----------|------|------|
| `run_ctx.metadata["env"]` | string | 运行环境标识（dev / staging / prod） |
| `run_ctx.metadata["user_id"]` | string | 当前用户 ID |
| `run_ctx.metadata["org_id"]` | string | 当前组织 ID |
| `run_ctx.metadata["agent_name"]` | string | 当前 Agent 名称 |
| `run_ctx.turn_count` | int | 当前对话轮次 |

### 4.3 前端条件配置方案（重设计）

**目标**：将自由 JSON 输入替换为结构化的规则编辑器。

**条件规则格式**：

```json
{
  "conditions": {
    "match": "all",
    "rules": [
      { "field": "env", "operator": "equals", "value": "production" },
      { "field": "user_id", "operator": "in", "value": ["user-1", "user-2"] }
    ]
  }
}
```

| 字段 | 说明 |
|------|------|
| `match` | 匹配模式：`all`（AND）/ `any`（OR） |
| `rules` | 规则数组 |
| `rules[].field` | 参数名（从上述可用参数中选择） |
| `rules[].operator` | 比较运算符：`equals` / `not_equals` / `in` / `not_in` / `gt` / `lt` / `gte` / `lte` |
| `rules[].value` | 比较值 |

**前端 UI 方案**：

```
┌─ 条件启用规则 ──────────────────────────────────────┐
│                                                       │
│  匹配模式：[全部满足 ▾]                               │
│                                                       │
│  ┌─ 规则 1 ─────────────────────────────────────────┐│
│  │ [环境 ▾]   [等于 ▾]   [production ▾]    [× 删除]││
│  └──────────────────────────────────────────────────┘│
│  ┌─ 规则 2 ─────────────────────────────────────────┐│
│  │ [用户ID ▾] [包含于 ▾] [user-1, user-2 ]  [× 删除]││
│  └──────────────────────────────────────────────────┘│
│                                                       │
│  [+ 添加规则]                                         │
└───────────────────────────────────────────────────────┘
```

---

## 5. UI 重设计方案

### 5.1 工具组列表页（ToolGroupPage）

保持现有 ProTable 列表，增强以下功能：

| 改进项 | 现状 | 方案 |
|--------|------|------|
| 工具预览 | 仅显示工具数量 | 展开行显示组内工具名称和描述 |
| 来源标识 | `builtin`/`custom` 文字标签 | 改为图标 + 颜色更明显的 Tag |
| 快速创建 | 仅 JSON 编辑器 | 增加"从模板创建"选项（预置常见工具组模板） |

### 5.2 工具组编辑弹窗（重设计）

**当前**：一个 JSON 编辑器让用户输入工具定义数组。

**方案**：替换为结构化表单 + 可视化工具列表。

```
┌─ 编辑工具组 ──────────────────────────────────────────┐
│                                                         │
│  名称：[web-search          ]                           │
│  描述：[网络搜索与页面抓取   ]                           │
│                                                         │
│  ── 工具列表 ───────────────────────────────────────── │
│  ┌──────────────────────────────────────────────────┐  │
│  │ 🔧 web_search                            [编辑][删除]│
│  │    搜索互联网并返回相关结果摘要                      │
│  │    参数：query (string, 必填) · max_results (int)   │
│  ├──────────────────────────────────────────────────┤  │
│  │ 🔧 fetch_webpage                         [编辑][删除]│
│  │    获取指定 URL 的网页内容                          │
│  │    参数：url (string, 必填) · format (string)       │
│  └──────────────────────────────────────────────────┘  │
│                                                         │
│  [+ 添加工具]  [{ } JSON 模式]                          │
│                                                         │
│  ── 条件启用 ─────────────────────────────────────── │
│  匹配模式：[全部满足 ▾]                                 │
│  ┌ 规则 1 ──────────────────────────────────────────┐  │
│  │ [环境 ▾]  [等于 ▾]  [production]          [× 删除]│  │
│  └──────────────────────────────────────────────────┘  │
│  [+ 添加规则]                                           │
│                                                         │
│           [取消]                     [保存]              │
└─────────────────────────────────────────────────────────┘
```

### 5.3 工具编辑子表单

点击"添加工具"或"编辑"时弹出：

```
┌─ 编辑工具 ──────────────────────────────────┐
│                                               │
│  工具名称：[web_search         ]              │
│  工具描述：[搜索互联网并返回... ]              │
│                                               │
│  ── 参数定义 ─────────────────────────────── │
│  ┌────────────────────────────────────────┐  │
│  │ 参数名 │  类型  │ 必填 │   描述        │  │
│  ├────────┼────────┼──────┼───────────────┤  │
│  │ query  │ string │  ✅  │ 搜索关键词    │  │
│  │ max_r..│ integer│  ❌  │ 最大返回数    │  │
│  └────────────────────────────────────────┘  │
│  [+ 添加参数]                                 │
│                                               │
│  高级选项（折叠）                              │
│  ├ 默认值：[           ]                      │
│  └ 枚举值：[           ]                      │
│                                               │
│        [取消]              [确认]              │
└───────────────────────────────────────────────┘
```

### 5.4 Agent 编辑页工具组选择（增强）

**当前**：下拉多选 `tool_groups` 名称列表。

**方案**：改为可展开的工具组卡片列表。

```
── 工具组 ─────────────────────────────────────────
┌─────────────────────────────────────────────────┐
│ ☑ web-search            来源：内置    工具：2 个 │
│   └ web_search · fetch_webpage                   │
├─────────────────────────────────────────────────┤
│ ☑ code-executor          来源：内置    工具：2 个 │
│   └ execute_python · execute_shell               │
├─────────────────────────────────────────────────┤
│ ☐ file-ops              来源：内置    工具：3 个 │
│   └ file_read · file_write · file_list           │
├─────────────────────────────────────────────────┤
│ ☐ my-custom-tools       来源：自定义   工具：1 个 │
│   └ translate                                     │
└─────────────────────────────────────────────────┘
```

---

## 6. 工具组模板

预置以下工具组模板，用户轻量修改即可使用：

| 模板名 | 包含工具 | 适用场景 |
|--------|----------|----------|
| 网络搜索 | web_search, fetch_webpage | 信息检索 Agent |
| 代码执行 | execute_python, execute_shell | 编程助手 Agent |
| 文件操作 | file_read, file_write, file_list | DevOps Agent |
| HTTP 客户端 | http_request | API 集成 Agent |
| 数据查询 | database_query | 数据分析 Agent |
| 邮件通知 | send_email, send_notification | 自动化 Agent |
| 日历管理 | create_event, list_events, delete_event | 办公助手 Agent |

---

## 7. 实施计划

### Phase 1：文档与校验增强 ✅
- [x] 编写工具定义 JSON 规范文档（本文档）
- [x] 前端工具定义 JSON 编辑器增加 placeholder 示例（已替换为结构化编辑器 + 模板系统）
- [x] 后端 ToolDefinition schema 增加更详细的 validation 错误信息（name 正则 + parameters_schema 结构校验）

### Phase 2：结构化工具编辑器 ✅
- [x] 工具组编辑弹窗改为结构化表单 + 可视化工具列表（ToolEditor 组件）
- [x] 工具编辑子表单：参数表格化编辑（ToolEditModal + 参数 Table）
- [x] "JSON 模式"切换按钮保留高级用户手写 JSON 能力（Segmented 控件切换）

### Phase 3：条件启用规则编辑器 ✅
- [x] 将自由 JSON `conditions` 改为结构化规则编辑器（ConditionRuleEditor 组件）
- [x] 下拉选择可用参数（env / user_id / org_id / agent_name / turn_count）
- [x] 下拉选择比较运算符（equals / not_equals / in / not_in / gt / lt / gte / lte）

### Phase 4：Agent 编辑页工具预览 ✅
- [x] Agent 编辑页工具组选择增强为带预览的 optionRender（显示来源、工具数量、工具名称）
- [x] 展示组内工具名称和描述
- [x] 工具组来源标识（内置 🏠 / 自定义 ✏️）

---

## 8. 附录：数据模型参考

### ToolGroupConfig ORM

```python
class ToolGroupConfig(SoftDeleteMixin, Base):
    __tablename__ = "tool_group_configs"
    
    id: Mapped[UUID]                    # 主键
    name: Mapped[str]                   # 唯一名称（3-64 字符）
    description: Mapped[str]            # 描述
    source: Mapped[str]                 # "hosted" | "custom"
    is_enabled: Mapped[bool]            # 启用状态
    tools: Mapped[list[Any]]            # JSONB 工具定义数组
    conditions: Mapped[dict[str, Any]]  # JSONB 条件启用规则
    org_id: Mapped[UUID | None]         # 租户隔离
```

### ToolDefinition Schema

```python
class ToolDefinition(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    description: str
    parameters_schema: dict
```

### FunctionTool 数据类

```python
@dataclass
class FunctionTool:
    name: str
    description: str = ""
    fn: Callable | None = None
    parameters_schema: dict = field(default_factory=dict)
    group: str | None = None
    timeout: float | None = None
    approval_required: bool = False
    condition: Callable[[RunContext], bool] | None = None
```

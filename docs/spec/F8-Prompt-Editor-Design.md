# F8 高级 Prompt Editor 设计文档

## 文档信息

| 字段 | 内容 |
|------|------|
| 版本 | v1.0.0 |
| 日期 | 2026-04-12 |
| 状态 | 待实现 |
| 优先级 | P1（用户体验） |
| 依赖 | AgentConfig ORM、AgentConfigVersion、A/B 测试 API |

---

## 一、需求概述

### 1.1 背景

当前 Agent 的 `instructions` 字段仅以纯文本方式存储和编辑（前端为 `<TextArea>`），存在以下痛点：

1. **无模板变量**：不同场景需要重复修改 instructions，无法参数化复用
2. **编辑体验差**：纯文本无语法高亮、无变量提示、无预览
3. **A/B 测试仅比模型**：现有 A/B 测试只支持同 Prompt 不同模型，不支持同模型不同 Prompt 变体

### 1.2 目标

- 支持 `{{variable}}` 模板变量语法，运行时自动渲染
- 提供带语法高亮、变量面板、实时预览的 Prompt 编辑器
- 扩展 A/B 测试支持 Prompt 变体对比
- 复用现有版本管理机制（AgentConfigVersion 自动快照）

---

## 二、数据模型

### 2.1 AgentConfig 扩展

在现有 `agent_configs` 表新增字段：

```sql
ALTER TABLE agent_configs ADD COLUMN prompt_variables JSONB NOT NULL DEFAULT '[]'::jsonb;
```

`prompt_variables` 结构：

```json
[
  {
    "name": "role",
    "type": "string",
    "default": "助手",
    "description": "Agent 角色定义",
    "required": true
  },
  {
    "name": "domain",
    "type": "string",
    "default": "通用",
    "description": "业务领域",
    "required": false
  },
  {
    "name": "max_steps",
    "type": "number",
    "default": 5,
    "description": "最大步骤数",
    "required": false
  }
]
```

支持的变量类型：
- `string`：文本字符串
- `number`：数值
- `boolean`：布尔值
- `enum`：枚举（附带 `options: string[]`）

### 2.2 Instructions 模板语法

```
你是一个{{role}}，专注于{{domain}}领域。

处理用户请求时：
1. 最多执行 {{max_steps}} 个步骤
2. 使用{{language}}语言回复
```

语法规则：
- 变量引用：`{{variable_name}}`
- 变量名：`[a-zA-Z_][a-zA-Z0-9_]*`
- 未定义变量渲染为空字符串并记录 warning
- 变量值做安全转义，禁止嵌套 `{{`

### 2.3 版本管理

**复用现有机制**：AgentConfigVersion 的 `snapshot: JSONB` 已包含完整 Agent 配置。`prompt_variables` 将自动纳入快照。无需新建版本表。

---

## 三、API 设计

### 3.1 Prompt 渲染预览

```
POST /api/v1/agents/{name}/prompt/preview
```

请求体：
```json
{
  "variables": {
    "role": "代码审查专家",
    "domain": "Python"
  }
}
```

响应：
```json
{
  "rendered": "你是一个代码审查专家，专注于 Python 领域。...",
  "warnings": ["变量 'language' 未提供值，使用默认值 ''"]
}
```

### 3.2 Prompt 变量验证

```
POST /api/v1/agents/{name}/prompt/validate
```

请求体：
```json
{
  "instructions": "你是{{role}}，领域{{domain}}",
  "variables": [
    { "name": "role", "type": "string", "default": "助手", "required": true }
  ]
}
```

响应：
```json
{
  "valid": false,
  "errors": [],
  "warnings": ["模板引用变量 'domain' 未在变量列表中定义"]
}
```

### 3.3 A/B Prompt 测试扩展

扩展现有 `POST /api/v1/ab-test`：

```json
{
  "prompts": [
    "你是一个严格的代码审查专家，只关注安全漏洞。",
    "你是一个友好的代码审查助手，关注代码质量和可维护性。"
  ],
  "model": "openai/gpt-4o",
  "provider_name": "openai",
  "max_tokens": 1024,
  "test_input": "请审查这段代码：def login(user, pwd): ..."
}
```

响应复用现有 `ABTestResponse` 结构，每个结果对应一个 Prompt 变体。

---

## 四、前端设计

### 4.1 Prompt Editor 组件

替换 AgentEditPage 中的 `<TextArea>` 为 `<PromptEditor>` 组件：

**功能清单**：
- 语法高亮：`{{variable}}` 标记为高亮色
- 变量面板：右侧显示已定义变量列表，点击插入
- 实时预览：下方 Tab 切换查看渲染后的 Prompt
- 变量检测：自动扫描模板中的 `{{xxx}}`，高亮未定义变量
- 行号显示

**技术方案**：使用 `@monaco-editor/react`（Monaco Editor）或自定义 `<textarea>` + 纯 CSS 高亮叠加层。MVP 推荐后者（轻量、无额外依赖）。

### 4.2 变量管理面板

在 Agent 编辑页新增 "模板变量" 配置区：
- 变量列表表格：名称、类型、默认值、描述、必填
- 添加/编辑/删除操作
- 变量类型下拉选择

### 4.3 Prompt A/B 测试集成

在 ABTestPage 新增 "Prompt 对比"模式 Tab：
- 输入 2-5 个 Prompt 变体
- 选择单个模型
- 输入测试 input
- 并行执行并对比结果

---

## 五、Framework 层集成

### 5.1 模板渲染器

新增 `kasaya/agent/template.py`：

```python
def render_template(template: str, variables: dict[str, Any]) -> str:
    """渲染 {{variable}} 模板。

    - 安全转义变量值，防止嵌套注入
    - 未匹配变量替换为空字符串
    - 返回渲染后的字符串
    """
```

### 5.2 Runner 集成

Runner 在构建 system message 时，如果 Agent.instructions 为 str 且包含 `{{`，自动调用模板渲染器。变量值来源：
1. RunConfig.template_variables（显式传入）
2. Agent 配置的默认值
3. 未提供 → 空字符串 + warning

---

## 六、安全考虑

1. **注入防护**：变量值中的 `{{` 和 `}}` 做转义（替换为单括号或转义符），防止递归渲染
2. **长度限制**：单个变量值 ≤ 10,000 字符，总渲染后 instructions ≤ 100,000 字符
3. **类型校验**：number 类型校验数值合法性，enum 类型校验值在 options 内

---

## 七、MVP 范围

| 阶段 | 内容 | 预估 |
|------|------|------|
| **Phase 1** | Backend：prompt_variables 字段 + 迁移 + 渲染预览 API + 验证 API | — |
| **Phase 2** | Framework：template.py 渲染器 + Runner 集成 | — |
| **Phase 3** | Frontend：PromptEditor 组件 + 变量管理面板 + AgentEditPage 集成 | — |
| **Phase 4** | A/B Prompt 测试扩展 + ABTestPage 新增 Prompt 对比模式 | — |
| **Phase 5** | 测试：Backend + Framework + Frontend 全栈测试 | — |

### 延期项（v2）

- Monaco Editor 高级代码编辑体验
- Prompt 模板库（跨 Agent 复用）
- Prompt 效果评分（结合 Auto Evaluator）
- 条件变量（根据上下文动态启用/禁用）

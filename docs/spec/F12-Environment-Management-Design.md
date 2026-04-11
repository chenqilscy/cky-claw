# F12 多环境管理设计文档

## 文档信息

| 字段 | 内容 |
|------|------|
| 版本 | v1.0.0 |
| 日期 | 2026-04-12 |
| 状态 | 待实现 |
| 优先级 | P2（企业能力） |
| 依赖 | AgentConfig ORM、AgentConfigVersion、RBAC 权限系统、审计日志 |

---

## 一、需求概述

### 1.1 背景

当前 CkyClaw 平台所有 Agent 配置在单一环境中运行，没有开发/测试/生产环境隔离机制。企业用户面临的痛点：

1. **配置误操作风险**：开发阶段的 Agent 配置变更直接影响生产环境
2. **无发布流程**：Agent 从开发到生产没有受控的发布审批流程
3. **无法 A/B 环境对比**：无法对比不同环境中 Agent 的行为差异
4. **回滚困难**：生产问题时缺乏快速回滚到已验证版本的机制

### 1.2 目标

- 支持 Dev / Staging / Prod 三种环境（可自定义扩展）
- Agent 配置按环境隔离，互不影响
- 提供受控的发布流程：Dev → Staging → Prod
- 发布操作记录审计日志
- 前端支持环境切换和环境内 Agent 管理

---

## 二、数据模型

### 2.1 Environment 表

```sql
CREATE TABLE environments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(32) NOT NULL UNIQUE,          -- dev / staging / prod / custom
    display_name VARCHAR(64) NOT NULL,          -- 显示名称
    description TEXT NOT NULL DEFAULT '',
    color VARCHAR(16) NOT NULL DEFAULT '#1890ff', -- UI 标签颜色
    sort_order INTEGER NOT NULL DEFAULT 0,       -- 排序
    is_protected BOOLEAN NOT NULL DEFAULT FALSE,  -- prod 受保护，删除需确认
    settings_override JSONB NOT NULL DEFAULT '{}', -- 环境级配置覆盖
    org_id UUID REFERENCES organizations(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

预置数据：
```sql
INSERT INTO environments (name, display_name, color, sort_order, is_protected) VALUES
    ('dev', '开发', '#52c41a', 0, FALSE),
    ('staging', '预发', '#faad14', 1, FALSE),
    ('prod', '生产', '#f5222d', 2, TRUE);
```

### 2.2 AgentEnvironmentBinding 表

```sql
CREATE TABLE agent_environment_bindings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_config_id UUID NOT NULL REFERENCES agent_configs(id) ON DELETE CASCADE,
    environment_id UUID NOT NULL REFERENCES environments(id) ON DELETE CASCADE,
    version_id UUID NOT NULL REFERENCES agent_config_versions(id) ON DELETE CASCADE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    published_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    published_by UUID REFERENCES users(id),
    rollback_from_id UUID REFERENCES agent_environment_bindings(id),  -- 回滚来源
    notes TEXT NOT NULL DEFAULT '',                                     -- 发布备注
    org_id UUID REFERENCES organizations(id),
    UNIQUE(agent_config_id, environment_id)  -- 每个 Agent 在每个环境只有一个活跃绑定
);
```

### 2.3 settings_override 结构

环境级配置覆盖，合并到 Agent 运行时配置：

```json
{
  "model_override": "openai/gpt-4o-mini",
  "provider_override": "openai-staging",
  "max_tokens_override": 2048,
  "guardrails_strict": true,
  "approval_mode_override": "suggest"
}
```

优先级：Agent 自身配置 < 环境级覆盖

---

## 三、API 设计

### 3.1 环境 CRUD

```
GET    /api/v1/environments                    -- 列表
POST   /api/v1/environments                    -- 创建
GET    /api/v1/environments/{env_name}          -- 详情
PUT    /api/v1/environments/{env_name}          -- 更新
DELETE /api/v1/environments/{env_name}          -- 删除（受保护环境需确认）
```

### 3.2 Agent 发布

```
POST   /api/v1/environments/{env_name}/agents/{agent_name}/publish
```

请求体：
```json
{
  "version_id": "uuid-of-agent-version",  // 可选，默认为最新版本
  "notes": "修复了 Prompt 模板变量"
}
```

响应：
```json
{
  "binding_id": "uuid",
  "agent_name": "code-reviewer",
  "environment": "staging",
  "version": 12,
  "published_at": "2026-04-12T10:00:00Z",
  "published_by": "admin"
}
```

### 3.3 Agent 回滚

```
POST   /api/v1/environments/{env_name}/agents/{agent_name}/rollback
```

请求体：
```json
{
  "target_version_id": "uuid-of-previous-version",  // 可选，默认回滚到上一次发布
  "notes": "回滚：v12 导致误判"
}
```

### 3.4 环境内 Agent 列表

```
GET    /api/v1/environments/{env_name}/agents
```

返回该环境中所有已发布的 Agent 及其绑定版本。

### 3.5 环境间对比

```
GET    /api/v1/environments/diff?agent={agent_name}&env1=staging&env2=prod
```

响应：对比两个环境中同一 Agent 的配置差异（复用 AgentVersionDiff 逻辑）。

---

## 四、前端设计

### 4.1 全局环境选择器

在 BasicLayout 顶部导航栏添加环境切换下拉框：
- 显示当前环境名称 + 颜色标签
- 切换后所有 Agent 列表、Chat 页面、运行记录均按当前环境过滤
- 使用 Zustand store 管理当前环境状态

### 4.2 环境管理页面

新增 `pages/environments/`：
- **EnvironmentListPage**：环境列表（名称、颜色标签、Agent 数量、最近发布时间）
- **EnvironmentDetailPage**：环境详情（已发布 Agent 列表 + 发布历史）

### 4.3 Agent 发布面板

在 Agent 详情/版本页面新增 "发布" 操作：
- 选择目标环境
- 选择版本（默认最新）
- 填写发布备注
- 确认发布（prod 环境需二次确认）

### 4.4 环境对比视图

- 选择两个环境 + Agent
- 左右对比配置差异（复用版本 diff 组件）
- 高亮变更字段

---

## 五、权限控制

| 操作 | 所需权限 |
|------|---------|
| 查看环境列表 | `environments:read` |
| 创建/编辑环境 | `environments:write` |
| 删除受保护环境 | `admin` |
| 发布到 dev | `environments:publish_dev` |
| 发布到 staging | `environments:publish_staging` |
| 发布到 prod | `environments:publish_prod`（默认仅 admin） |
| 回滚 | 同发布权限 |

---

## 六、Runner 集成

### 6.1 环境感知运行

Runner 启动时，如果 RunConfig 指定了 `environment`，自动加载该环境的 Agent 绑定配置：

```python
# Runner 内部逻辑
if run_config.environment:
    binding = await get_agent_binding(agent_name, environment)
    agent_config = load_version_snapshot(binding.version_id)
    # 合并环境级覆盖
    agent_config = merge_settings_override(agent_config, environment.settings_override)
```

### 6.2 Chat 页面集成

前端 Chat 页面在发送消息时，附带当前环境标识：
```json
{
  "agent_name": "code-reviewer",
  "message": "审查这段代码",
  "environment": "staging"
}
```

---

## 七、审计日志

所有发布/回滚操作自动记录审计日志（复用现有 AuditLog 模型）：

```json
{
  "action": "environment.publish",
  "resource_type": "agent_environment_binding",
  "resource_id": "uuid",
  "details": {
    "agent_name": "code-reviewer",
    "environment": "prod",
    "version": 12,
    "previous_version": 10,
    "notes": "修复 Prompt 模板"
  }
}
```

---

## 八、MVP 范围

| 阶段 | 内容 | 预估 |
|------|------|------|
| **Phase 1** | Backend：Environment + Binding 模型 + 迁移 + 预置数据 | — |
| **Phase 2** | Backend：环境 CRUD API + 发布/回滚 API + 环境 Agent 列表 | — |
| **Phase 3** | Backend：环境对比 API + 审计日志集成 | — |
| **Phase 4** | Frontend：环境管理页面 + 全局环境选择器 + Zustand store | — |
| **Phase 5** | Frontend：Agent 发布面板 + 环境对比视图 | — |
| **Phase 6** | 测试：Backend + Frontend 全栈测试 | — |

### 延期项（v2）

- Runner 环境感知运行（需 Framework 层改动）
- 环境级 Provider 覆盖（不同环境用不同 LLM 厂商）
- 自动化发布流水线（CI/CD 触发发布）
- Kubernetes 多集群环境隔离（依赖 F2）
- 发布审批流程（多人审批链）
- 环境间自动同步

# CkyClaw Agent Skill 市场机制设计

> 版本：v1.0
> 日期：2026-04-16
> 状态：方案设计
> 关联 Issue：#13

## 1. 背景与现状

### 1.1 已有能力

| 层 | 组件 | 状态 |
|----|------|:----:|
| **Framework** | SkillFactory（Agent 自主创建 Skill + AST 白名单安全） | ✅ |
| **Backend ORM** | `SkillRecord`（name/version/content/category/tags/author） | ✅ |
| **Backend API** | 7 端点：CRUD + search + find-for-agent | ✅ |
| **Marketplace API** | 8 端点：browse/publish/unpublish/install/review | ✅ |
| **Frontend** | SkillPage（列表/搜索/CRUD）+ MarketplacePage（浏览/筛选/安装/评价） | ✅ |

### 1.2 缺失能力

| 功能 | 说明 | 优先级 |
|------|------|:------:|
| **多源导入** | 从 GitHub/URL/本地文件导入 Skill | P1 |
| **安全审查** | LLM 自动审查 + 人工审核队列 | P1 |
| **版本管理** | 版本历史、回滚、依赖冲突检测 | P2 |
| **依赖管理** | Skill 间依赖声明和冲突检测 | P3 |
| **访问控制** | 私有/组织/公开三级隔离 | P2 |

---

## 2. Skill 多源导入

### 2.1 支持的导入来源

| 来源 | 方式 | 说明 |
|------|------|------|
| **手动创建** | 前端编辑器 | 当前已支持 |
| **Agent 自动生成** | SkillFactory | Framework 层已支持 |
| **GitHub 仓库** | URL → `raw.githubusercontent.com` 拉取 | 支持公开仓库和 Token 授权的私有仓库 |
| **URL 导入** | 任意 HTTPS URL | 直接下载 Skill 文件内容 |
| **文件上传** | 前端文件选择器 | `.py` / `.json` / `.yaml` 格式 |

### 2.2 导入流程

```
用户选择导入方式
     │
     ├── GitHub URL → 解析 owner/repo/path → 调用 GitHub API 获取文件内容
     ├── HTTPS URL → HTTP GET 下载内容
     └── 文件上传 → FormData → 后端接收
           │
           ▼
     [内容解析]
     ├── Python → AST 解析验证语法
     ├── JSON → Schema 验证
     └── YAML → 解析为 Skill 配置
           │
           ▼
     [安全审查] ← 自动触发
           │
           ▼
     [存储] → SkillRecord 持久化
```

### 2.3 API 设计

```
POST /api/v1/skills/import
Body:
{
  "source": "github" | "url" | "upload",
  "github_url": "https://github.com/user/repo/blob/main/skills/my_skill.py",  // source=github
  "url": "https://example.com/skill.py",                                        // source=url
  "content": "...",                                                              // source=upload
  "name": "my-skill",
  "description": "技能描述",
  "tags": ["web", "search"]
}

Response:
{
  "id": "uuid",
  "name": "my-skill",
  "review_status": "pending" | "approved" | "rejected",
  "review_result": { ... }
}
```

---

## 3. 安全审查机制

### 3.1 审查流程

```
Skill 内容提交
     │
     ▼
[第一层：静态分析] ← AST白名单（已有）
  ├── 禁止 import os/subprocess/sys
  ├── 禁止 exec()/eval()/__import__()
  ├── 禁止网络调用（socket/requests）
  └── 通过/拒绝
     │ 通过
     ▼
[第二层：LLM 审查]
  ├── 将代码提交给 LLM（使用系统内置 Provider）
  ├── Prompt：检查安全风险、数据泄露、恶意逻辑
  └── 返回 risk_level + findings 列表
     │
     ├── risk_level = "safe" → 自动批准
     ├── risk_level = "low" → 自动批准 + 警告标记
     ├── risk_level = "medium" → 进入人工审核队列
     └── risk_level = "high" → 自动拒绝
     │
     ▼
[第三层：人工审核]（可选）
  ├── Admin 用户在审核队列中查看
  ├── 审核内容：代码 + LLM 审查报告
  └── 操作：批准 / 拒绝 / 要求修改
```

### 3.2 LLM 审查 Prompt

```
你是一个代码安全审查专家。请审查以下 Agent Skill 代码，检查：

1. **安全风险**：是否存在命令注入、代码注入、文件系统越权访问？
2. **数据泄露**：是否有硬编码密钥、凭证，或尝试外泄用户数据？
3. **恶意逻辑**：是否存在无限循环、资源耗尽、隐蔽后门？
4. **合规性**：是否符合安全编码最佳实践？

输出格式：
{
  "risk_level": "safe" | "low" | "medium" | "high",
  "findings": [
    { "severity": "info" | "warning" | "critical", "description": "..." }
  ],
  "summary": "一句话总结"
}

代码：
{skill_content}
```

### 3.3 数据模型扩展

```python
# SkillRecord 新增字段
class SkillRecord(SoftDeleteMixin, Base):
    # ... 现有字段 ...
    
    # 审查相关
    review_status: Mapped[str] = mapped_column(default="pending")  # pending/approved/rejected
    review_result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)  # LLM审查结果
    reviewed_by: Mapped[UUID | None] = mapped_column(nullable=True)  # 人工审核者
    reviewed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    
    # 来源相关
    source_type: Mapped[str] = mapped_column(default="manual")  # manual/github/url/upload/generated
    source_url: Mapped[str | None] = mapped_column(nullable=True)
    
    # 访问控制
    visibility: Mapped[str] = mapped_column(default="private")  # private/org/public
```

---

## 4. 版本管理

### 4.1 版本模型

每次更新 Skill 时创建新版本快照，保留完整内容：

```python
class SkillVersion(Base):
    id: Mapped[UUID]
    skill_id: Mapped[UUID]        # FK → SkillRecord
    version: Mapped[str]           # semver: "1.0.0"
    content: Mapped[str]           # 完整 Skill 内容
    changelog: Mapped[str | None]  # 变更说明
    review_status: Mapped[str]     # 每个版本独立审查
    created_at: Mapped[datetime]
    created_by: Mapped[UUID]
```

### 4.2 版本操作

| 操作 | 说明 |
|------|------|
| 升级 | 创建新版本，自动触发安全审查 |
| 回滚 | 切换 SkillRecord 当前版本指针 |
| 对比 | 两个版本间的 diff 展示 |
| 历史 | 按时间线浏览所有版本 |

---

## 5. 市场机制增强

### 5.1 发布流程

```
Skill 通过安全审查
     │
     ▼
[发布到市场]
  ├── 填写发布信息（标题、描述、分类、标签、截图）
  ├── 选择可见范围（公开 / 组织内 / 私有）
  └── 提交发布
     │
     ▼
[市场展示]
  ├── 按分类浏览：通用工具 / 数据分析 / DevOps / 客服 / 编程助手
  ├── 搜索：名称 + 标签 + 描述全文匹配
  ├── 排序：安装量 / 评分 / 最新更新
  └── 详情页：描述 + 代码预览 + 评价 + 版本历史
```

### 5.2 安装机制

```
用户在市场找到 Skill
     │
     ▼
[安装]
  ├── 检查兼容性（适用 Agent 类型）
  ├── 检查依赖冲突（与已安装 Skill）
  └── 复制 Skill 到用户空间
     │
     ▼
[绑定到 Agent]
  ├── Agent 编辑页的 skills 多选列表
  └── Runner 执行时自动加载
```

---

## 6. 前端页面设计

### 6.1 Skill 管理页增强

| 功能 | 现状 | 增强 |
|------|:----:|:----:|
| 列表浏览 | ✅ | 增加审查状态过滤 |
| 创建编辑 | ✅ | 增加导入入口（GitHub/URL/上传） |
| 搜索 | ✅ | 增加标签过滤 |
| 版本历史 | ❌ | 新增版本列表+对比+回滚 |
| 审核队列 | ❌ | Admin 专属审核页面 |

### 6.2 市场页增强

| 功能 | 现状 | 增强 |
|------|:----:|:----:|
| 浏览卡片 | ✅ | 增加安装量和评分徽章 |
| 筛选排序 | ✅ | 增加排序选项（热门/评分/最新） |
| 安装 | ✅ | 增加版本选择 |
| 评价 | ✅ (API) | 前端集成评价组件 |
| 详情页 | ❌ | 新增 Skill 详情页（描述+代码+评价+历史） |

---

## 7. 实施计划

| Phase | 内容 | 优先级 |
|-------|------|:------:|
| **Phase 1** | 多源导入 API + 前端导入弹窗（GitHub/URL/上传） | P1 |
| **Phase 2** | LLM 安全审查 + review_status 字段 + 审核队列页 | P1 |
| **Phase 3** | 版本管理（SkillVersion ORM + 版本列表/对比 UI） | P2 |
| **Phase 4** | 访问控制（visibility 字段 + 权限过滤） | P2 |
| **Phase 5** | 市场增强（详情页 + 排序 + 版本选择安装） | P2 |
| **Phase 6** | 依赖管理（依赖声明 + 冲突检测） | P3 |

---

## 8. 审批签署

- **PM 评估**：✅ P2 级垂直 Agent 能力，Skill 市场是 Agent 生态建设的关键环节
- **架构师方案**：✅ 增量改造，不改现有 API，新增字段+端点
- **审查员确认**：✅ AST 白名单 + LLM 审查双层安全，不引入外部执行风险
- **决策者裁决**：✅ 按 Phase 分阶段实施

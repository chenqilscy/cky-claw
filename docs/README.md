# CkyClaw 文档目录规范

## 目录结构

```
docs/
├── README.md              ← 本文件：目录规范与命名约定
├── spec/                  ← 正式规格文档（PRD、设计文档、数据模型）
│   ├── CkyClaw PRD v2.0.md              ← 总纲（一~三章 + 附录 + 索引）
│   ├── CkyClaw PRD-Agent编排 v2.0.md    ← 分册：四~六章
│   ├── CkyClaw PRD-企业能力 v2.0.md     ← 分册：七~十章
│   ├── CkyClaw PRD-基础设施 v2.0.md     ← 分册：十一~十五章
│   ├── CkyClaw Framework Design v2.0.md
│   ├── CkyClaw API Design v1.2.md
│   ├── CkyClaw Application Design v1.2.md
│   ├── CkyClaw Data Model v1.3.md
│   └── todo.md            ← 文档层面的待办事项
├── plan/                  ← 迭代计划、里程碑、Sprint 计划（暂空）
├── references/            ← 竞品分析、技术调研、外部参考资料
│   ├── codex-cli-architecture.md
│   ├── competitive-analysis.md
│   └── DeerFlow/
└── (未来) guides/         ← 开发指南、部署手册、运维手册
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

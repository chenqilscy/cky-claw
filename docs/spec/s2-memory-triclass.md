# S2 记忆三类化详细设计

## 1. 概述

### 1.1 目标

从当前的 MemoryEntry 单一模型升级为完整的三类记忆系统，每类记忆有专属的提取、检索和注入路径，使 Agent 在跨会话对话中能引用历史知识。

### 1.2 三类记忆映射

| 枚举值 | 记忆类型 | 存储内容 | 检索方式 |
|--------|---------|---------|---------|
| `USER_PROFILE` | Episodic（情景） | 用户偏好、档案、技术栈 | 关键词匹配 |
| `HISTORY_SUMMARY` | Episodic（情景） | 对话摘要、会话事件 | 全文搜索 |
| `STRUCTURED_FACT` | Semantic（语义） | 提取的知识/事实 | 关键词 + 可选 embedding |

> Procedural 记忆（Agent 自创模式/工具配置）复用 Skill 系统，不在 MemoryEntry 中建模。

### 1.3 当前状态

- MemoryType 枚举已有三类 ✅
- MemoryEntry 已有 confidence + decay ✅
- InMemoryMemoryBackend 完整实现 ✅
- MemoryExtractionHook 提供 Hook 级集成 ✅
- MemoryRetriever 提供检索 + 格式化 ✅

### 1.4 缺失项

| 项 | 当前状态 | S2 目标 |
|----|---------|---------|
| embedding 字段 | ❌ 不存在 | MemoryEntry 新增可选 embedding |
| tags 字段 | ❌ 不存在 | MemoryEntry 新增标签分类 |
| Runner 自动注入 | ❌ 只能通过 Hook | MemoryInjector 自动在 LLM 调用前注入 |
| RunConfig 集成 | ❌ 无 memory 字段 | 新增 memory_backend + memory_config |
| 容量管理 | ❌ 无上限 | max_entries + 自动归档 |
| Backend REST API | ❌ 不存在 | /api/v1/memories/* CRUD + 搜索 |

## 2. Framework 层变更

### 2.1 MemoryEntry 扩展

```python
@dataclass
class MemoryEntry:
    # ... 现有字段不变 ...
    
    # S2 新增
    embedding: list[float] | None = None
    """可选向量表示，用于语义相似度检索。"""
    
    tags: list[str] = field(default_factory=list)
    """分类标签，用于 Procedural 记忆快速过滤。"""
    
    access_count: int = 0
    """访问计数，用于 LRU 淘汰和热度排序。"""
```

### 2.2 MemoryInjector

新建 `memory/injector.py`：

```python
@dataclass
class MemoryInjectionConfig:
    max_memory_tokens: int = 1000
    min_confidence: float = 0.3
    inject_types: list[MemoryType] | None = None  # None = 全部
    
class MemoryInjector:
    def __init__(self, backend: MemoryBackend, config: MemoryInjectionConfig | None = None):
        ...
    
    async def build_memory_context(self, user_id: str, query: str) -> str:
        """检索相关记忆，格式化为可注入 system 消息的文本。"""
```

### 2.3 RunConfig 集成

```python
@dataclass
class RunConfig:
    # ... 现有字段 ...
    
    memory_backend: MemoryBackend | None = None
    """记忆存储后端。配置后 Runner 自动注入历史记忆到 system 消息。"""
    
    memory_user_id: str | None = None
    """记忆所属用户 ID。配合 memory_backend 使用。"""
    
    memory_injection_config: MemoryInjectionConfig | None = None
    """记忆注入配置。None 时使用默认配置。"""
```

### 2.4 Runner 注入点

在 `_build_system_messages()` 中，cache prefix 之后、Agent instructions 之前注入：

```
[cache prefix]     ← S1 已实现
[memory context]   ← S2 新增
[instructions]     ← 现有
```

### 2.5 MemoryBackend 扩展

```python
class MemoryBackend(ABC):
    # ... 现有方法 ...
    
    async def count(self, user_id: str) -> int:
        """返回用户记忆条目总数。默认实现使用 list_entries。"""
        entries = await self.list_entries(user_id)
        return len(entries)
```

## 3. Backend API

### 3.1 路由设计

| 方法 | 路径 | 功能 |
|------|------|------|
| GET | /api/v1/memories | 列出当前用户记忆（分页 + 类型过滤） |
| GET | /api/v1/memories/:id | 查询单条记忆 |
| POST | /api/v1/memories | 创建记忆条目 |
| PUT | /api/v1/memories/:id | 更新记忆条目 |
| DELETE | /api/v1/memories/:id | 删除记忆条目 |
| POST | /api/v1/memories/search | 搜索记忆（关键词 + 类型 + 标签） |
| POST | /api/v1/memories/decay | 执行指定用户的记忆衰减 |

### 3.2 Pydantic Schema

```python
class MemoryCreate(BaseModel):
    type: MemoryType = MemoryType.STRUCTURED_FACT
    content: str
    confidence: float = 1.0
    agent_name: str | None = None
    tags: list[str] = []
    metadata: dict[str, Any] = {}

class MemoryUpdate(BaseModel):
    content: str | None = None
    confidence: float | None = None
    tags: list[str] | None = None
    metadata: dict[str, Any] | None = None

class MemorySearchRequest(BaseModel):
    query: str
    memory_type: MemoryType | None = None
    tags: list[str] | None = None
    min_confidence: float = 0.0
    limit: int = 20
```

## 4. 测试计划

| 测试类 | 覆盖点 |
|--------|--------|
| TestMemoryEntryExtended | embedding/tags/access_count 新字段 |
| TestMemoryInjector | 检索 + 格式化 + token 预算 |
| TestRunnerMemoryIntegration | RunConfig.memory_backend → system 消息注入 |
| TestMemoryBackendCount | count() 默认实现 |
| TestMemorySearchByTags | 标签过滤搜索 |

## 5. 向后兼容

- MemoryEntry 新字段均有默认值，不破坏现有序列化
- RunConfig 新字段默认 None，不影响已有配置
- 现有 MemoryExtractionHook + MemoryRetriever 接口不变

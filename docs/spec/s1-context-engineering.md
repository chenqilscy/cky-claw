# S1 上下文工程详设文档

> 版本 v1.0 · 2026-04-11

---

## 一、目标

将 HistoryTrimmer 从 2 策略升级到 5 Tier 渐进式上下文管理体系，实现 Artifact Store 外部化大型工具输出，新增 PROGRESSIVE 和 SUMMARY_PREFIX 策略。

## 二、模块设计

### 2.1 新增模块：artifacts/

```
kasaya/
└── artifacts/
    ├── __init__.py       # 导出 Artifact, ArtifactStore, LocalArtifactStore
    ├── artifact.py       # Artifact 数据类
    └── store.py          # ArtifactStore 抽象 + LocalArtifactStore 实现
```

### 2.2 Artifact 数据模型

```python
@dataclass
class Artifact:
    artifact_id: str          # UUID
    run_id: str               # 所属运行 ID
    content: str              # 原始内容
    summary: str              # 摘要（截取前 200 字符）
    token_count: int          # 估算 token 数
    metadata: dict[str, Any]  # 扩展元数据（tool_name, created_at 等）
    created_at: datetime
```

### 2.3 ArtifactStore 接口

```python
class ArtifactStore(ABC):
    async def save(self, run_id: str, content: str, metadata: dict) -> Artifact
    async def load(self, artifact_id: str) -> Artifact | None
    async def list_by_run(self, run_id: str) -> list[Artifact]
    async def cleanup(self, older_than: datetime) -> int
```

### 2.4 LocalArtifactStore

- 存储路径：`{base_dir}/artifacts/{run_id}/{artifact_id}.json`
- 使用 `aiofiles` 异步 I/O
- `cleanup()` 删除过期文件

### 2.5 HistoryTrimmer 扩展

新增 PROGRESSIVE 策略枚举：

```python
class HistoryTrimStrategy(str, Enum):
    SLIDING_WINDOW = "sliding_window"
    TOKEN_BUDGET = "token_budget"
    PROGRESSIVE = "progressive"        # 5 Tier 渐进
    SUMMARY_PREFIX = "summary_prefix"  # LLM 摘要前缀
```

PROGRESSIVE 策略处理流程：
1. Tier 0: 默认保留所有消息
2. Tier 1: 截断单条 >max_result_chars 的工具结果
3. Tier 2: 超 80% 预算时淘汰最旧的工具结果
4. Tier 3: 超 90% 预算时对早期消息做摘要（需 LLM callback）
5. Tier 4: 外部状态充分时标记可以 fresh restart

### 2.6 RunConfig 新增字段

```python
@dataclass
class RunConfig:
    # ... 现有字段 ...
    artifact_store: ArtifactStore | None = None
    artifact_threshold: int = 8000       # token 阈值，超过则外部化
    max_tool_result_chars: int = 0       # 单条工具结果最大字符数，0=不限制
```

### 2.7 Runner 集成点

1. `_execute_tool_calls()` 中工具结果 → 检查 token 数 → 超阈值则存入 ArtifactStore，替换为摘要+引用
2. `_build_system_message()` 中 system prompt 拆分为 stable_prefix（不变） + 动态部分（每次可变）
3. HistoryTrimmer.trim() 中新增 PROGRESSIVE 分支

## 三、测试用例设计

### 3.1 Artifact Store 测试
- test_save_and_load: 保存后能正确读取
- test_save_generates_summary: 摘要不超过 200 字符
- test_list_by_run: 按 run_id 查询
- test_cleanup: 过期 artifact 被删除
- test_load_nonexistent: 返回 None

### 3.2 HistoryTrimmer PROGRESSIVE 测试
- test_progressive_tier1_truncate_large_tool_result: 大工具结果被截断
- test_progressive_tier2_evict_old_tool_results: 超 80% 预算时淘汰旧结果
- test_progressive_preserves_system_messages: system 消息不被裁剪
- test_progressive_within_budget_no_change: 预算内不裁剪

### 3.3 RunConfig 集成测试
- test_artifact_externalization_in_runner: 工具结果超阈值时自动外部化
- test_max_tool_result_chars: 工具结果被截断到指定长度

### 3.4 向后兼容测试
- test_default_config_unchanged: 默认 RunConfig 行为不变
- test_existing_strategies_unaffected: SLIDING_WINDOW / TOKEN_BUDGET 不受影响
